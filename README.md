# InstaPermit Exercise

Scrapes product listings and enhances them with AI categorization.

## How It Works
1. Attempts to scrape the first 5 products from Amazon using Selenium
2. Falls back to FakeStore API if Amazon blocks the request
3. Sends products to Claude API for categorization
4. Returns structured JSON with status: ok / degraded / error

## Setup
```bash
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

Set your Anthropic API key:
```bash
export ANTHROPIC_API_KEY=your-key-here  # Mac/Linux
$env:ANTHROPIC_API_KEY="your-key-here"  # Windows
```

## Usage
```bash
python scraper.py                        # default: laptops
python scraper.py --query "headphones"  # custom query
```

## Output
```json
{
  "status": "ok",
  "products": [
    {
      "title": "...",
      "price": "...",
      "rating": "...",
      "url": "...",
      "category": "budget | mid-range | gaming | professional"
    }
  ]
}
```

## Degraded Mode
If Claude is unavailable, products are returned without categories and status is set to `degraded`. The scrape always succeeds independently of the AI step.
