help:
	@echo "Available commands:"
	@echo "  install       Install dependencies"
	@echo "  run           Run the production server"
	@echo "  dev           Run the development server with reload"
	@echo "  docker-up     Start the docker containers"
	@echo "  docker-down   Stop the docker containers"
	@echo "  migrate       Generate a new migration (usage: make migrate msg=\"message\")"
	@echo "  up            Apply all migrations"
	@echo "  up-one        Apply one migration step"
	@echo "  down          Downgrade to base"
	@echo "  down-one      Downgrade one migration step"
	@echo "  history       Show migration history"
	@echo "  clean         Remove cache files"

install:
	pip install -r requirements.txt

run:
	uvicorn app.main:app --host 0.0.0.0 --port 8000

dev:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

docker-up:
	docker compose up -d

docker-down:
	docker compose down

migrate:
	@if [ -z "$(msg)" ]; then echo "Error: Provide a message using msg=\"...\""; exit 1; fi
	alembic revision --autogenerate -m "$(msg)"

up:
	alembic upgrade head

up-one:
	alembic upgrade +1

down:
	alembic downgrade base

down-one:
	alembic downgrade -1

history:
	alembic history

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
