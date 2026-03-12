# TODO

## Testing
- [ ] Mock FakeStore HTTP call in test_fakestore_returns_five_products and test_fakestore_product_shape — currently makes a real network request on every test run
- [ ] Add integration tests for scrape_amazon() and scrape_books() — requires real browser and network, should live in a separate tests/integration/ suite

## Code Quality
- [ ] scrape_amazon() and scrape_books() share identical Chrome options setup — extract into a helper function to avoid duplication
