#!/usr/bin/env python3
"""
Timed coding exercise: Product scraper with AI categorization.
Scrapes products from Amazon (or fallback to FakeStore API), then categorizes via Claude.
"""

import argparse
import json
import os
import sys
from typing import Any

import requests


def scrape_amazon(query: str) -> list[dict[str, Any]] | None:
    """
    Scrape first 5 products from Amazon using Selenium.
    Returns None if Amazon blocks (captcha, timeout, empty results).
    """
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
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

    driver = None
    try:
        driver = webdriver.Chrome(options=options)
        driver.get(url)

        # Wait for product listings (Amazon uses various selectors; try common ones)
        wait = WebDriverWait(driver, 15)
        wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "[data-component-type='s-search-result']"))
        )

        # Get first 5 product cards
        cards = driver.find_elements(By.CSS_SELECTOR, "[data-component-type='s-search-result']")[:5]

        if not cards:
            # Maybe blocked or different layout
            return None

        for card in cards:
            product: dict[str, Any] = {"title": "", "price": None, "rating": None, "url": ""}

            try:
                # Title and URL
                title_el = card.find_elements(By.CSS_SELECTOR, "h2 a")
                if title_el:
                    product["title"] = title_el[0].text.strip()
                    href = title_el[0].get_attribute("href") or ""
                    # Ensure full URL
                    product["url"] = href if href.startswith("http") else f"https://www.amazon.com{href}"

                # Price
                price_el = card.find_elements(By.CSS_SELECTOR, ".a-price .a-offscreen")
                if price_el:
                    raw = price_el[0].get_attribute("textContent") or ""
                    product["price"] = raw.strip()

                # Rating
                rating_el = card.find_elements(By.CSS_SELECTOR, ".a-icon-star-small .a-icon-alt")
                if rating_el:
                    product["rating"] = rating_el[0].get_attribute("textContent")

                if product["title"]:
                    products.append(product)

            except Exception:
                continue

        # Check for block indicators (captcha, robot check)
        page_source = driver.page_source.lower()
        if "robot" in page_source or "captcha" in page_source or "enter the characters" in page_source:
            return None

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

        products.append({
            "title": item.get("title", ""),
            "price": str(item.get("price", "")),
            "rating": rating,
            "url": f"https://fakestoreapi.com/products/{item.get('id', '')}",
        })
    return products


def categorize_with_claude(products: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Send product list to Claude API and add 'category' field to each.
    Categories: budget, mid-range, gaming, professional.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable is not set")

    from anthropic import Anthropic

    client = Anthropic(api_key=api_key)
    products_json = json.dumps(products, indent=2)

    prompt = f"""Given these products, categorize each one as exactly one of: "budget", "mid-range", "gaming", or "professional".
Return a JSON array with the same length and order, each element being the category string only.
Example: ["budget", "mid-range", "gaming", "professional", "budget"]

Products:
{products_json}"""

    message = client.messages.create(
        model="claude-3-5-haiku-20241022",
        max_tokens=256,
        messages=[{"role": "user", "content": prompt}],
    )

    text = message.content[0].text
    # Extract JSON array from response (handle markdown code blocks)
    if "```" in text:
        start = text.find("[")
        end = text.rfind("]") + 1
        text = text[start:end]
    categories = json.loads(text)

    for i, product in enumerate(products):
        cat = categories[i] if i < len(categories) else "mid-range"
        if cat not in ("budget", "mid-range", "gaming", "professional"):
            cat = "mid-range"
        product["category"] = cat

    return products


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape products and categorize with AI")
    parser.add_argument("--query", default="laptops", help="Search query for Amazon (default: laptops)")
    args = parser.parse_args()

    # Part 1: Scrape products
    products = scrape_amazon(args.query)
    if products is None:
        products = scrape_fakestore(args.query)

    if not products:
        print(json.dumps({"error": "No products found"}), file=sys.stderr)
        sys.exit(1)

    # Part 2: AI enhancement
    try:
        products = categorize_with_claude(products)
    except Exception as e:
        print(json.dumps({"error": str(e), "products": products}), file=sys.stderr)
        sys.exit(1)

    # Output final enhanced data as JSON
    print(json.dumps(products, indent=2))


if __name__ == "__main__":
    main()
