.PHONY: install fmt lint test

install:
uv sync --dev

fmt:
uv run ruff format .

lint:
uv run ruff check .

test:
uv run pytest
