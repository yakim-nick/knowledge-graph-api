# knowledge-graph-api

Knowledge Graph API. FastAPI-сервис, который строит граф знаний из документов:
извлекает сущности и связи (LLM + шаблоны Jinja), сохраняет в Neo4j + PostgreSQL
(pgvector) и отдаёт гибридный поиск (векторный + графовый).

## Стек
- FastAPI (ingest / query / graph routes)
- Neo4j (`src/models/neo4j_driver.py`) + PostgreSQL/pgvector (`src/models/pg_driver.py`)
- Извлечение сущностей: `src/services/entity_extractor.py`
- Построение графа: `src/services/graph_builder.py`
- Гибридный поиск: `src/services/hybrid_search.py`
- Парсинг документов: `src/services/document_parser.py`
- Промпты: `src/templates/extraction_prompt.j2`

## Запуск
```bash
pip install -e .
uvicorn src.main:app --port 8000
```

## CI
`.github/workflows/ci.yml` — синтаксис-проверка + pytest на каждый push.

## Автор
Nick Yakim — github.com/yakim-nick
