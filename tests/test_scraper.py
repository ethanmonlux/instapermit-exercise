"""
Tests for scraper.py — covers happy path, degraded mode, and edge cases.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from scraper import categorize_with_claude, scrape_fakestore


# --- FakeStore tests ---


def test_fakestore_returns_five_products():
    products = scrape_fakestore("laptops")
    assert len(products) == 5


def test_fakestore_product_shape():
    products = scrape_fakestore("laptops")
    for p in products:
        assert "title" in p
        assert "price" in p
        assert "rating" in p
        assert "url" in p


# --- Claude categorization tests ---

MOCK_PRODUCTS = [
    {
        "title": "Cheap Laptop",
        "price": "299.99",
        "rating": "3.5",
        "url": "https://example.com/1",
    },
    {
        "title": "Gaming Beast Pro",
        "price": "1999.99",
        "rating": "4.8",
        "url": "https://example.com/2",
    },
]

VALID_CLAUDE_RESPONSE = json.dumps(
    [
        {"category": "budget", "sentiment": "Great value for basic tasks."},
        {"category": "gaming", "sentiment": "Top-tier performance for serious gamers."},
    ]
)


def test_categorize_happy_path():
    mock_message = MagicMock()
    mock_message.content[0].text = VALID_CLAUDE_RESPONSE

    with patch("scraper.Anthropic") as mock_anthropic:
        mock_anthropic.return_value.messages.create.return_value = mock_message
        products = categorize_with_claude([p.copy() for p in MOCK_PRODUCTS])

    assert products[0]["category"] == "budget"
    assert products[1]["category"] == "gaming"
    assert "sentiment" in products[0]
    assert "sentiment" in products[1]


def test_categorize_degraded_on_bad_json():
    mock_message = MagicMock()
    mock_message.content[0].text = "not valid json at all"

    with patch("scraper.Anthropic") as mock_anthropic:
        mock_anthropic.return_value.messages.create.return_value = mock_message
        products = categorize_with_claude([p.copy() for p in MOCK_PRODUCTS])

    # Should not crash — defaults to uncategorized
    assert products[0]["category"] == "uncategorized"
    assert products[1]["category"] == "uncategorized"


def test_categorize_dynamic_categories_pass_through():
    bad_response = json.dumps(
        [
            {"category": "unknown_category", "sentiment": "Some sentiment."},
            {"category": "budget", "sentiment": "Good value."},
        ]
    )
    mock_message = MagicMock()
    mock_message.content[0].text = bad_response

    with patch("scraper.Anthropic") as mock_anthropic:
        mock_anthropic.return_value.messages.create.return_value = mock_message
        products = categorize_with_claude([p.copy() for p in MOCK_PRODUCTS])

    # Categories are open-ended — Claude's category passes through as-is
    assert products[0]["category"] == "unknown_category"
    assert products[1]["category"] == "budget"


def test_categorize_missing_api_key():
    with patch.dict("os.environ", {}, clear=True):
        import os

        os.environ.pop("ANTHROPIC_API_KEY", None)
        with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
            categorize_with_claude([p.copy() for p in MOCK_PRODUCTS])
