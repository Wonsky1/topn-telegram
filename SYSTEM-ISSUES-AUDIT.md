# TopN System Issues Audit

Comprehensive audit across **topn-telegram**, **topn-db**, and **topn-worker**.
Last updated: 2026-02-28.

---

## System Overview

| Project | Role | Stack | Talks to |
|---------|------|-------|----------|
| **topn-telegram** | Telegram bot UI | aiogram, Redis, httpx | topn-db (HTTP) |
| **topn-db** | REST API + PostgreSQL | FastAPI, SQLAlchemy, Alembic | PostgreSQL |
| **topn-worker** | Scraper/worker loop | httpx, Playwright, BeautifulSoup, LangChain | topn-db (HTTP), external sites |

---

## CRITICAL — Security / Data Loss

### SEC-2: Secrets baked into Docker images via build args
**Severity**: Medium (downgraded from Critical)
**Projects**: all three
- Dockerfiles use `ARG`/`ENV` to embed `BOT_TOKEN`, `GROQ_API_KEY`, `DATABASE_URL` etc. into image layers.
- CI workflows pass secrets as `build-args`.

**Context**: Registry is private (requires GitHub token to pull). Server access is controlled. Practical risk is low in current setup.
**Residual risk**: Anyone with SSH access to the server can `docker inspect` or `docker history --no-trunc` to read build args in plain text. If team/access grows, secrets travel with the image.
**Fix** (low effort, ~10 min per project):
1. Remove all `ARG`/`ENV` secret lines from Dockerfiles (build still succeeds — those lines don't affect the build process, only set env vars).
2. Pass secrets at runtime via docker-compose instead:
   ```yaml
   services:
     telegram:
       image: topn-telegram:latest
       environment:
         - BOT_TOKEN=${BOT_TOKEN}
         - ADMIN_IDS=${ADMIN_IDS}
         - TOPN_DB_BASE_URL=http://db:8000
   ```
3. On the server, provide secrets via a `.env` file next to docker-compose or as shell environment variables.
4. Update CI workflows to remove `build-args` for secrets — they're no longer needed at build time.
5. Result: image is secret-free. Secrets only exist on the server where compose runs.

### SEC-3: CORS wildcard with credentials enabled
**Project**: topn-db (`app.py:49-55`)
```python
allow_origins=["*"]
allow_credentials=True
```
**Impact**: Allows any origin to make credentialed cross-origin requests. Combined with no auth (SEC-4), the API is fully open.
**Fix**: Restrict `allow_origins` to known frontends, or remove `allow_credentials`.

### SEC-4: No authentication or authorization on API
**Project**: topn-db
**Impact**: Any network client can create, modify, or delete tasks, items, and user data. In production, this means anyone who discovers the endpoint has full access.
**Fix**: Add API key auth at minimum. Consider JWT/OAuth for multi-tenant scenarios.

### SEC-5: Redis with no authentication
**Project**: topn-telegram (docker-compose uses `redis:7-alpine` with no password)
**Impact**: Any container/process on the network can read/write Redis data.
**Fix**: Configure `requirepass` in Redis and set `REDIS_PASSWORD` in config.

---

## HIGH — Bugs / Reliability

### ~~BUG-1: `update_last_got_item` updates ALL tasks instead of the one that received items~~ — FIXED
**Project**: topn-telegram (`repositories/monitoring.py:184-192`)
- `notifier.py:103` sends items for a specific task, then calls `update_last_got_item(task.chat_id)`.
- The repository lists ALL tasks for that `chat_id` and calls `update_last_got_item_timestamp` on every one.
- If a user has 3 monitoring tasks and items arrive for task #1, all 3 tasks get their `last_got_item` bumped. Tasks #2 and #3 will miss items because their timestamp moved forward without them receiving anything.

**Note**: `last_updated` (last checked) is NOT affected — it correctly passes the specific task ID. The topn-db API endpoint (`POST /{task_id}/update-last-got-item`) also correctly works by task_id. The bug is only in topn-telegram's repository layer.
**Note**: topn-db has an unused `TaskService.update_last_got_item(db, chat_id)` method that only updates the FIRST task per chat — this is dead code (not exposed via API) but should be cleaned up.
**Impact**: Tasks get incorrect `last_got_item` timestamps, causing missed items for users with multiple monitoring tasks.
**Fix**: Change `notifier.py` to call `update_last_got_item(task.id)` instead of `update_last_got_item(task.chat_id)`. Update the repository to call `update_last_got_item_timestamp` for that single task only. Remove the dead `update_last_got_item(db, chat_id)` method from topn-db.

### BUG-2: Fragile HTML parsing in OLX scraper
**Project**: topn-worker (`tools/scraping/olx.py:63-79`)
- `div.find(...)` can return `None`, but `.get_text()` is called without null-check.
- `location_date.split("Dzisiaj o ")` throws `ValueError` when text format changes.
- `a_tag["href"]` throws `KeyError`/`AttributeError` when structure changes.

**Impact**: Any OLX HTML layout change crashes the scraper for all tasks.
**Fix**: Add defensive null-checks; wrap parsing in try/except per item; log and skip malformed entries.

### BUG-3: Python version mismatch in Docker
**Project**: topn-worker
- `Dockerfile` uses `python:3.11-slim-bookworm`.
- `pyproject.toml` requires `>=3.12,<3.13`.

**Impact**: The built image may fail or behave differently than dev/test environments.
**Fix**: Align Dockerfile base image to `python:3.12-slim-bookworm`.

### BUG-4: Config field references unresolved default
**Project**: topn-telegram (`core/config.py:27`)
```python
IMAGE_CACHE_TTL_DAYS: int = DB_REMOVE_OLD_ITEMS_DATA_N_DAYS + 1
```
`DB_REMOVE_OLD_ITEMS_DATA_N_DAYS` may not be resolved at class definition time.
**Impact**: Potential `NameError` at startup.
**Fix**: Use a Pydantic validator/computed field or hardcode the default.

### BUG-5: Config defaults contradict descriptions
**Project**: topn-db (`core/config.py:27-33`)
- `DEFAULT_SENDING_FREQUENCY_MINUTES`: default=1, description says "default: 60".
- `DEFAULT_LAST_MINUTES_GETTING`: default=60, description says "default: 30".

**Impact**: Developers/ops will configure wrong values based on misleading docs.
**Fix**: Align defaults and descriptions.

### BUG-6: Leaky abstractions — private member access
**Project**: topn-telegram
- `bot/handlers/monitoring.py:82` — `monitoring_service._repo.has_url(...)`.
- `bot/handlers/admin.py:61,69,79,86,91,142,186` — `repo._client.get_all_tasks()` etc.

**Impact**: Tight coupling to internals; any refactor of service/repository breaks handlers. Violates encapsulation.
**Fix**: Expose needed operations as public methods on the service/repository.

### DEP-1: aiohttp 3.11.0 has known CVEs
**Project**: topn-telegram
- CVE-2024-52303, CVE-2024-52304, plus 2025 advisories (zip bomb, DoS, request smuggling).

**Impact**: Exploitable vulnerabilities in a production dependency.
**Fix**: Upgrade to aiohttp >= 3.13.3.

---

## MEDIUM — Code Quality / Performance

### PERF-1: Redis `KEYS` command used in admin
**Project**: topn-telegram (`bot/handlers/admin.py:91`)
```python
photo_keys = await redis_client.keys("photo:*")
```
**Impact**: `KEYS` is O(N), blocks Redis for the entire keyspace scan.
**Fix**: Use `SCAN` iterator instead.

### PERF-2: N+1 queries on task loading
**Project**: topn-db
- `get_all_tasks`, `get_tasks_by_chat_id`, `get_pending_tasks` don't eager-load `city` or `allowed_districts`.

**Impact**: Each task triggers additional queries when relationships are accessed.
**Fix**: Add `joinedload`/`selectinload` options on relationship queries.

### PERF-3: Bulk delete loads all rows into memory
**Project**: topn-db (`api/services/item_service.py:283-291`)
```python
items_to_delete = db.query(ItemRecord).filter(...).all()
for item in items_to_delete:
    db.delete(item)
```
**Impact**: Memory spike and slow execution for large datasets.
**Fix**: Use `db.query(ItemRecord).filter(...).delete()` for bulk operations.

### PERF-4: No batch item creation
**Project**: topn-worker
- Each scraped item triggers a separate HTTP `POST /items` call.

**Impact**: High latency and load when many items are found.
**Fix**: Add a batch endpoint in topn-db and use it from the worker.

### PERF-5: Blocking `psutil.cpu_percent(interval=1)` in admin
**Project**: topn-telegram (`bot/handlers/admin.py:74`)
**Impact**: Blocks the event loop for 1 second on every system status check.
**Fix**: Run in `asyncio.to_thread()`.

### CODE-1: Duplicated district filtering logic
**Project**: topn-telegram
- Same "unknown" filter appears in `keyboards_inline.py:171-172`, `handlers/districts.py:72-73,111-112`, `handlers/monitoring.py:106-110`.

**Fix**: Extract to a shared utility function.

### CODE-2: Duplicated MarkdownV2 escaping
**Project**: topn-telegram
- Long escaping logic in `admin.py:214-276`; separate `_escape_markdown_v2()` in `services/notifier.py:269-278`.

**Fix**: Single shared utility function.

### CODE-3: Direct ORM access bypassing service layer
**Project**: topn-db (`api/routers/items.py:95-96`)
```python
item = db.query(ItemRecord).filter(ItemRecord.id == item_id).first()
```
**Fix**: Route through `ItemService.get_item_by_id()`.

### CODE-4: Bare `except` swallowing errors
**Project**: topn-telegram (`bot/handlers/admin.py:210-211`)
```python
except:
    pass
```
**Fix**: Catch specific exceptions; at minimum log the error.

### CODE-5: Overly broad `except Exception` throughout
**Projects**: topn-telegram (multiple), topn-worker (`main.py:31-33`)
- No distinction between transient (network timeout) and fatal (config error) exceptions.

**Fix**: Differentiate exception types; add structured retry for transient failures.

### CODE-6: Redundant URL validation
**Project**: topn-telegram (`bot/handlers/monitoring.py:71-78`)
- `is_supported()` called twice (before and after `normalize()`); second check is redundant.

### CODE-7: Duplicated HTTP headers in scrapers
**Project**: topn-worker
- `BaseScraper.HEADERS` and `OLXScraper.HEADERS` are near-identical.

**Fix**: OLX should inherit and override only what differs.

### DEP-2: Unused `psycopg2-binary`
**Projects**: topn-telegram, topn-worker
- Neither project connects to PostgreSQL directly (both use HTTP to topn-db).

**Fix**: Remove from dependencies.

### DEP-3: Unpinned dependencies
**Project**: topn-db (`requirements.txt`) — `httpx` and `unidecode` have no version pins.
**Fix**: Pin all dependency versions.

### DEP-4: Inconsistent dependency management
**Cross-project**:
- topn-telegram and topn-worker use `uv` + `pyproject.toml`.
- topn-db uses `requirements.txt`.

**Fix**: Standardize on one approach across all projects.

### CFG-1: Coverage thresholds misaligned
**Projects**: topn-db (`.coveragerc` = 80, `test.yaml` = 60), topn-worker (same mismatch)
**Fix**: Align CLI and config values.

---

## LOW — Documentation / Minor

### DOC-1: Minimal or missing READMEs
**Project**: topn-worker — README is a single line.
**Fix**: Add purpose, architecture, env vars, local run instructions, Docker usage.

### DOC-2: README env vars outdated
**Project**: topn-db — README references `OLX_*` prefixed vars; code uses unprefixed names.
**Fix**: Align documentation with actual config.

### DOC-3: Missing `.env.example` files
**Projects**: topn-telegram, topn-worker
**Fix**: Add `.env.example` with all required/optional vars and safe placeholder values.

### DOC-4: Referenced docs don't exist
**Project**: topn-telegram — README links to `IMPLEMENTATION_SUMMARY.md` and `ADMIN_PANEL_README.md` which are missing.
**Fix**: Create the referenced documents or remove the dead links.

### MISC-1: Dead code `if False` block
**Project**: topn-db (`app.py:15-17`)
```python
if False:
    handlers.append(file_handler)
```
**Fix**: Remove dead code.

### MISC-2: Hardcoded greeting and placeholder image
**Project**: topn-telegram
- `main.py:86` — `"Hello Yana, this is a bot for you <3"`
- `services/notifier.py:78-79` — hardcoded Bing image URL as placeholder.

**Fix**: Move to config or responses module.

### MISC-3: No graceful shutdown handler
**Project**: topn-worker
- `asyncio.run(main())` does not handle SIGTERM/SIGINT explicitly.
- Docker/K8s sends SIGTERM on stop; the process may be killed mid-operation.

**Fix**: Add signal handler for clean shutdown.

### MISC-4: No health endpoints
**Projects**: all three
- No service exposes a `/health` or `/ready` endpoint.

**Fix**: Add health endpoints for container orchestration and monitoring.

### MISC-5: Test directory naming inconsistency
**Project**: topn-telegram — `tests/service/` vs source `services/`.

### MISC-6: No shared API contract between clients and server
**Cross-project**: topn-telegram and topn-worker both implement HTTP clients for topn-db independently with duplicated logic.
**Fix**: Consider a shared SDK/package, or at minimum shared Pydantic schemas.

### MISC-7: `get_db` return type annotation incorrect
**Project**: topn-db (`core/database.py:39`)
- Annotated as `-> Session` but is a generator.

**Fix**: Annotate as `Generator[Session, None, None]`.

### MISC-8: `load_dotenv("dev.env")` references non-existent file
**Project**: topn-worker (`core/config.py:13`)
**Fix**: Guard with existence check or remove.

---

## Cross-Project Systemic Issues

| Issue | Description |
|-------|-------------|
| **No centralized logging/monitoring** | Each service logs independently; no aggregation or alerting. |
| **No shared API contract** | Two clients (telegram, worker) independently implement HTTP clients for topn-db with no shared schema. |
| **Inconsistent tooling** | uv vs pip, pyproject.toml vs requirements.txt, different Python versions. |
| **No API versioning** | topn-db has no API version prefix; breaking changes will affect all consumers simultaneously. |
| **No rate limiting** | topn-db API has no rate limiting; a misbehaving client can overload the database. |
| **No observability** | No metrics, tracing, or structured logging across services. |
| **No integration tests** | Each project tests in isolation; no end-to-end test validates the full pipeline. |

---

## Issue Count Summary

| Severity | Count |
|----------|-------|
| Critical | 3 |
| High | 7 |
| Medium | 17 |
| Low | 15 |
| False positive | 1 |
| **Total** | **43 (42 active)** |
