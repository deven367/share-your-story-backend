.PHONY: setup start test

setup:
	uv sync --extra dev --extra openai

start:
	uv run python server.py

test:
	uv run pytest tests/ -v
