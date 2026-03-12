# InstaPermit Exercise — Claude Code Context

> Read this file before making any changes.

## Project
Timed coding exercise: scrape products with Selenium, enhance with Claude API.
Single file: scraper.py. Submit via GitHub repo link.

## Safety Rules (non-negotiable)
- Never commit .env or API keys — ANTHROPIC_API_KEY comes from environment only
- Never log or print API keys or secrets
- Always validate Claude's structured output with Pydantic before using it — treat LLM output like untrusted user input
- Fail-silent on LLM errors: if Claude is unavailable, return products without categories (degraded), never crash
- Structured output only — every exit path returns status: ok / degraded / error

## Reliability Principles
- Fail-closed on missing credentials: raise immediately if ANTHROPIC_API_KEY is not set
- Fail-open on LLM enrichment: scrape succeeds even if categorization fails — degraded is better than nothing
- Explicit waits only — never use time.sleep()
- Always close browser in finally block — no resource leaks
- Fallback chain: Amazon (x2) → books.toscrape.com (Selenium) → FakeStore API (requests)
- Dynamic selector recovery: if Amazon returns no cards, ask Claude for the right selector before giving up
- Handle empty results explicitly — never let None propagate silently

## Code Style
- Surgical edits over rewrites
- Minimal changes — don't refactor things that aren't broken
- Read the file before proposing any change
- One function, one responsibility
- Comments explain why, not what

## Architecture
- scraper.py — single file, five functions + main()
  - scrape_amazon() — Selenium, returns list[dict] | None on block/failure. Attempts dynamic selector recovery via Claude before giving up.
  - scrape_books() — Selenium fallback to books.toscrape.com, never blocks
  - scrape_fakestore() — requests fallback, always returns list[dict]
  - get_selector_from_claude() — sends truncated page HTML to Claude, returns recovered CSS selector or None
  - categorize_with_claude() — Anthropic API, Pydantic-validated output, adds category + sentiment fields
  - main() — argparse, orchestration, structured JSON output

## Output Schema
All output printed as JSON with:
- status: "ok" | "degraded" | "error"
- products: list of dicts (title, price, rating, url, category, sentiment)
- reason: human-readable message if status != "ok"

## Pre-commit Checks
- ruff check . --fix && ruff format .
- python scraper.py runs clean before pushing
- No .env committed — verify with git status
