---
name: zhihu-scraper-contracts
description: Use when changing scraper payload parsing, typed scraper contracts, supported Zhihu URL handling, browser fallback behavior, or anti-drift tests.
---

# Scraper Contracts

## Guardrails

- `core/scraper.py` should not become an unbounded god object again; keep downloader, humanizer, payload, and contracts separate.
- `core/scraper_payloads.py` owns normalized payload extraction.
- `core/scraper_contracts.py` owns typed data contracts.
- Prefer fixing current validated paths over adding new scraping surfaces.
- Browser fallback is optional support, not the default persistence model.

## Validation

Run `python -m unittest -q tests.test_scraper tests.test_scraper_payloads tests.test_scraper_contracts tests.test_browser_fallback` for scraper changes.
