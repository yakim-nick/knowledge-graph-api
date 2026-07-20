from __future__ import annotations

import pytest
from src.models.schemas import (
    IngestResponse,
    GraphQueryRequest,
    GraphQueryResponse,
    SearchRequest,
    SearchResponse,
    SearchResultItem,
)


class TestIngestResponse:
    def test_default_values(self):
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
    def test_read_only_validation(self):
        req = GraphQueryRequest(
            cypher="MATCH (n) RETURN n LIMIT 10",
            parameters={"limit": 10},
        )
        assert "MATCH" in req.cypher
        assert req.parameters["limit"] == 10


class TestSearchRequest:
    def test_n_results_clamped(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            SearchRequest(query="test", n_results=100)

    def test_valid_search_request(self):
        req = SearchRequest(query="test query", n_results=5, entity_filter=["Service"])
        assert req.n_results == 5
        assert req.entity_filter == ["Service"]


class TestSearchResultItem:
    def test_graph_context_optional(self):
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
    def test_contains_results(self):
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
