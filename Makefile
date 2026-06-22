.PHONY: help install dev up down logs migrate seed test lint infra-init infra-fmt infra-validate infra-plan infra-apply infra-output

help:
	@echo "Cloud Lab commands"
	@echo "  make up             Start PostgreSQL + FastAPI with Docker Compose"
	@echo "  make down           Stop local stack"
	@echo "  make logs           Follow backend logs"
	@echo "  make migrate        Run Alembic migrations in Docker"
	@echo "  make seed           Seed demo data in Docker"
	@echo "  make test           Run backend tests"
	@echo "  make infra-init     Terraform init"
	@echo "  make infra-plan     Terraform plan"
	@echo "  make infra-apply    Terraform apply"

install:
	cd server && python -m venv .venv && .venv/Scripts/pip install -r requirements.txt

dev:
	cd server && .venv/Scripts/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

up:
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs -f backend

migrate:
	docker compose exec backend alembic upgrade head

seed:
	docker compose exec backend python -m scripts.seed

test:
	cd server && python -m pytest tests

lint:
	cd server && python -m compileall app scripts -q

infra-init:
	cd infrastructure && terraform init

infra-fmt:
	cd infrastructure && terraform fmt

infra-validate:
	cd infrastructure && terraform validate

infra-plan:
	cd infrastructure && terraform plan

infra-apply:
	cd infrastructure && terraform apply

infra-output:
	cd infrastructure && terraform output
