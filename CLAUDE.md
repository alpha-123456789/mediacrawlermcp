# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MediaCrawler is a multi-platform social media data crawler supporting Xiaohongshu (XHS), Douyin, Kuaishou, Bilibili, Weibo, Tieba, and Zhihu. It uses Playwright for browser automation with login state preservation and CDP mode for anti-detection.

## Common Commands

```bash
# Install dependencies (requires uv)
uv sync

# Install browser driver
uv run playwright install

# Run crawler - keyword search
uv run main.py --platform xhs --lt qrcode --type search

# Run crawler - post details by ID
uv run main.py --platform xhs --lt qrcode --type detail

# Run crawler - creator homepage
uv run main.py --platform xhs --lt qrcode --type creator

# View all available options
uv run main.py --help

# Start WebUI (FastAPI)
uv run uvicorn api.main:app --port 8080 --reload

# Run tests
uv run pytest

# Run type checking
uv run mypy

# Run pre-commit hooks
uv run pre-commit run --all-files
```

## Architecture

### Crawler Factory Pattern
Entry point is `main.py` with `CrawlerFactory` that creates platform-specific crawlers via `CrawlerFactory.create_crawler(platform)`.

### Platform Modules
Each platform lives in `media_platform/{platform}/` with:
- `core.py` - Main crawler implementation
- `client.py` - API client with request handling
- `login.py` - Login logic (QR code, phone, cookies)
- `xhs_sign.py` / `playwright_sign.py` - Signature generation for API requests

### Abstract Base Classes
Defined in `base/base_crawler.py`:
- `AbstractCrawler` - Core crawler interface (start, search, launch_browser)
- `AbstractLogin` - Login interface (begin, login_by_qrcode, login_by_mobile, login_by_cookies)
- `AbstractStore` - Data storage interface (store_content, store_comment, store_creator)
- `AbstractApiClient` - HTTP client interface (request, update_cookies)

### Storage Backends
In `store/` and `database/`, supporting: CSV, JSON, JSONL, SQLite, Excel, MySQL, PostgreSQL, MongoDB. Configured via `config/base_config.SAVE_DATA_OPTION`.

### Configuration
- `config/base_config.py` - Main settings (platform, keywords, login type, CDP mode, data storage)
- `config/*_config.py` - Platform-specific configurations
- CLI arguments in `cmd_arg/arg.py` using typer

### Data Models
SQLAlchemy models in `database/models.py` and Pydantic models in `model/m_*.py` for each platform.

## Key Patterns

1. CDP Mode: Uses Chrome DevTools Protocol for better anti-detection (`config.ENABLE_CDP_MODE`)
2. Login State Caching: Browser context persisted in `browser_data/` directory
3. Async/Await: Core crawler logic uses asyncio throughout
4. Pre-commit: File header copyright checker in `tools/file_header_manager.py`

## File Header Requirement

All Python files must include the copyright header. Use `tools/file_header_manager.py` to check/add headers.