# TopN System — Project Context

This file is the **single source of truth** for the TopN system architecture.
Other projects (topn-db, topn-worker) reference this file.

## System Overview

TopN is a multi-service system that monitors Polish real-estate listing sites (OLX, Otodom) and sends new listings to users via Telegram. Users configure what to monitor (URL, city, districts); the system scrapes, stores, and notifies.

## Services

### topn-telegram (this project)

| Attribute | Value |
|-----------|-------|
| **Role** | Telegram bot — user interface, admin panel, notifications |
| **Stack** | Python 3.12, aiogram 3, Redis, httpx, aiohttp, Pillow |
| **Dependency mgmt** | uv + pyproject.toml |
| **Talks to** | topn-db (HTTP REST), Redis (caching), Telegram API |
| **Entry point** | `main.py` → polling mode |
| **Key patterns** | Protocol-based interfaces, service/repository/client layers, FSM for conversations |

#### Layer structure
```
bot/           → Handlers, keyboards, FSM, responses (Telegram-specific)
services/      → MonitoringService, UrlValidator, Notifier (business logic)
repositories/  → MonitoringRepository (abstracts topn-db API)
clients/       → TopnDbClient (HTTP client for topn-db)
tools/         → url_parser, texts, datetime_utils
core/          → Config (pydantic-settings), DI container
```

### topn-db

| Attribute | Value |
|-----------|-------|
| **Role** | REST API + PostgreSQL database — central data store |
| **Stack** | Python 3.11, FastAPI, SQLAlchemy 2, Alembic, psycopg2 |
| **Dependency mgmt** | requirements.txt |
| **Talks to** | PostgreSQL |
| **Consumed by** | topn-telegram (HTTP), topn-worker (HTTP) |
| **Entry point** | `app.py` → uvicorn |
| **Key patterns** | Router/service layers, Pydantic schemas, Alembic migrations |
| **Location** | Sibling directory: `../topn-db/` |

#### Database schema (core tables)
- **monitoring_tasks** — User monitoring configurations (chat_id, URL, city, GraphQL config)
- **item_records** — Scraped listing items (URL, title, price, city, district, images)
- **cities** — Normalized city names
- **districts** — Districts per city
- **monitoring_task_districts** — Many-to-many: tasks ↔ allowed districts

#### Key API endpoints
- `GET/POST/DELETE /tasks/` — CRUD for monitoring tasks
- `GET /tasks/pending` — Tasks ready for scraping (worker uses this)
- `GET/POST /items/` — Item storage and retrieval
- `GET /items/to-send/{task_id}` — Items to notify user about
- `GET/POST /cities/`, `GET/POST /districts/` — Location management

### topn-worker

| Attribute | Value |
|-----------|-------|
| **Role** | Scraper/worker — fetches listings from OLX/Otodom, stores in DB |
| **Stack** | Python 3.12, httpx, BeautifulSoup4, Playwright, LangChain (Groq) |
| **Dependency mgmt** | uv + pyproject.toml |
| **Talks to** | topn-db (HTTP REST), OLX/Otodom (scraping), Groq LLM API |
| **Entry point** | `main.py` → infinite loop with sleep |
| **Key patterns** | Abstract BaseScraper with OLX/Otodom implementations, Playwright for GraphQL capture, LLM for description summarization |
| **Location** | Sibling directory: `../topn-worker/` |

#### Scraping flow
1. Fetch pending tasks from topn-db
2. Group tasks by source URL
3. For each URL: try GraphQL scraper → fall back to HTML scraper
4. Deduplicate against existing items in DB
5. Persist new items via topn-db API

## Data Flow

```
User (Telegram) → topn-telegram → topn-db (REST) → PostgreSQL
                                                    ↑
topn-worker (scraper loop) ─────→ topn-db (REST) ──┘
                                                    
topn-telegram (notifier loop) ← topn-db (items to send) ← PostgreSQL
```

## Deployment

- All services run as Docker containers
- Staging: `stage` branch → build + push
- Production: `main` branch → build + push
- Compose files in each project's `stg/` and `prod/` directories
- Shared infrastructure: PostgreSQL, Redis (defined in compose)

## Known Issues

See `SYSTEM-ISSUES-AUDIT.md` in this project root for a comprehensive severity-sorted audit across all three projects (43 issues total: 5 critical, 7 high, 16 medium, 15 low).

## Conventions

- topn-telegram and topn-worker: `uv` for dependency management, `pyproject.toml`
- topn-db: `requirements.txt` (to be aligned)
- All projects: pytest for testing, GitHub Actions for CI/CD
- topn-telegram: protocol-based interfaces, centralized responses in `bot/responses.py`
- topn-db: router → service → ORM pattern, Pydantic schemas for API contracts
- topn-worker: abstract base scraper pattern, scraper registry
