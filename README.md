# knowledge-graph-api

A knowledge graph API. A FastAPI service that builds a graph of knowledge from
documents: it extracts entities and relationships (LLM + Jinja templates),
stores them in Neo4j + PostgreSQL (pgvector), and serves hybrid search
(vector + graph).

## Stack
- FastAPI (ingest / query / graph routes)
- Neo4j (`src/models/neo4j_driver.py`) + PostgreSQL/pgvector (`src/models/pg_driver.py`)
- Entity extraction: `src/services/entity_extractor.py`
- Graph building: `src/services/graph_builder.py`
- Hybrid search: `src/services/hybrid_search.py`
- Document parsing: `src/services/document_parser.py`
- Prompts: `src/templates/extraction_prompt.j2`

## Run
```bash
pip install -e .
uvicorn src.main:app --port 8000
```

## CI
`.github/workflows/ci.yml` — syntax check + `pytest` on every push, with
least-privilege permissions and pinned action versions.

## Author
Nick Yakim — github.com/yakim-nick
