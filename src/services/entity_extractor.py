from __future__ import annotations

import json
import logging
from typing import Any

from openai import AsyncOpenAI

from src.config import settings
from src.models.schemas import ExtractionResult, Entity, Relationship

logger = logging.getLogger(__name__)


EXTRACTION_SYSTEM_PROMPT = """You are a knowledge graph extraction engine.
Given a document chunk, extract:
1. Entities — distinct named concepts (people, systems, services, databases, teams, processes, documents)
2. Relationships — directed connections between entities with a type label

Rules:
- Entity types must be one of: Service, Database, System, Person, Team, Process, Document, API, Infrastructure, Concept
- Relationship types must be one of: DEPENDS_ON, OWNS, USES, DEPLOYS, CONTAINS, MANAGES, COMMUNICATES_WITH, DOCUMENTS, IMPLEMENTS
- Every relationship must connect two entities that both appear in the extraction
- Include a brief description in properties for each entity and relationship
- Return ONLY valid JSON with no markdown fences"""


class EntityExtractor:
    def __init__(self) -> None:
        self._client = AsyncOpenAI(api_key=settings.openai_api_key)
        self._model = settings.extraction_model

    async def extract(self, chunk_text: str) -> ExtractionResult:
        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": f"Extract entities and relationships from this text:\n\n{chunk_text}",
                    },
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
            )

            raw = response.choices[0].message.content or "{}"
            parsed = json.loads(raw)

            entities = [
                Entity(name=e["name"], type=e["type"], properties=e.get("properties", {}))
                for e in parsed.get("entities", [])
            ]

            relationships = [
                Relationship(
                    source=r["source"],
                    target=r["target"],
                    rel_type=r["rel_type"],
                    properties=r.get("properties", {}),
                )
                for r in parsed.get("relationships", [])
            ]

            logger.debug(f"Extracted {len(entities)} entities, {len(relationships)} relationships")
            return ExtractionResult(entities=entities, relationships=relationships)

        except json.JSONDecodeError as exc:
            logger.error(f"LLM returned invalid JSON: {exc}")
            return ExtractionResult()
        except Exception as exc:
            logger.error(f"Extraction failed: {exc}", exc_info=True)
            return ExtractionResult()
