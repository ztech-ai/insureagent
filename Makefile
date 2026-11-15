.PHONY: setup test lint api contracts prototype
setup:
	uv sync --frozen
test:
	uv run pytest
lint:
	uv run ruff check .
	uv run ruff format --check .
api:
	uv run uvicorn insureagent_api.main:app --reload --host 127.0.0.1
contracts:
	uv run python scripts/export_contracts.py
prototype:
	python -m http.server 8080 --bind 127.0.0.1 --directory design/prototype
