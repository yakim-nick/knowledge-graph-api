from __future__ import annotations

import pytest
from src.services.graph_builder import _sanitize_label, ALLOWED_ENTITY_TYPES, ALLOWED_REL_TYPES


class TestSanitizeLabel:
    def test_allows_valid_entity_type(self):
        assert _sanitize_label("Service", ALLOWED_ENTITY_TYPES) == "Service"

    def test_allows_valid_rel_type(self):
        assert _sanitize_label("DEPENDS_ON", ALLOWED_REL_TYPES) == "DEPENDS_ON"

    def test_rejects_invalid_type(self):
        with pytest.raises(ValueError, match="not in allowed set"):
            _sanitize_label("Hacker", ALLOWED_ENTITY_TYPES)

    def test_rejects_malformed_label(self):
        with pytest.raises(ValueError, match="Invalid label format"):
            _sanitize_label("Service {name: 'x'}", ALLOWED_ENTITY_TYPES)

    def test_rejects_empty_string(self):
        with pytest.raises(ValueError, match="Invalid label format"):
            _sanitize_label("", ALLOWED_ENTITY_TYPES)


class TestSchemas:
    def test_entity_creation(self):
        from src.models.schemas import Entity
        e = Entity(name="api-gateway", type="Service", properties={"version": "2.0"})
        assert e.name == "api-gateway"
        assert e.type == "Service"
        assert e.properties["version"] == "2.0"

    def test_relationship_creation(self):
        from src.models.schemas import Relationship
        r = Relationship(source="a", target="b", rel_type="DEPENDS_ON")
        assert r.source == "a"
        assert r.target == "b"
        assert r.rel_type == "DEPENDS_ON"

    def test_extraction_result_defaults(self):
        from src.models.schemas import ExtractionResult
        result = ExtractionResult()
        assert result.entities == []
        assert result.relationships == []

    def test_search_request_validation(self):
        from src.models.schemas import SearchRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            SearchRequest(query="test", n_results=100)
        req = SearchRequest(query="test query", n_results=5, entity_filter=["Service"])
        assert req.n_results == 5

    def test_search_result_item_optional_graph_context(self):
        from src.models.schemas import SearchResultItem
        item = SearchResultItem(
            id=1, document_name="doc.md", chunk_index=0,
            text="text", entities=[], similarity=0.95, graph_context=None,
        )
        assert item.graph_context is None
