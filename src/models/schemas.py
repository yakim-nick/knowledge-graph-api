"""Pydantic models shared across the API, services, and UI."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Entity(BaseModel):
    """A named, typed entity extracted from a document (e.g. a Service or Person)."""

    name: str
    type: str
    properties: dict[str, str] = Field(default_factory=dict)


class Relationship(BaseModel):
    """A typed, directed link between two entities (e.g. DEPENDS_ON)."""

    source: str
    target: str
    rel_type: str
    properties: dict[str, str] = Field(default_factory=dict)


class ExtractionResult(BaseModel):
    """The outcome of LLM extraction for one chunk."""

    entities: list[Entity] = Field(default_factory=list)
    relationships: list[Relationship] = Field(default_factory=list)


class IngestResponse(BaseModel):
    """Summary returned after a document is ingested."""

    filename: str
    chunks_processed: int
    entities_extracted: int
    relationships_mapped: int
    nodes_created: int


class GraphQueryRequest(BaseModel):
    """A read-only Cypher query with optional parameters."""

    cypher: str
    parameters: dict = Field(default_factory=dict)


class GraphQueryResponse(BaseModel):
    """Records returned by a graph query, echoed with the original query."""

    results: list[dict]
    query: str


class SearchRequest(BaseModel):
    """A hybrid search request with optional entity/relationship filters."""

    query: str
    n_results: int = Field(default=10, ge=1, le=50)
    entity_filter: list[str] | None = None
    relationship_filter: list[str] | None = None


class SearchResultItem(BaseModel):
    """One ranked search result with optional graph context."""

    id: int
    document_name: str
    chunk_index: int
    text: str
    entities: list[str]
    similarity: float
    graph_context: list[dict] | None = None


class SearchResponse(BaseModel):
    """The full hybrid search response."""

    query: str
    results: list[SearchResultItem]


class DocumentChunk(BaseModel):
    """A token-bounded slice of a document ready for extraction and embedding."""

    text: str
    index: int
    document_name: str
