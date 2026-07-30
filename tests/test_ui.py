"""Tests for the Streamlit UI module.

We mock all heavy imports (streamlit, pandas, neo4j, src modules, …)
so the tests can run in isolation without a display or database.
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _async_method(return_value=None):
    """Return an async function that returns *return_value* when called."""
    async def _inner(*args, **kwargs):
        return return_value
    return _inner


def _make_streamlit_mock() -> MagicMock:
    """Return a configured MagicMock that mimics Streamlit's common API shape."""
    m = MagicMock()

    m.set_page_config = MagicMock()

    # sidebar as context manager
    sidebar = MagicMock()
    sidebar.__enter__ = MagicMock(return_value=sidebar)
    sidebar.__exit__ = MagicMock(return_value=None)
    m.sidebar = sidebar

    # columns → tuple of mocks (supports both int and list[width, …])
    def _columns(spec, **kwargs):
        if isinstance(spec, int):
            n = spec
        else:
            n = len(spec)
        return tuple(MagicMock() for _ in range(n))

    m.columns = _columns

    # tabs → list of mocks
    m.tabs = MagicMock(return_value=[MagicMock() for _ in range(4)])

    # spinner / expander / container / empty as context managers
    for name in ("spinner", "expander", "container"):
        ctx = MagicMock()
        ctx.__enter__ = MagicMock()
        ctx.__exit__ = MagicMock(return_value=None)
        setattr(m, name, MagicMock(return_value=ctx))

    empty = MagicMock()
    empty.__enter__ = MagicMock(return_value=empty)
    empty.__exit__ = MagicMock(return_value=None)
    m.empty = MagicMock(return_value=empty)

    # cache_resource as passthrough decorator
    m.cache_resource = MagicMock(return_value=lambda f: f)

    # UI elements
    m.file_uploader = MagicMock(return_value=None)
    m.button = MagicMock(return_value=False)
    m.text_input = MagicMock(return_value="")
    m.number_input = MagicMock(return_value=10)
    m.selectbox = MagicMock(return_value="")
    m.radio = MagicMock(return_value="Node Table")
    m.progress = MagicMock()
    m.metric = MagicMock()
    m.markdown = MagicMock()
    m.dataframe = MagicMock()
    m.bar_chart = MagicMock()
    m.info = MagicMock()
    m.success = MagicMock()
    m.warning = MagicMock()
    m.error = MagicMock()
    m.caption = MagicMock()
    m.rerun = MagicMock()
    m.stop = MagicMock(side_effect=SystemExit)

    # data cache
    m.cache_data = MagicMock()
    m.cache_data.clear = MagicMock()

    return m


def _make_neo4j_mock() -> MagicMock:
    """Return a Neo4jDriver-like instance with async methods returning coroutines."""
    inst = MagicMock()
    inst.connect = _async_method()
    inst.disconnect = _async_method()
    inst.count_nodes = _async_method(0)
    inst.count_relationships = _async_method(0)
    inst.run_cypher = _async_method([])
    inst.execute_batch = _async_method()
    return inst


def _make_pg_mock() -> MagicMock:
    """Return a PgDriver-like instance with async methods returning coroutines."""
    inst = MagicMock()
    inst.connect = _async_method()
    inst.disconnect = _async_method()
    inst.count_chunks = _async_method(0)
    inst.store_chunk = _async_method(0)
    inst.similarity_search = _async_method([])

    # pool — used in _fetch_documents / _fetch_document_chunks
    pool = MagicMock()
    pool.fetch = _async_method([])
    inst._pool = pool

    return inst


# ---------------------------------------------------------------------------
# Patch all problematic modules before importing ui.app
# ---------------------------------------------------------------------------

_streamlit_mock = _make_streamlit_mock()
_neo4j_instance = _make_neo4j_mock()
_pg_instance = _make_pg_mock()

_PATCHED: dict[str, MagicMock] = {
    "pandas": MagicMock(),
    "streamlit": _streamlit_mock,
    "streamlit.components": MagicMock(),
    "streamlit.components.v1": MagicMock(),
    "src": MagicMock(),
    "src.config": MagicMock(),
    "src.models": MagicMock(),
    "src.models.neo4j_driver": MagicMock(),
    "src.models.pg_driver": MagicMock(),
    "src.services": MagicMock(),
    "src.services.document_parser": MagicMock(),
    "src.services.entity_extractor": MagicMock(),
    "src.services.graph_builder": MagicMock(),
    "src.services.hybrid_search": MagicMock(),
    "src.services.embeddings": MagicMock(),
}

for mod_name, mock in _PATCHED.items():
    sys.modules[mod_name] = mock

# Wire up nested attribute access so e.g. ``src.models.neo4j_driver`` resolves
_PATCHED["src"].models = _PATCHED["src.models"]
_PATCHED["src"].models.neo4j_driver = _PATCHED["src.models.neo4j_driver"]
_PATCHED["src"].models.pg_driver = _PATCHED["src.models.pg_driver"]
_PATCHED["src"].services = _PATCHED["src.services"]
_PATCHED["src"].services.document_parser = _PATCHED["src.services.document_parser"]
_PATCHED["src"].services.entity_extractor = _PATCHED["src.services.entity_extractor"]
_PATCHED["src"].services.graph_builder = _PATCHED["src.services.graph_builder"]
_PATCHED["src"].services.hybrid_search = _PATCHED["src.services.hybrid_search"]
_PATCHED["src"].services.embeddings = _PATCHED["src.services.embeddings"]
_PATCHED["src"].config = _PATCHED["src.config"]

# Make Neo4jDriver() and PgDriver() return our preconfigured instances
_PATCHED["src.models.neo4j_driver"].Neo4jDriver = MagicMock(return_value=_neo4j_instance)
_PATCHED["src.models.pg_driver"].PgDriver = MagicMock(return_value=_pg_instance)

# Settings
_PATCHED["src.config"].settings.chunk_size = 1000
_PATCHED["src.config"].settings.chunk_overlap = 200
_PATCHED["src.config"].settings.extraction_model = "gpt-4o"

# Now safe to import ui.app
import ui.app  # noqa: E402


# ---------------------------------------------------------------------------
# _entity_color
# ---------------------------------------------------------------------------


class TestEntityColor:
    def test_returns_known_colors(self) -> None:
        assert ui.app._entity_color("Service") == "#3b82f6"
        assert ui.app._entity_color("Database") == "#8b5cf6"
        assert ui.app._entity_color("Person") == "#f59e0b"
        assert ui.app._entity_color("Team") == "#ef4444"
        assert ui.app._entity_color("Concept") == "#f97316"

    def test_fallback_for_unknown_type(self) -> None:
        assert ui.app._entity_color("FooBar") == "#6b7280"


# ---------------------------------------------------------------------------
# _run_async
# ---------------------------------------------------------------------------


class TestRunAsync:
    def test_runs_coroutine_and_returns_result(self) -> None:
        async def double(x: int) -> int:
            return x * 2

        assert ui.app._run_async(double(21)) == 42

    def test_raises_on_coroutine_error(self) -> None:
        async def crash() -> None:
            raise ValueError("boom")

        with pytest.raises(ValueError, match="boom"):
            ui.app._run_async(crash())

    def test_with_string_result(self) -> None:
        async def greet(name: str) -> str:
            return f"Hello {name}"

        assert ui.app._run_async(greet("World")) == "Hello World"


# ---------------------------------------------------------------------------
# _build_pyvis_html
# ---------------------------------------------------------------------------


class TestBuildPyvisHtml:
    def test_returns_html_string(self) -> None:
        nodes = [{"name": "A", "type": "Service", "properties": {}}]
        edges: list[dict] = []
        html = ui.app._build_pyvis_html(nodes, edges)
        assert isinstance(html, str)
        assert len(html) > 100

    def test_includes_graph_structure(self) -> None:
        nodes = [
            {"name": "A", "type": "Service", "properties": {}},
            {"name": "B", "type": "Database", "properties": {}},
        ]
        edges = [{"source": "A", "target": "B", "rel_type": "DEPENDS_ON"}]
        html = ui.app._build_pyvis_html(nodes, edges)
        assert "A" in html
        assert "B" in html


# ---------------------------------------------------------------------------
# _fetch_stats — only the None-guard path is tested here
# ---------------------------------------------------------------------------


class TestFetchStats:
    def test_returns_zeros_when_both_none(self) -> None:
        result = ui.app._fetch_stats(None, None)
        assert result == {"nodes": 0, "relationships": 0, "vector_chunks": 0}

    def test_returns_zeros_when_neo4j_none(self) -> None:
        pg = MagicMock()
        result = ui.app._fetch_stats(None, pg)
        assert result["nodes"] == 0
        assert result["relationships"] == 0


# ---------------------------------------------------------------------------
# Smoke test — verify the app module initialised without crashing
# ---------------------------------------------------------------------------


class TestAppInit:
    def test_set_page_config_was_called(self) -> None:
        _streamlit_mock.set_page_config.assert_called_once()

    def test_entity_color_available(self) -> None:
        assert callable(ui.app._entity_color)

    def test_run_async_available(self) -> None:
        assert callable(ui.app._run_async)
