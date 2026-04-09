# (1) Architecture summary

## Why this structure fits demo-first + deploy-ready

The implementation uses one shared Python codebase for ingest, normalized domain models, deterministic services, chat orchestration, API endpoints, and the browser UI. Local demo mode and deployment mode differ only at the host boundary: both call the same domain/service/tool layer. That preserves demo-to-deploy continuity and avoids throwaway demo code.

## Why a Lang-family-centered structure is still the practical choice

The primary app host is FastAPI, while the chat orchestration layer is implemented as an internal LangGraph-compatible workflow with a no-dependency fallback. LangServe is exposed as an optional runnable wrapper for playground/demo use when the dependency is installed. This keeps LangGraph/LangServe in the architecture, but does not force the entire product to depend on optional packages just to run deterministic APIs or the front-end.

## Why OpenAI-only is easier to maintain

All AI integration points are routed through one provider wrapper (`OpenAIService`): embeddings for the optional index build and answer composition for grounded chat responses. No second embedding vendor, no separate reranker, and no external vector DB were introduced in the base design.

## Why exchange rate is manual-first but auto-ready

The current production-safe behavior is a local manual exchange-rate source of truth with validation and persistence. A placeholder `FutureAutoExchangeRateProvider` is already part of the provider contract, so future automation can be attached without changing UI contracts or deterministic conversion services.

## Why the front-end is HCI-first

The UI is not a thin shell. The browser app was designed around cognitive clarity and recovery: explicit hover/focus/active/loading/empty/error states, short helper text, semantic color tokens, tooltips for ambiguous status concepts, sticky navigation, mobile-sized targets, and reversible exchange-rate editing. Every primary section was implemented with specific interaction states instead of cosmetic-only styling.

# (2) System architecture diagram (text)

```text
Raw files (delivery.json, holiday.json, Hovey-Bus-TimeTable.xlsx, Bosan-Train-TimeTable.xlsx)
    -> ingest layer (JSON/XLSX parsers)
    -> normalized domain JSON (stores, holidays, bus, trains)
    -> deterministic services (day type, store status, bus/train next departure, exchange rate, search)
    -> optional RAG chunks + optional OpenAI embedding index
    -> FastAPI host
         -> REST endpoints for deterministic UI flows
         -> optional LangServe wrapper (/langserve/chat)
         -> LangGraph-compatible chat orchestrator with fallback
    -> HCI-first web UI (Jinja + vanilla JS + CSS)
         -> home / transit / delivery / holidays / exchange / chat
```

# (3) File tree

```text
camp-casey-app/
├─ camp_casey_app/
│  ├─ ai/
│  │  └─ openai_client.py
│  ├─ api/
│  │  ├─ app.py
│  │  ├─ langserve_routes.py
│  │  ├─ routes.py
│  │  └─ web.py
│  ├─ chat/
│  │  ├─ composer.py
│  │  ├─ intent_router.py
│  │  ├─ langgraph_workflow.py
│  │  └─ schemas.py
│  ├─ domain/
│  │  └─ models.py
│  ├─ ingest/
│  │  ├─ bus_parser.py
│  │  ├─ common.py
│  │  ├─ delivery_parser.py
│  │  ├─ holiday_parser.py
│  │  ├─ normalize.py
│  │  ├─ rag.py
│  │  └─ train_parser.py
│  ├─ repositories/
│  │  ├─ exchange_rate_store.py
│  │  ├─ normalized_repository.py
│  │  └─ rag_repository.py
│  ├─ services/
│  │  ├─ day_type.py
│  │  ├─ exchange_rate.py
│  │  ├─ holidays.py
│  │  ├─ search.py
│  │  ├─ stores.py
│  │  └─ transport.py
│  ├─ utils/
│  │  ├─ money.py
│  │  ├─ text.py
│  │  └─ time.py
│  ├─ web/
│  │  ├─ static/
│  │  │  ├─ app.css
│  │  │  ├─ app.js
│  │  │  └─ i18n/
│  │  │     ├─ en.json
│  │  │     └─ ko.json
│  │  └─ templates/
│  │     ├─ base.html
│  │     └─ index.html
│  ├─ bootstrap.py
│  ├─ config.py
│  ├─ container.py
│  └─ main.py
├─ data/
│  ├─ raw/
│  ├─ normalized/
│  ├─ rag/
│  └─ state/
├─ scripts/
│  ├─ build_rag_index.py
│  ├─ ingest_all.py
│  └─ seed_exchange_rate.py
├─ tests/
│  ├─ conftest.py
│  ├─ test_api_smoke.py
│  ├─ test_chat_router.py
│  ├─ test_day_type_service.py
│  ├─ test_exchange_rate.py
│  ├─ test_ingest.py
│  ├─ test_rag_repository.py
│  ├─ test_store_service.py
│  ├─ test_transport_bus.py
│  ├─ test_transport_train.py
│  └─ test_ui_static.py
├─ .env.example
├─ Dockerfile
├─ Makefile
├─ README.md
├─ DELIVERY_REPORT.md
├─ pyproject.toml
└─ render.yaml
```

# (4) Environment and deployment files

Included in the repo root:

- `pyproject.toml`
- `Dockerfile`
- `render.yaml`
- `.env.example`
- `README.md`
- `Makefile`

Notable deployment detail: `DATA_ROOT` lets deployed instances use a mounted writable volume for normalized data, RAG files, and the exchange-rate state file, while still seeding raw source files from the bundled repo on first boot.

# (5) Actual runnable code

All core code is in the repository under `camp_casey_app/` and is complete rather than pseudocode. The implementation includes:

- JSON/XLSX parsers for the uploaded files
- normalized domain schemas
- deterministic services for day type, open-now, bus/train next departure, search, and currency conversion
- optional LangGraph-compatible chat orchestration with a no-dependency fallback
- optional LangServe wrapper
- OpenAI provider wrapper
- local Jinja + vanilla JS UI with detailed interaction states
- API endpoints for deterministic UI flows and chat
- tests

# (6) Data ingest / indexing scripts

Included scripts:

- `scripts/ingest_all.py`
  - raw files -> normalized JSON
  - normalized JSON -> RAG chunks
- `scripts/build_rag_index.py`
  - RAG chunks -> optional OpenAI embedding index
  - when no OpenAI key is present, writes a lexical-only placeholder index
- `scripts/seed_exchange_rate.py`
  - initialize or update the manual exchange-rate seed

All scripts are rerunnable.

# (7) Run instructions

## Install

```bash
python -m pip install -e .[dev]
```

## Ingest

```bash
python scripts/ingest_all.py
```

## Embed / index

```bash
python scripts/build_rag_index.py
```

## Run local demo

```bash
uvicorn camp_casey_app.main:app --reload
```

## Run tests

```bash
pytest
```

## Build container

```bash
docker build -t camp-casey-app .
```

# (8) Deployment guide

## Lang-family-only-leaning path

Use the FastAPI app as the primary production host, keep LangGraph-compatible orchestration inside the chat layer, and enable the optional LangServe runnable wrapper if `langserve` and `langchain-core` are installed. This gives a deterministic API surface and a browser UI without depending on any external DB or SaaS backend.

## When Render should be added

Add Render when you want simple internet hosting plus a mounted disk for the persisted exchange-rate state. The included `render.yaml` already mounts a writable disk and sets `DATA_ROOT` to `/var/data/camp-casey`.

## Required environment variables

- `OPENAI_API_KEY` for embeddings/LLM composition
- `DATA_ROOT` for a writable persisted data path in deployment
- `APP_TIMEZONE`, `DEFAULT_LOCALE`, `DEFAULT_USD_TO_KRW` as needed

## Local demo -> deployed app transition

1. Keep the same repo.
2. Keep the same raw source files or mounted data volume.
3. Run `scripts/ingest_all.py` once locally or let bootstrap create normalized outputs on first boot.
4. Set `OPENAI_API_KEY` only when embeddings / LLM composition are desired.
5. Deploy the exact same FastAPI entrypoint (`camp_casey_app.main:app`).

# (9) UI / HCI explanation

## Home

- A single global search/question bar is placed at the top because the user’s first task is usually not category selection but intent expression.
- Quick suggestion chips reduce input friction for the most common workflows.
- Summary cards are keyboard-focusable and clickable to jump to the relevant section. This reduces navigation ambiguity on first use.
- The top-right locale/currency segmented controls give immediate feedback with pressed state and persistence via localStorage.

## Transit

- Bus and train are separated with keyboard-accessible tabs because the mental model and filters differ.
- “Next departure” is visually dominant, while full schedule is a secondary action.
- Midnight rollover is shown with `+1d` instead of hiding the day transition in small print.
- The bus stop favorite action uses a small reversible control instead of a hidden settings page, reducing recall burden.

## Delivery

- Store cards surface open-now state, minimum order, delivery fee, and phone before menu detail because those are the most action-driving facts.
- Clicking a store opens a dialog with progressive disclosure for menu detail, so scanning the list stays fast.
- Empty states explain the next recovery action (“relax filters”, “reduce keywords”) instead of leaving a blank result pane.
- Alternate-board sections are explicitly marked so ambiguous pricing is visible instead of silently merged away.

## Holidays

- Status badges distinguish official / pattern / likely / unconfirmed with both color and text.
- The note box stays above the list because users otherwise misread “confirmed_pattern” as “official”.
- Paired-with information is shown inline to make four-day logic legible without opening a detail screen.

## Exchange

- The current applied rate, updated time, and manual/auto status are shown before the form because the user must understand the active source of truth before editing it.
- Validation messages are restorative rather than punitive.
- The quick converter renders immediately from the same rate state that powers UI price labels, which keeps mental models consistent.
- The currency-mode toggle is global so list/detail/chat all use the same display rule.

## Chat

- Chat bubbles separate the answer from the source basis so the user can distinguish explanation from evidence.
- Deterministic tool results are invoked first, which keeps countdowns, open-now decisions, and currency calculations trustworthy.
- Source basis rows are visible by default; they are not hidden behind an extra click because trust is a primary requirement.

## Shared interaction design details

- Buttons/cards/tabs/segmented controls all implement hover, focus-visible, active, disabled, and loading states.
- Tooltips are short and used for ambiguous domain terms, but no essential information is tooltip-only.
- Skeletons, empty states, toasts, badges, and helper text are treated as system-level components rather than ad hoc one-offs.
- The CSS token set standardizes spacing, radius, borders, shadows, semantic colors, and animation timing so state changes feel consistent rather than decorative.
