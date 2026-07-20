from __future__ import annotations

from pydantic import BaseModel, Field


class Entity(BaseModel):
    name: str
    type: str
    properties: dict[str, str] = Field(default_factory=dict)


class Relationship(BaseModel):
    source: str
    target: str
    rel_type: str
    properties: dict[str, str] = Field(default_factory=dict)


class ExtractionResult(BaseModel):
    entities: list[Entity] = Field(default_factory=list)
    relationships: list[Relationship] = Field(default_factory=list)


class IngestResponse(BaseModel):
    filename: str
    chunks_processed: int
    entities_extracted: int
    relationships_mapped: int
    nodes_created: int


class GraphQueryRequest(BaseModel):
    cypher: str
    parameters: dict = Field(default_factory=dict)


class GraphQueryResponse(BaseModel):
    results: list[dict]
    query: str


class SearchRequest(BaseModel):
    query: str
    n_results: int = Field(default=10, ge=1, le=50)
    entity_filter: list[str] | None = None
    relationship_filter: list[str] | None = None


class SearchResultItem(BaseModel):
    id: int
    document_name: str
    chunk_index: int
    text: str
    entities: list[str]
    similarity: float
    graph_context: list[dict] | None = None


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResultItem]


class DocumentChunk(BaseModel):
    text: str
    index: int
    document_name: str
