#!/usr/bin/env python3
"""
Timed coding exercise: Product scraper with AI categorization.
Scrapes products from Amazon (or fallback to FakeStore API), then categorizes via Claude.
"""

import argparse
import json
import logging
import os
import sys
from typing import Any

import requests
from anthropic import Anthropic
from pydantic import BaseModel, ValidationError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


class Product(BaseModel):
    title: str
    price: str | None = None
    rating: str | None = None
    url: str
    category: str | None = None


class ProductEnhancement(BaseModel):
    category: str
    sentiment: str


class EnhancementList(BaseModel):
    enhancements: list[ProductEnhancement]


def scrape_amazon(query: str) -> list[dict[str, Any]] | None:
    """
    Scrape first 5 products from Amazon using Selenium.
    Returns None if Amazon blocks (captcha, timeout, empty results).
    """
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.support.ui import WebDriverWait
    except ImportError:
        return None

    url = f"https://www.amazon.com/s?k={query.replace(' ', '+')}"
    products: list[dict[str, Any]] = []

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    driver = None
    try:
        logger.info("Attempting Amazon scrape: %s", url)
        driver = webdriver.Chrome(options=options)
        driver.get(url)

        # Wait for product listings (Amazon uses various selectors; try common ones)
        wait = WebDriverWait(driver, 15)
        wait.until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "[data-component-type='s-search-result']")
            )
        )

        # Get first 5 product cards
        cards = driver.find_elements(
            By.CSS_SELECTOR, "[data-component-type='s-search-result']"
        )[:5]

        if not cards:
            logger.warning(
                "Amazon: default selector found no cards — asking Claude for recovery selector"
            )
            recovered_selector = get_selector_from_claude(driver.page_source)
            if recovered_selector:
                try:
                    cards = driver.find_elements(By.CSS_SELECTOR, recovered_selector)[
                        :5
                    ]
                    logger.info("Recovery selector found %d cards", len(cards))
                except Exception:
                    logger.warning("Recovery selector failed")
                    cards = []
            if not cards:
                return None

        for card in cards:
            product: dict[str, Any] = {
                "title": "",
                "price": None,
                "rating": None,
                "url": "",
            }

            try:
                # Title and URL
                title_el = card.find_elements(By.CSS_SELECTOR, "h2 a")
                if title_el:
                    product["title"] = title_el[0].text.strip()
                    href = title_el[0].get_attribute("href") or ""
                    # Ensure full URL
                    product["url"] = (
                        href
                        if href.startswith("http")
                        else f"https://www.amazon.com{href}"
                    )

                # Price
                price_el = card.find_elements(By.CSS_SELECTOR, ".a-price .a-offscreen")
                if price_el:
                    raw = price_el[0].get_attribute("textContent") or ""
                    product["price"] = raw.strip()

                # Rating
                rating_el = card.find_elements(
                    By.CSS_SELECTOR, ".a-icon-star-small .a-icon-alt"
                )
                if rating_el:
                    product["rating"] = rating_el[0].get_attribute("textContent")

                if product["title"]:
                    products.append(product)

            except Exception:
                continue

        # Check for block indicators (captcha, robot check)
        page_source = driver.page_source.lower()
        if (
            "robot" in page_source
            or "captcha" in page_source
            or "enter the characters" in page_source
        ):
            logger.warning("Amazon: bot detection triggered")
            return None

        logger.info("Amazon: scraped %d products", len(products))

        return products if products else None

    except Exception:
        return None
    finally:
        if driver:
            driver.quit()


def scrape_fakestore(query: str) -> list[dict[str, Any]]:
    """
    Fallback: fetch first 5 products from FakeStore API via requests.
    """
    logger.info("Using FakeStore API fallback")
    resp = requests.get("https://fakestoreapi.com/products", timeout=10)
    resp.raise_for_status()
    data = resp.json()

    products: list[dict[str, Any]] = []
    for item in data[:5]:
        rating = None
        if "rating" in item and isinstance(item["rating"], dict):
            rating = str(item["rating"].get("rate", ""))
        elif "rating" in item:
            rating = str(item["rating"])

        products.append(
            {
                "title": item.get("title", ""),
                "price": str(item.get("price", "")),
                "rating": rating,
                "url": f"https://fakestoreapi.com/products/{item.get('id', '')}",
            }
        )
    return products


def scrape_books(query: str) -> list[dict[str, Any]] | None:
    """
    Secondary fallback: scrape books.toscrape.com using Selenium.
    Built for scraper practice — never blocks.
    Returns first 5 books as products.
    """
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.support.ui import WebDriverWait
    except ImportError:
        return None

    url = "https://books.toscrape.com"
    products: list[dict[str, Any]] = []

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    driver = None
    try:
        logger.info("Attempting books.toscrape.com scrape")
        driver = webdriver.Chrome(options=options)
        driver.get(url)

        wait = WebDriverWait(driver, 15)
        wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "article.product_pod"))
        )

        cards = driver.find_elements(By.CSS_SELECTOR, "article.product_pod")[:5]

        if not cards:
            logger.warning("books.toscrape.com: no products found")
            return None

        for card in cards:
            product: dict[str, Any] = {
                "title": "",
                "price": None,
                "rating": None,
                "url": "",
            }
            try:
                title_el = card.find_elements(By.CSS_SELECTOR, "h3 a")
                if title_el:
                    product["title"] = title_el[0].get_attribute("title") or ""
                    href = title_el[0].get_attribute("href") or ""
                    product["url"] = href

                price_el = card.find_elements(By.CSS_SELECTOR, ".price_color")
                if price_el:
                    product["price"] = price_el[0].text.strip()

                rating_el = card.find_elements(By.CSS_SELECTOR, ".star-rating")
                if rating_el:
                    product["rating"] = (
                        rating_el[0].get_attribute("class").replace("star-rating ", "")
                    )

                if product["title"]:
                    products.append(product)

            except Exception:
                continue

        logger.info("books.toscrape.com: scraped %d products", len(products))
        return products if products else None

    except Exception:
        return None
    finally:
        if driver:
            driver.quit()


def get_selector_from_claude(page_source: str) -> str | None:
    """
    Ask Claude to find the CSS selector for product listings on a page.
    Used as a recovery mechanism when the default selector returns no results.
    Sends a truncated version of the page HTML to avoid token limits.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None

    # Truncate to first 15000 chars — enough structure without blowing context
    truncated = page_source[:15000]

    client = Anthropic(api_key=api_key)
    prompt = f"""You are a web scraping expert. Look at this HTML and return ONLY a CSS selector
that would find product listing cards on this page. Return the selector string only — no explanation,
no markdown, no punctuation. If you cannot find product listings, return the word NONE.

HTML:
{truncated}"""

    try:
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=64,
            messages=[{"role": "user", "content": prompt}],
        )
        selector = message.content[0].text.strip()
        if selector == "NONE" or not selector:
            return None
        logger.info("Claude suggested selector: %s", selector)
        return selector
    except Exception:
        return None


def categorize_with_claude(products: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Send product list to Claude API and add 'category' field to each.
    Categories: budget, mid-range, gaming, professional.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable is not set")

    logger.info("Calling Claude API for enhancement")
    client = Anthropic(api_key=api_key)
    products_json = json.dumps(products, indent=2)

    prompt = f"""Given these products, return a JSON array with the same length and order.
Each element must be an object with exactly two fields:
- "category": a short category label that best describes this product (e.g. "budget", "gaming", "professional", "fiction", "non-fiction", "thriller", "self-help") — infer the right category from the product itself
- "sentiment": one sentence describing the product's appeal based on title, price, and rating

Example: [{{"category": "budget", "sentiment": "Affordable option with solid ratings for everyday use."}}]

Return JSON only. No markdown, no preamble.

Products:
{products_json}"""

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=256,
        messages=[{"role": "user", "content": prompt}],
    )

    text = message.content[0].text
    # Extract JSON array from response (handle markdown code blocks)
    if "```" in text:
        start = text.find("[")
        end = text.rfind("]") + 1
        text = text[start:end]
    try:
        raw = json.loads(text)
        validated = EnhancementList(enhancements=raw)
        for i, product in enumerate(products):
            if i < len(validated.enhancements):
                enh = validated.enhancements[i]
                product["category"] = enh.category or "uncategorized"
                product["sentiment"] = enh.sentiment
            else:
                product["category"] = "uncategorized"
                product["sentiment"] = ""
    except (json.JSONDecodeError, ValidationError):
        for product in products:
            product["category"] = "uncategorized"
            product["sentiment"] = ""

    return products


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scrape products and categorize with AI"
    )
    parser.add_argument(
        "--query", default="laptops", help="Search query for Amazon (default: laptops)"
    )
    args = parser.parse_args()

    # Attempt Amazon twice, then books.toscrape.com, then FakeStore API
    logger.info("Attempt 1: Amazon")
    products = scrape_amazon(args.query)
    if products is None:
        logger.info("Attempt 2: Amazon")
        products = scrape_amazon(args.query)
    if products is None:
        logger.info("Amazon failed — trying books.toscrape.com")
        products = scrape_books(args.query)
    if products is None:
        logger.info("All Selenium attempts failed — falling back to FakeStore API")
        products = scrape_fakestore(args.query)

    if not products:
        print(
            json.dumps({"status": "error", "reason": "No products found"}),
            file=sys.stderr,
        )
        sys.exit(1)

    # Part 2: AI enhancement
    try:
        products = categorize_with_claude(products)
        print(json.dumps({"status": "ok", "products": products}, indent=2))
    except Exception as e:
        # Degraded: return products without categories rather than crashing
        print(
            json.dumps(
                {"status": "degraded", "reason": str(e), "products": products}, indent=2
            )
        )


if __name__ == "__main__":
    main()
