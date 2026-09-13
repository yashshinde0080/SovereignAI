"""
Regression test: RAG delete/re-ingest must not desync FAISS from metadata.

Historical bug: delete_document() wiped metadata rows but left stale vectors in
the FAISS index ("rebuild recommended" was logged but never done). The next
ingest then assigned vector_index starting at 0 — colliding with the stale
FAISS positions — so get_chunks_by_vector_indices() missed and every chat RAG
query returned zero sources ("unable to access sources").

Covers:
- ingest keeps FAISS/metadata counts in sync
- delete_document() rebuilds so counts stay equal
- re-ingest after delete: searches still resolve content (no collisions)
- full rebuild maps vector_index cumulatively (multi-doc correct)
- startup self-heal repairs a desynced store (orphans dropped)
"""
import os
import tempfile

import numpy as np
import pytest

from app.vectorstore.config import VectorStoreConfig
from app.vectorstore.manager import VectorStoreManager
from app.vectorstore.store import VectorMetadataStore


@pytest.fixture()
def store(tmp_path, monkeypatch):
    """VectorStoreManager on a temp path, with a fake embedder (no model dl)."""
    cfg = VectorStoreConfig(
        index_path=str(tmp_path / "vector_index"),
        index_type="Flat",
    )
    monkeypatch.setattr("app.vectorstore.config.VectorStoreConfig", VectorStoreConfig)
    mgr = VectorStoreManager.__new__(VectorStoreManager)
    mgr.config = cfg
    from app.vectorstore.chunker import DocumentChunker
    mgr.chunker = DocumentChunker()
    mgr.embedding_pipeline = _FakeEmbedder(cfg)
    mgr.index_builder = __import__(
        "app.vectorstore.index_builder", fromlist=["FAISSIndexBuilder"]
    ).FAISSIndexBuilder(cfg)
    mgr.metadata_store = VectorMetadataStore(cfg.metadata_db_path)
    from app.vectorstore.retriever import Retriever
    mgr.retriever = Retriever(
        config=cfg,
        index=mgr.index_builder,
        metadata_store=mgr.metadata_store,
        embedding_pipeline=mgr.embedding_pipeline,
    )
    mgr._initialized = False
    mgr.initialize()
    return mgr


class _FakeEmbedder:
    """Deterministic bag-of-words embedder — real model not needed for sync tests."""

    def __init__(self, cfg):
        self.config = cfg
        self._dimension = cfg.embedding_dimension
        self._vocab = {}

    def _vec(self, text):
        v = np.zeros(self._dimension, dtype=np.float32)
        for w in text.lower().split():
            h = hash(w) % self._dimension
            v[h] += 1.0
        n = np.linalg.norm(v)
        return v / n if n else v

    def embed_texts(self, texts, batch_size=32, show_progress=False):
        return np.stack([self._vec(t) for t in texts])

    def embed_single(self, text):
        return self._vec(text)

    def unload_model(self):
        pass


def _assert_sync(mgr):
    assert mgr.index_builder.total_vectors == mgr.metadata_store.get_total_embeddings(), (
        f"FAISS ({mgr.index_builder.total_vectors}) vs metadata "
        f"({mgr.metadata_store.get_total_embeddings()}) desync"
    )


def test_ingest_delete_reingest_stays_in_sync(store):
    d1 = store.ingest_text("Alpha doc about foxes. Foxes are quick.", "alpha.txt")
    d2 = store.ingest_text("Beta doc about rockets. Rockets need fuel.", "beta.txt")
    _assert_sync(store)

    store.delete_document(d1)
    _assert_sync(store)

    # Re-ingest after delete — used to collide with stale FAISS slots
    store.ingest_text("Gamma doc about oceans. Whales live there.", "gamma.txt")
    _assert_sync(store)

    res = store.search("what do rockets need?", top_k=1)
    assert len(res) == 1
    assert "rocket" in res[0].content.lower()
    assert res[0].metadata.get("filename") == "beta.txt"


def test_rebuild_maps_vector_indices_cumulatively(store):
    store.ingest_text("One about whales in oceans.", "a.txt")
    store.ingest_text("Two about rockets in space.", "b.txt")
    store.ingest_text("Three about deserts and sand.", "c.txt")
    _assert_sync(store)

    store.rebuild_index()
    _assert_sync(store)

    for q, word in [("whales", "whale"), ("rockets", "rocket"), ("deserts", "desert")]:
        res = store.search(f"tell me about {q}", top_k=1)
        assert len(res) == 1, f"query {q!r} returned nothing after rebuild"
        assert word in res[0].content.lower()


def test_startup_self_heal_repairs_desync(store):
    d1 = store.ingest_text("Alpha doc about foxes. Foxes are quick.", "alpha.txt")
    d2 = store.ingest_text("Beta doc about rockets. Rockets need fuel.", "beta.txt")

    # Simulate the historical poisoning: orphan vector in FAISS, no metadata row
    store.index_builder.add_vectors(store.embedding_pipeline.embed_texts(["orphan"]))
    assert store.index_builder.total_vectors != store.metadata_store.get_total_embeddings()

    # Fresh manager on same path — startup self-heal must repair
    fresh = VectorStoreManager.__new__(VectorStoreManager)
    fresh.config = store.config
    fresh.chunker = store.chunker
    fresh.embedding_pipeline = store.embedding_pipeline
    fresh.index_builder = __import__(
        "app.vectorstore.index_builder", fromlist=["FAISSIndexBuilder"]
    ).FAISSIndexBuilder(store.config)
    fresh.metadata_store = VectorMetadataStore(store.config.metadata_db_path)
    from app.vectorstore.retriever import Retriever
    fresh.retriever = Retriever(
        config=store.config,
        index=fresh.index_builder,
        metadata_store=fresh.metadata_store,
        embedding_pipeline=fresh.embedding_pipeline,
    )
    fresh._initialized = False
    fresh.initialize()

    _assert_sync(fresh)
    res = fresh.search("what do rockets need?", top_k=1)
    assert len(res) == 1
    assert "rocket" in res[0].content.lower()


def test_delete_all_then_ingest(store):
    d1 = store.ingest_text("Alpha doc about foxes.", "alpha.txt")
    d2 = store.ingest_text("Beta doc about rockets.", "beta.txt")
    store.delete_document(d1)
    store.delete_document(d2)
    assert store.index_builder.total_vectors == 0
    assert store.metadata_store.get_total_embeddings() == 0

    store.ingest_text("Zulu final doc. Chimpanzees use tools.", "zulu.txt")
    res = store.search("which animal uses tools?", top_k=1)
    assert len(res) == 1
    assert "chimpanzee" in res[0].content.lower()
