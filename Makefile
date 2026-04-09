PYTHON ?= python
UVICORN ?= uvicorn

install:
	$(PYTHON) -m pip install -e .[dev]

ingest:
	$(PYTHON) scripts/ingest_all.py

index:
	$(PYTHON) scripts/build_rag_index.py

seed-rate:
	$(PYTHON) scripts/seed_exchange_rate.py --rate 1380

demo:
	$(UVICORN) camp_casey_app.main:app --reload --host 0.0.0.0 --port 8000

backend:
	$(UVICORN) camp_casey_app.main:app --host 0.0.0.0 --port 8000

test:
	pytest

build:
	docker build -t camp-casey-app .
