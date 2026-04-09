# Camp Casey App

Camp Casey / Hovey / Bosan 생활 도우미 웹앱 + 챗봇 시스템이다. 핵심 계산은 deterministic service가 처리하고, 챗봇은 그 결과와 업로드 데이터 기반 RAG를 정리하는 보조 계층으로 동작한다.

## Stack

- Python + FastAPI
- Optional LangGraph orchestration and optional LangServe wrapper
- OpenAI-only AI integration
- Jinja templates + vanilla JS + CSS for a mobile-first HCI-oriented UI
- Local JSON/XLSX ingest with normalized JSON outputs

## Repo layout

- `camp_casey_app/` application package
- `data/raw/` uploaded source files bundled for local demo
- `data/normalized/` normalized JSON outputs
- `data/rag/` RAG chunk store and embedding index placeholder
- `data/state/` exchange-rate state file
- `scripts/` ingest / embedding / seed utilities
- `tests/` deterministic/service/API/UI smoke tests

## Quick start

```bash
python -m pip install -e .[dev]
python scripts/ingest_all.py
python scripts/build_rag_index.py
uvicorn camp_casey_app.main:app --reload
```

Open `http://127.0.0.1:8000`.

## Make targets

```bash
make install
make ingest
make index
make demo
make test
make build
```

## Environment

Copy `.env.example` to `.env` and set `OPENAI_API_KEY` when you want embedding creation or LLM answer composition.

`DATA_ROOT` is optional but useful in deployed environments. When set, normalized data, RAG files, and exchange-rate state are stored on that writable path. The app seeds raw source files from the bundled `data/raw/` directory on first boot.

## LangGraph / LangServe note

The repo keeps LangGraph as the chat orchestration layer when the dependency is installed, but it still runs without it by falling back to the same deterministic service flow. LangServe is exposed as an optional runnable wrapper at `/langserve/chat` when the dependency is installed. The main production host remains FastAPI so deterministic API endpoints and the HCI-first web UI stay available even when LangServe is disabled.

## Exchange-rate behavior

- Current build: manual exchange rate only
- Persistence: local JSON state file (`data/state/exchange_rate.json` or `${DATA_ROOT}/state/exchange_rate.json`)
- Future-ready placeholder: `FutureAutoExchangeRateProvider`

## Tests

```bash
pytest
```

The test suite covers holiday/day-type resolution, store open-now logic, bus/train next-departure logic, midnight rollover, exchange-rate validation and conversion, RAG retrieval smoke tests, intent routing, placeholder providers, API smoke tests, and static HCI affordance presence.
