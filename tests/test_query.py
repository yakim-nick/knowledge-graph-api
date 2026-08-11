"""Unit tests for the query-related Pydantic schemas."""

from __future__ import annotations

import pytest
from src.models.schemas import (
    IngestResponse,
    GraphQueryRequest,
    SearchRequest,
    SearchResponse,
    SearchResultItem,
)


class TestIngestResponse:
    """Tests for the ingest summary response model."""

    def test_default_values(self):
        """IngestResponse stores the ingest summary fields."""
        resp = IngestResponse(
            filename="test.md",
            chunks_processed=5,
            entities_extracted=24,
            relationships_mapped=18,
            nodes_created=24,
        )
        assert resp.filename == "test.md"
        assert resp.chunks_processed == 5
        assert resp.nodes_created == 24


class TestGraphQueryRequest:
    """Tests for the graph query request model."""

    def test_read_only_validation(self):
        """GraphQueryRequest carries a Cypher query and parameters."""
        req = GraphQueryRequest(
            cypher="MATCH (n) RETURN n LIMIT 10",
            parameters={"limit": 10},
        )
        assert "MATCH" in req.cypher
        assert req.parameters["limit"] == 10


class TestSearchRequest:
    """Tests for the hybrid search request model."""

    def test_n_results_clamped(self):
        """SearchRequest rejects n_results above the allowed maximum."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            SearchRequest(query="test", n_results=100)

    def test_valid_search_request(self):
        """A valid search request keeps its filters."""
        req = SearchRequest(query="test query", n_results=5, entity_filter=["Service"])
        assert req.n_results == 5
        assert req.entity_filter == ["Service"]


class TestSearchResultItem:
    """Tests for a single search result item."""

    def test_graph_context_optional(self):
        """SearchResultItem allows graph_context to be None."""
        item = SearchResultItem(
            id=1,
            document_name="doc.md",
            chunk_index=0,
            text="some text",
            entities=["ServiceA"],
            similarity=0.95,
            graph_context=None,
        )
        assert item.graph_context is None


class TestSearchResponse:
    """Tests for the search response model."""

    def test_contains_results(self):
        """SearchResponse wraps a list of result items."""
        resp = SearchResponse(
            query="test",
            results=[
                SearchResultItem(
                    id=1,
                    document_name="doc.md",
                    chunk_index=0,
                    text="text",
                    entities=[],
                    similarity=0.9,
                )
            ],
        )
        assert len(resp.results) == 1
