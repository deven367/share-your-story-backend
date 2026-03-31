.PHONY: setup-backend setup-frontend setup start-backend start-frontend test-backend

setup-backend:
	cd backend && uv sync --extra dev --extra openai

setup-frontend:
	cd frontend && npm install

setup: setup-backend setup-frontend

start-backend:
	cd backend && uv run python server.py

start-backend-prod:
	cd backend && uv run gunicorn server:app --bind 0.0.0.0:5050 --workers 4 --timeout 120

start-frontend:
	cd frontend && npm run dev

build-frontend:
	cd frontend && npm run build

test-backend:
	cd backend && uv run pytest tests/ -v
