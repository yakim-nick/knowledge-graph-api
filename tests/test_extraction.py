"""Unit tests for graph label validation and the Pydantic data models."""

from __future__ import annotations

import pytest
from src.services.graph_builder import (
    _validate_label,
    ALLOWED_ENTITY_TYPES,
    ALLOWED_REL_TYPES,
)


class TestValidateLabel:
    """Tests for graph label validation (format + whitelist)."""

    def test_allows_valid_entity_type(self):
        """A whitelisted, well-formed entity type passes validation."""
        assert _validate_label("Service", ALLOWED_ENTITY_TYPES) == "Service"

    def test_allows_valid_rel_type(self):
        """A whitelisted, well-formed relationship type passes validation."""
        assert _validate_label("DEPENDS_ON", ALLOWED_REL_TYPES) == "DEPENDS_ON"

    def test_rejects_invalid_type(self):
        """A type outside the whitelist is rejected."""
        with pytest.raises(ValueError, match="not in allowed set"):
            _validate_label("Hacker", ALLOWED_ENTITY_TYPES)

    def test_rejects_malformed_label(self):
        """A label with invalid characters is rejected."""
        with pytest.raises(ValueError, match="Invalid label format"):
            _validate_label("Service {name: 'x'}", ALLOWED_ENTITY_TYPES)

    def test_rejects_empty_string(self):
        """An empty label is rejected."""
        with pytest.raises(ValueError, match="Invalid label format"):
            _validate_label("", ALLOWED_ENTITY_TYPES)


class TestSchemas:
    """Tests for the Pydantic data models."""

    def test_entity_creation(self):
        """An Entity can be constructed with name, type, and properties."""
        from src.models.schemas import Entity

        e = Entity(name="api-gateway", type="Service", properties={"version": "2.0"})
        assert e.name == "api-gateway"
        assert e.type == "Service"
        assert e.properties["version"] == "2.0"

    def test_relationship_creation(self):
        """A Relationship can be constructed with source, target, and type."""
        from src.models.schemas import Relationship

        r = Relationship(source="a", target="b", rel_type="DEPENDS_ON")
        assert r.source == "a"
        assert r.target == "b"
        assert r.rel_type == "DEPENDS_ON"

    def test_extraction_result_defaults(self):
        """ExtractionResult defaults to empty entity/relationship lists."""
        from src.models.schemas import ExtractionResult

        result = ExtractionResult()
        assert result.entities == []
        assert result.relationships == []

    def test_search_request_validation(self):
        """SearchRequest rejects n_results above the allowed maximum."""
        from src.models.schemas import SearchRequest
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            SearchRequest(query="test", n_results=100)
        req = SearchRequest(query="test query", n_results=5, entity_filter=["Service"])
        assert req.n_results == 5

    def test_search_result_item_optional_graph_context(self):
        """SearchResultItem allows graph_context to be None."""
        from src.models.schemas import SearchResultItem

        item = SearchResultItem(
            id=1,
            document_name="doc.md",
            chunk_index=0,
            text="text",
            entities=[],
            similarity=0.95,
            graph_context=None,
        )
        assert item.graph_context is None
