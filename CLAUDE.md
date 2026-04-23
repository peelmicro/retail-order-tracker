# CLAUDE.md — Retail Order Tracker

## Project Overview

AI-augmented EDI operations platform with human-in-the-loop review. Retailers (Carrefour, Leroy Merlin, El Corte Inglés, ...) submit purchase orders in multiple formats (JSON, XML/Facturae, CSV, EDIFACT D.96A, PDF). The system parses them, runs an AI Analyst Agent to suggest an action (approve / request clarification / escalate), and presents suggestions to operators for review. Every operator decision becomes a labelled example for Phoenix-based evaluation.

## Tech Stack

- **Backend:** Python 3.13, FastAPI, SQLAlchemy 2.x (async), Alembic, Pydantic v2, PostgreSQL 16
- **AI:** LangChain, Anthropic Claude (`claude-sonnet-4-6` for Parser + Analyst), Arize Phoenix (self-hosted OTLP observability)
- **Storage:** MinIO (S3-compatible) for original uploaded files
- **Frontend:** Vue 3 (Composition API), Vite, Pinia, TanStack Query for Vue, Tailwind CSS v4
- **Orchestration:** n8n (pure orchestrator — never calls Claude directly)
- **Infrastructure:** Docker Compose (Postgres, MinIO, Phoenix, n8n, API, Web — 7 containers total)
- **Testing:** pytest + Testcontainers (API), Vitest (Web)
- **Auth:** JWT (PyJWT, in-memory user store — demo scope)

## Project Structure

```
apps/api/           # FastAPI backend (Python 3.13, clean architecture)
apps/web/           # Vue 3 frontend
samples/orders/     # 5 sample order files (one per format)
n8n/workflows/      # 4 exported n8n workflow JSON files
scripts/            # Seed and helper scripts
docker-compose.yml          # Full 7-container stack
docker-compose.infra.yml    # Infra-only (Postgres, MinIO, Phoenix, n8n) for local dev
```

### Backend Layout (`apps/api/src/`)

Clean architecture — domain has zero external dependencies:

- `domain/` — Entities, value objects, business rules (pure Python)
- `application/` — Use cases, agent orchestrators, abstract ports
- `infrastructure/` — Adapters implementing ports
  - `parsers/` — 5 pluggable parsers (JSON, XML, CSV, EDIFACT, PDF)
  - `agents/` — Parser Agent + Analyst Agent (LangChain)
  - `storage/` — MinIO adapter
  - `persistence/` — SQLAlchemy + Alembic
  - `observability/` — Phoenix OTLP exporter
- `api/` — FastAPI routes, WebSocket handlers, JWT middleware, Pydantic schemas
- `main.py` — FastAPI app entry point

## AI Agents

Two distinct agents, each with its own prompt, Phoenix dataset, and evaluator:

| Agent | Role | Input | Output |
|-------|------|-------|--------|
| **Parser Agent** | Extract structured data from PDFs | PDF bytes (multimodal) | `OrderDTO` with `parsing_confidence` |
| **Analyst Agent** | Decide action on an order | `OrderDTO` + last 50 orders for retailer–supplier pair | `{action, confidence, reasoning, anomalies_detected[]}` via tool calling |

Parser Agent runs only for PDF uploads. Analyst Agent runs for every order regardless of format. Both export OpenTelemetry traces to Phoenix.

## Document Parsing

Five parsers behind a common `OrderParser` protocol (ports & adapters). Dispatcher picks by file extension + MIME type.

| Format | Parser | Library |
|--------|--------|---------|
| `.json` | `JsonOrderParser` | stdlib `json` |
| `.xml` | `XmlOrderParser` | `lxml` + XPath (Facturae 3.2.2) |
| `.csv` | `CsvOrderParser` | `pandas` |
| `.edi` | `EdifactOrderParser` | `pydifact` (D.96A ORDERS) |
| `.pdf` | `PdfOrderParser` | Delegates to Parser Agent |

All parsers return a normalised `OrderDTO` (Pydantic v2). Original file bytes always stored in MinIO under `orders/{order_id}/{filename}`.

## Conventions

### General

- All monetary amounts stored in **minor units** (integer cents) — never floats
- UUIDs for all primary keys
- Human-readable codes with format `PREFIX-YYYY-MM-NNNNNN` (e.g. `ORD-2026-04-000012`)
- Soft deletes via a nullable `disabled_at` datetime (not hard deletes)
- All tables include `created_at` and `updated_at` timestamps
- **DB columns are snake_case**; API JSON is camelCase (via Pydantic `alias_generator=to_camel`)
- `Europe/Madrid` timezone for dates displayed to operators

### Python / Backend

- Use **async** SQLAlchemy sessions and FastAPI async endpoints
- Pydantic v2 for all request/response validation
- Snake_case for Python code, camelCase for JSON API responses (Pydantic `alias_generator`)
- One router per domain, mounted in `main.py`
- `.http` files in `apps/api/http/` for VS Code REST Client testing
- `uv` for dependency management; pinned `.venv` inside `apps/api/`
- Lint with `ruff`; format with `ruff format`
- Alembic migrations committed to `apps/api/alembic/versions/` — never use `create_all` in production paths

### TypeScript / Frontend

- Strict TypeScript — no `any`
- Composition API only (`<script setup lang="ts">`)
- Pinia for client state, TanStack Query for Vue for server state
- Tailwind CSS v4 for styling
- WebSocket via a `useWebSocket` composable

### Database

- PostgreSQL 16 with `asyncpg` driver
- 9 tables: `currencies`, `formats`, `documents`, `retailers`, `suppliers`, `orders`, `order_line_items`, `agent_suggestions`, `feedbacks`
- Schema created and evolved exclusively via Alembic migrations
- Enums as PostgreSQL enums (`orderStatus`, `agentAction`, `operatorDecision`)

### AI / Agents

- All AI invocations go through the FastAPI backend — n8n **never** calls Claude directly
- Every agent run exports an OTLP trace to Phoenix with custom attributes (`order_id`, `agent_type`, `confidence`)
- Every operator decision on an agent suggestion is persisted as a `feedback` row and eligible for export as a Phoenix labelled example

### Testing

- `pytest` + Testcontainers for integration tests (real Postgres, real n8n)
- One parser test per format against the sample file in `samples/orders/`
- `vitest` for Vue component tests with a fake WebSocket

### Docker

- `docker compose up` starts the full 7-container stack
- `docker compose -f docker-compose.infra.yml up` starts just the 4 infra containers (for local dev with API + Web run on host)
- n8n workflows auto-imported from `n8n/workflows/` on container startup
- MinIO bucket created by a one-shot `minio-init` container

## Collaboration Rules

- **Do not start coding when the user asks a question.** When the user asks "what do you think?" or discusses an approach, reply with analysis and wait for confirmation.
- **Each implementation phase is committed by the user.** Suggest a commit message; the user runs the commit.
- **Explain commands before running them.** The user executes commands from the terminal to understand what gets created.

## Key Design Decisions

- **Two agents (Parser + Analyst) over one** — different failure modes, different evaluation datasets, different prompts
- **Pluggable parsers over single AI parser** — deterministic formats (JSON/XML/CSV/EDIFACT) are faster, cheaper, more reliable than AI; Claude only used where structure is missing (PDF)
- **Phoenix over LangSmith** — open-source, self-hosted, no data leaves the environment
- **MinIO over local filesystem** — S3-compatible API means the same code works in production (AWS S3, GCS, Azure Blob)
- **Tool calling over linear chain** (Analyst Agent) — dynamically picks among 3 actions
- **n8n orchestration over inline orchestration** — workflow logic decoupled from the API, reviewers can tweak in the UI
- **Vue 3 over React** — portfolio diversification (other assessments use React / Angular)
- **Alembic over `create_all`** — every schema change is versioned and reviewable
- **JWT simple over Keycloak/Auth0** — assessment scope; production would use a managed IdP

## Commands

```bash
# Infra only (Postgres, MinIO, Phoenix, n8n)
npm run dc:up:infra

# Backend
cd apps/api && uv venv && uv pip install -r requirements.txt
npm run api
npm run api:test

# Frontend
cd apps/web && npm install
npm run web

# Full stack
npm run dc:up
```
