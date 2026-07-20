.PHONY: up down build test lint clean

up:
	docker compose up -d

down:
	docker compose down -v

build:
	docker compose build

test:
	python -m pytest tests/ -v --tb=short

test-cov:
	python -m pytest tests/ --cov=src/ --cov-report=term-missing

lint:
	ruff check src/ tests/
	mypy src/ --ignore-missing-imports

typecheck:
	mypy src/ --ignore-missing-imports

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name '*.pyc' -delete

.PHONY: install
install:
	pip install --upgrade pip
	pip install -e ".[dev]"
