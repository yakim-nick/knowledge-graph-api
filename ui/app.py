"""Knowledge Graph Explorer — Streamlit dashboard.

Calls the existing `src` modules directly (no HTTP). Connects to Neo4j and
PostgreSQL/pgvector to let you upload documents, extract entities/relations,
browse the graph, and run hybrid searches.
"""

from __future__ import annotations

import asyncio
import io
import logging
import os
import tempfile
import time
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

# Must be the very first Streamlit call.
st.set_page_config(
    page_title="Knowledge Graph Explorer",
    page_icon="🔗",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Imports from the existing codebase
# ---------------------------------------------------------------------------
from src.config import settings
from src.models.neo4j_driver import Neo4jDriver
from src.models.pg_driver import PgDriver
from src.services.document_parser import DocumentParser
from src.services.entity_extractor import EntityExtractor
from src.services.graph_builder import GraphBuilder
from src.services.hybrid_search import HybridSearch

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Page config & branding
# ---------------------------------------------------------------------------
PAGE_TITLE = "Knowledge Graph Explorer"
PAGE_SUBTITLE = "Upload documents, extract entities & relationships, and explore your knowledge graph."

st.markdown(
    f"""
    <style>
      /* ---- global ---- */
      .main-header {{
          font-size: 2.2rem; font-weight: 700; letter-spacing: -0.02em;
          color: #111827; margin-bottom: 0.1rem; display: flex; align-items: center; gap: 0.5rem;
      }}
      .main-header small {{
          font-size: 1rem; font-weight: 400; color: #6b7280; margin-left: 0.5rem;
      }}
      .sub-header {{
          font-size: 1rem; color: #6b7280; margin-bottom: 1.5rem;
      }}
      .kpi-card {{
          background: #ffffff; border: 1px solid #e5e7eb; border-radius: 12px;
          padding: 1.2rem 1.5rem; box-shadow: 0 1px 3px rgba(0,0,0,0.04);
          text-align: center;
      }}
      .kpi-card .kpi-value {{
          font-size: 2rem; font-weight: 700; color: #111827; line-height: 1.2;
      }}
      .kpi-card .kpi-label {{
          font-size: 0.85rem; color: #6b7280; text-transform: uppercase;
          letter-spacing: 0.04em; margin-top: 0.25rem;
      }}
      .section-title {{
          font-size: 1.25rem; font-weight: 600; color: #111827;
          margin: 1.5rem 0 0.75rem 0;
      }}
      .result-card {{
          background: #ffffff; border: 1px solid #e5e7eb; border-radius: 10px;
          padding: 1rem 1.25rem; margin-bottom: 0.75rem;
      }}
      .result-card .score {{
          font-size: 0.8rem; font-family: monospace; color: #2563eb;
          font-weight: 600;
      }}
      .result-card .entities {{
          margin-top: 0.35rem; display: flex; flex-wrap: wrap; gap: 0.3rem;
      }}
      .result-card .entity-badge {{
          background: #eef2ff; color: #4338ca; font-size: 0.75rem;
          padding: 0.15rem 0.55rem; border-radius: 999px; font-weight: 500;
      }}
      .stAlert {{ border-radius: 8px; }}
      footer {{ display: none; }}
      #MainMenu {{ visibility: hidden; }}
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Async helper
# ---------------------------------------------------------------------------


def _run_async(coro) -> Any:
    """Synchronously await an async coroutine from Streamlit's sync context."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    # If a loop is already running, use a new one in a separate thread.
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(asyncio.run, coro)
        return future.result()


# ---------------------------------------------------------------------------
# Cached resource handles
# ---------------------------------------------------------------------------


@st.cache_resource(show_spinner="Connecting to Neo4j …")
def _get_neo4j() -> Neo4jDriver | None:
    """Return a connected Neo4jDriver (or None on failure)."""
    driver = Neo4jDriver()
    try:
        _run_async(driver.connect())
        return driver
    except Exception as exc:
        st.warning(f"Neo4j connection failed: {exc}")
        return None


@st.cache_resource(show_spinner="Connecting to PostgreSQL …")
def _get_pg() -> PgDriver | None:
    """Return a connected PgDriver (or None on failure)."""
    driver = PgDriver()
    try:
        _run_async(driver.connect())
        return driver
    except Exception as exc:
        st.warning(f"PostgreSQL connection failed: {exc}")
        return None


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------


def _fetch_stats(neo4j: Neo4jDriver | None, pg: PgDriver | None) -> dict[str, int]:
    """Return entity / relationship / chunk counts."""
    result: dict[str, int] = {"nodes": 0, "relationships": 0, "vector_chunks": 0}
    if neo4j is not None:
        try:
            result["nodes"] = _run_async(neo4j.count_nodes())
            result["relationships"] = _run_async(neo4j.count_relationships())
        except Exception:
            pass
    if pg is not None:
        try:
            result["vector_chunks"] = _run_async(pg.count_chunks())
        except Exception:
            pass
    return result


def _fetch_all_nodes(neo4j: Neo4jDriver) -> list[dict]:
    """Return all nodes from the graph."""
    return _run_async(
        neo4j.run_cypher(
            "MATCH (n:Entity) RETURN n.name AS name, n.type AS type, n.properties AS props ORDER BY n.name"
        )
    )


def _fetch_all_edges(neo4j: Neo4jDriver) -> list[dict]:
    """Return all relationships from the graph."""
    return _run_async(
        neo4j.run_cypher(
            "MATCH (a:Entity)-[r]->(b:Entity) RETURN a.name AS source, type(r) AS rel_type, b.name AS target"
        )
    )


def _fetch_documents(pg: PgDriver) -> list[str]:
    """Return distinct document names."""
    rows = _run_async(
        pg._pool.fetch("SELECT DISTINCT document_name FROM document_chunks ORDER BY document_name")
    )
    return [r["document_name"] for r in rows]


def _fetch_document_chunks(pg: PgDriver, doc_name: str) -> pd.DataFrame:
    rows = _run_async(
        pg._pool.fetch(
            "SELECT id, chunk_index, text, entities FROM document_chunks WHERE document_name = $1 ORDER BY chunk_index",
            doc_name,
        )
    )
    return pd.DataFrame([dict(r) for r in rows])


def _build_pyvis_html(nodes: list[dict], edges: list[dict]) -> str:
    """Build a self-contained pyvis Network HTML string."""
    from pyvis.network import Network

    net = Network(height="600px", width="100%", directed=True, notebook=False, bgcolor="#ffffff", font_color="#111827")

    # Add nodes
    for n in nodes:
        label = n["name"]
        title = f"<b>{n['name']}</b><br/>Type: {n['type']}"
        color = _entity_color(n.get("type", ""))
        net.add_node(n["name"], label=label, title=title, color=color, size=18, borderWidth=2)

    # Add edges
    for e in edges:
        net.add_edge(
            e["source"],
            e["target"],
            label=e["rel_type"],
            title=f"{e['source']} → {e['target']}<br/>{e['rel_type']}",
            arrows="to",
            font={"size": 11, "color": "#6b7280", "strokeWidth": 0},
            color="#9ca3af",
            width=2,
        )

    net.set_options(
        """
        {
          "physics": {
            "enabled": true,
            "stabilization": {"iterations": 100},
            "repulsion": {"nodeDistance": 180, "centralGravity": 0.3, "springLength": 200}
          },
          "interaction": {
            "hover": true,
            "tooltipDelay": 100,
            "zoomView": true,
            "dragView": true
          }
        }
        """
    )
    return net.generate_html()


def _entity_color(etype: str) -> str:
    palette = {
        "Service": "#3b82f6",
        "Database": "#8b5cf6",
        "System": "#06b6d4",
        "Person": "#f59e0b",
        "Team": "#ef4444",
        "Process": "#10b981",
        "Document": "#6366f1",
        "API": "#ec4899",
        "Infrastructure": "#14b8a6",
        "Concept": "#f97316",
        "Entity": "#6b7280",
    }
    return palette.get(etype, "#6b7280")


def _search(
    neo4j: Neo4jDriver,
    pg: PgDriver,
    query_text: str,
    n_results: int = 10,
    entity_filter: list[str] | None = None,
) -> list[dict]:
    """Run a hybrid search and return results as plain dicts."""
    search = HybridSearch(neo4j, pg)
    items = _run_async(search.search(query=query_text, n_results=n_results, entity_filter=entity_filter))
    out = []
    for item in items:
        out.append({
            "id": item.id,
            "document_name": item.document_name,
            "chunk_index": item.chunk_index,
            "text": item.text,
            "entities": item.entities,
            "similarity": item.similarity,
            "graph_context": item.graph_context,
        })
    return out


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown(
        f"<div class='main-header' style='font-size:1.4rem;'>🔗 {PAGE_TITLE}</div>",
        unsafe_allow_html=True,
    )
    st.markdown("<hr style='margin:0.5rem 0 1rem 0;'>", unsafe_allow_html=True)

    # --- Connection status ---
    neo4j = _get_neo4j()
    pg = _get_pg()

    col1, col2 = st.columns(2)
    with col1:
        if neo4j is not None:
            st.markdown("✅ **Neo4j**")
        else:
            st.markdown("❌ **Neo4j**")
    with col2:
        if pg is not None:
            st.markdown("✅ **PostgreSQL**")
        else:
            st.markdown("❌ **PostgreSQL**")

    st.markdown("<hr style='margin:0.5rem 0 1rem 0;'>", unsafe_allow_html=True)

    # --- Upload section ---
    st.markdown("### 📄 Upload Document")
    uploaded_file = st.file_uploader(
        "Choose a file",
        type=["txt", "md", "pdf", "html", "json", "yaml", "yml"],
        label_visibility="collapsed",
    )

    if uploaded_file is not None and st.button("⚡ Extract & Build Graph", type="primary", use_container_width=True):
        if neo4j is None or pg is None:
            st.error("Cannot process — database connections are not available.")
        else:
            ingest_placeholder = st.empty()
            with ingest_placeholder.container():
                with st.spinner("Parsing document …"):
                    content = uploaded_file.read()
                    parser = DocumentParser(chunk_size=settings.chunk_size, chunk_overlap=settings.chunk_overlap)
                    chunks = _run_async(parser.parse(content, uploaded_file.name))
                if not chunks:
                    st.error("Document produced no chunks.")
                else:
                    st.info(f"📄 {len(chunks)} chunks created.")
                    all_entities: list = []
                    all_relationships: list = []
                    extractor = EntityExtractor()
                    progress_bar = st.progress(0, text="Extracting entities …")
                    for i, chunk in enumerate(chunks):
                        result = _run_async(extractor.extract(chunk.text))
                        all_entities.extend(result.entities)
                        all_relationships.extend(result.relationships)
                        progress_bar.progress((i + 1) / len(chunks), text=f"Chunk {i + 1}/{len(chunks)}")
                    with st.spinner("Building graph & indexing …"):
                        builder = GraphBuilder(neo4j)
                        nodes_created = _run_async(builder.build(all_entities, all_relationships))
                        search = HybridSearch(neo4j, pg)
                        _run_async(search.index(chunks, all_entities))
                    st.success(
                        f"✅ **{uploaded_file.name}** ingested — "
                        f"{len(all_entities)} entities, {len(all_relationships)} relationships, "
                        f"{nodes_created} graph nodes."
                    )
                    # Clear cached stats so they refresh
                    st.cache_data.clear()
                    time.sleep(0.5)
                    st.rerun()

    st.markdown("<hr style='margin:0.5rem 0 1rem 0;'>", unsafe_allow_html=True)

    # --- Stats (always visible) ---
    st.markdown("### 📊 Statistics")
    stats = _fetch_stats(neo4j, pg) if (neo4j is not None and pg is not None) else {"nodes": 0, "relationships": 0, "vector_chunks": 0}
    st.metric("Graph Nodes", stats["nodes"])
    st.metric("Relationships", stats["relationships"])
    st.metric("Vector Chunks", stats["vector_chunks"])

    st.markdown("<hr style='margin:0.5rem 0 1rem 0;'>", unsafe_allow_html=True)
    st.caption(f"v1.0.0 · [{settings.extraction_model}]")

# ---------------------------------------------------------------------------
# Main area — tabs
# ---------------------------------------------------------------------------

tab_dashboard, tab_graph, tab_search, tab_documents = st.tabs(
    ["📊 Dashboard", "🔗 Graph", "🔍 Search", "📂 Documents"]
)

# ═══════════════════════════════════════════════════════════════════════════
# TAB 1 — Dashboard
# ═══════════════════════════════════════════════════════════════════════════

with tab_dashboard:
    st.markdown(
        f"<div class='main-header'>{PAGE_TITLE} <small>{PAGE_SUBTITLE}</small></div>",
        unsafe_allow_html=True,
    )

    if neo4j is None and pg is None:
        st.warning("No database connections available. Start the API stack (`docker compose up`) and refresh.")
    else:
        stats = _fetch_stats(neo4j, pg)
        kpi_cols = st.columns(3)
        kpis = [
            ("🗂️", "Graph Nodes", stats["nodes"]),
            ("🔗", "Relationships", stats["relationships"]),
            ("📄", "Vector Chunks", stats["vector_chunks"]),
        ]
        for col, (icon, label, value) in zip(kpi_cols, kpis):
            with col:
                st.markdown(
                    f"""
                    <div class="kpi-card">
                        <div style="font-size:1.8rem;">{icon}</div>
                        <div class="kpi-value">{value:,}</div>
                        <div class="kpi-label">{label}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        st.markdown("<br>", unsafe_allow_html=True)

        # Quick-glance entity type breakdown
        if neo4j is not None:
            type_rows = _run_async(
                neo4j.run_cypher(
                    "MATCH (n:Entity) RETURN n.type AS type, count(*) AS cnt ORDER BY cnt DESC"
                )
            )
            if type_rows:
                st.markdown("<div class='section-title'>Entities by Type</div>", unsafe_allow_html=True)
                type_df = pd.DataFrame(type_rows)
                st.bar_chart(type_df.set_index("type"), height=250, use_container_width=True)

        # Recent activity placeholder
        st.markdown("<div class='section-title'>Getting Started</div>", unsafe_allow_html=True)
        st.markdown(
            """
            1. **Upload a document** using the sidebar file picker.
            2. Click **Extract & Build Graph** — the LLM will extract entities and relationships.
            3. Browse the **Graph** tab to explore connections.
            4. Use **Search** for hybrid (vector + graph) retrieval.
            """
        )

# ═══════════════════════════════════════════════════════════════════════════
# TAB 2 — Graph
# ═══════════════════════════════════════════════════════════════════════════

with tab_graph:
    st.markdown("<div class='section-title'>Knowledge Graph</div>", unsafe_allow_html=True)

    if neo4j is None:
        st.warning("Neo4j is not connected. Start the stack and refresh.")
    else:
        with st.spinner("Loading graph data …"):
            try:
                nodes = _fetch_all_nodes(neo4j)
                edges = _fetch_all_edges(neo4j)
            except Exception as exc:
                st.error(f"Failed to query graph: {exc}")
                nodes, edges = [], []

        if not nodes:
            st.info("The graph is empty. Ingest a document first.")
        else:
            st.markdown(f"_{len(nodes):,} nodes · {len(edges):,} relationships_")
            viz_mode = st.radio("Visualization", ["Interactive Graph", "Node Table", "Edge Table"], horizontal=True, label_visibility="collapsed")

            if viz_mode == "Interactive Graph":
                try:
                    html_str = _build_pyvis_html(nodes, edges)
                    from streamlit.components.v1 import html as st_html

                    st_html(html_str, height=620, scrolling=False)
                except ImportError:
                    st.warning("pyvis not installed — showing tables instead. Install with `pip install pyvis`.")
                    viz_mode = "Node Table"  # fallback

            if viz_mode == "Node Table":
                node_df = pd.DataFrame(nodes)
                if not node_df.empty:
                    st.dataframe(node_df, use_container_width=True, hide_index=True)
                else:
                    st.info("No nodes found.")

            if viz_mode == "Edge Table":
                edge_df = pd.DataFrame(edges)
                if not edge_df.empty:
                    st.dataframe(edge_df, use_container_width=True, hide_index=True)
                else:
                    st.info("No relationships found.")

# ═══════════════════════════════════════════════════════════════════════════
# TAB 3 — Search
# ═══════════════════════════════════════════════════════════════════════════

with tab_search:
    st.markdown("<div class='section-title'>Hybrid Search</div>", unsafe_allow_html=True)

    if neo4j is None or pg is None:
        st.warning("Database connections required. Start the stack and refresh.")
    else:
        col_q, col_n = st.columns([3, 1])
        with col_q:
            query_text = st.text_input("Search query", placeholder="e.g. microservices architecture …", label_visibility="collapsed")
        with col_n:
            n_results = st.number_input("Results", min_value=1, max_value=50, value=10, label_visibility="collapsed")

        if query_text:
            with st.spinner("Searching …"):
                try:
                    results = _search(neo4j, pg, query_text, n_results=n_results)
                except Exception as exc:
                    st.error(f"Search failed: {exc}")
                    results = []

            if not results:
                st.info("No results found.")
            else:
                st.markdown(f"_{len(results)} result(s)_")
                for r in results:
                    with st.container():
                        st.markdown(
                            f"""
                            <div class="result-card">
                                <div style="display:flex;justify-content:space-between;align-items:center;">
                                    <strong style="font-size:0.9rem;">{r['document_name']}</strong>
                                    <span class="score">score: {r['similarity']:.4f}</span>
                                </div>
                                <div style="margin-top:0.4rem;font-size:0.9rem;color:#374151;line-height:1.5;">
                                    {r['text'][:500]}{'…' if len(r['text']) > 500 else ''}
                                </div>
                                <div class="entities">
                                    {''.join(f'<span class="entity-badge">{e}</span>' for e in r['entities'][:10])}
                                </div>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )

                        # Expandable graph context
                        if r.get("graph_context"):
                            with st.expander(f"Graph context ({len(r['graph_context'])} relation(s))"):
                                ctx_df = pd.DataFrame(r["graph_context"])
                                st.dataframe(ctx_df, use_container_width=True, hide_index=True)

# ═══════════════════════════════════════════════════════════════════════════
# TAB 4 — Documents
# ═══════════════════════════════════════════════════════════════════════════

with tab_documents:
    st.markdown("<div class='section-title'>Ingested Documents</div>", unsafe_allow_html=True)

    if pg is None:
        st.warning("PostgreSQL is not connected.")
    else:
        try:
            doc_names = _fetch_documents(pg)
        except Exception as exc:
            st.error(f"Failed to list documents: {exc}")
            doc_names = []

        if not doc_names:
            st.info("No documents have been ingested yet.")
        else:
            selected_doc = st.selectbox("Select a document", doc_names, label_visibility="collapsed")
            if selected_doc:
                chunks_df = _fetch_document_chunks(pg, selected_doc)
                if not chunks_df.empty:
                    st.markdown(f"_{len(chunks_df)} chunk(s)_")
                    st.dataframe(chunks_df, use_container_width=True, hide_index=True)
                else:
                    st.info("No chunks found.")
