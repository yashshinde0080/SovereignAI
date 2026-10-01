"""Retrieval quality tests: min-score floor, MMR, source labels, offline
embedder flags. Uses a deterministic fake embedder (no model download)."""

import os
import sys
import types
import hashlib

import numpy as np
import pytest

from app.vectorstore.config import VectorStoreConfig
from app.vectorstore.index_builder import FAISSIndexBuilder
from app.vectorstore.store import VectorMetadataStore
from app.vectorstore.retriever import Retriever
from app.schemas.vector_schemas import (
    SearchQuery, TextChunk, EmbeddingRecord,
)


class FakeEmbedder:
    """Bag-of-words md5-hash embedder, L2-normalized. Deterministic per process.
    1024 buckets keeps hash-collision noise below the 0.15 min-score floor."""

    dimension = 1024

    def embed_single(self, text: str) -> np.ndarray:
        vec = np.zeros(self.dimension, dtype=np.float32)
        for word in text.lower().split():
            idx = int(hashlib.md5(word.encode()).hexdigest(), 16) % self.dimension
            vec[idx] += 1.0
        norm = np.linalg.norm(vec)
        return vec / norm if norm else vec

    def embed_texts(self, texts, batch_size=32, show_progress=False):
        return np.stack([self.embed_single(t) for t in texts])


@pytest.fixture
def vs_parts(tmp_path):
    cfg = VectorStoreConfig(
        index_path=str(tmp_path / "vectors"),
        embedding_dimension=FakeEmbedder.dimension,
        index_type="Flat",
    )
    index = FAISSIndexBuilder(cfg)
    index.create_index()
    store = VectorMetadataStore(cfg.metadata_db_path)
    retriever = Retriever(
        config=cfg, index=index, metadata_store=store,
        embedding_pipeline=FakeEmbedder(),
    )
    return cfg, index, store, retriever


def _seed(index, store, docs: dict):
    """docs: {doc_id: [(filename, [chunk_texts])]}. Adds chunks + vectors."""
    records, vecs, pos = [], [], 0
    for doc_id, (filename, chunks) in docs.items():
        for i, content in enumerate(chunks):
            cid = f"{doc_id}_chunk_{i:06d}"
            store.insert_chunks_batch([TextChunk(
                chunk_id=cid, document_id=doc_id, content=content,
                chunk_index=i, start_char=0, end_char=len(content),
                metadata={"filename": filename},
            )])
            records.append(EmbeddingRecord(
                embedding_id=f"{cid}_emb", chunk_id=cid, document_id=doc_id,
                vector_index=pos, dimension=FakeEmbedder.dimension, norm=1.0,
            ))
            store.insert_embeddings_batch([records[-1]])
            pos += 1
    index.add_vectors(np.stack([FakeEmbedder().embed_single(c)
                                for _, (_, cs) in docs.items() for c in cs]))


def test_min_score_floor_filters_junk(vs_parts):
    cfg, index, store, retriever = vs_parts
    _seed(index, store, {"d1": ("notes.txt", ["the cat sat on the mat"])})
    # Unrelated query scores low → floor (0.15) removes it
    results = retriever.search(SearchQuery(query_text="quantum entanglement physics"))
    assert results == []


def test_explicit_threshold_stricter_than_floor(vs_parts):
    cfg, index, store, retriever = vs_parts
    _seed(index, store, {"d1": ("notes.txt", ["the cat sat on the mat"])})
    # "the cat" partially matches (sim ~0.75): floor keeps it, 0.99 drops it
    loose = retriever.search(SearchQuery(query_text="the cat"))
    assert len(loose) == 1
    strict = retriever.search(SearchQuery(
        query_text="the cat", score_threshold=0.99))
    assert strict == []


def test_search_ranks_closest_first(vs_parts):
    cfg, index, store, retriever = vs_parts
    _seed(index, store, {"d1": ("zoo.txt", [
        "the cat sat on the mat",
        "quantum physics describes atoms and particles",
        "python is a programming language",
    ])})
    results = retriever.search(SearchQuery(query_text="cat sat mat"))
    assert results[0].content == "the cat sat on the mat"
    assert all(r.score >= cfg.min_score for r in results)


def test_mmr_caps_results_at_top_k(vs_parts):
    cfg, index, store, retriever = vs_parts
    _seed(index, store, {"d1": ("zoo.txt", [
        f"document number {i} about aviation and airplanes flying high"
        for i in range(10)
    ])})
    results = retriever.search(SearchQuery(query_text="aviation airplanes flying", top_k=3))
    assert len(results) <= 3


def test_source_label_includes_chunk_index(vs_parts):
    cfg, index, store, retriever = vs_parts
    _seed(index, store, {"d1": ("manual.pdf", ["battery lasts fourteen hours on one charge"])})
    ctx = retriever.build_rag_context(SearchQuery(query_text="battery hours charge"))
    assert "[Source: manual.pdf#0]" in ctx.context_text


def test_rag_context_respects_token_budget(vs_parts):
    cfg, index, store, retriever = vs_parts
    _seed(index, store, {"d1": ("big.txt", [f"chunk {i} " + "filler words " * 100 for i in range(5)])})
    ctx = retriever.build_rag_context(SearchQuery(query_text="chunk filler"), max_tokens=120)
    assert ctx.total_tokens <= 120


def test_embedder_load_sets_offline_flags(monkeypatch):
    """load_model must set offline env vars and pass device=cpu +
    local_files_only=True to SentenceTransformer."""
    import app.vectorstore.embedding_pipeline as ep

    captured = {}

    class _StubST:
        def __init__(self, model_name, **kwargs):
            captured.update(kwargs)
            captured["model_name"] = model_name

        def encode(self, texts, **kw):
            return np.zeros((len(texts), 384), dtype=np.float32)

    stub_module = types.ModuleType("sentence_transformers")
    stub_module.SentenceTransformer = _StubST
    monkeypatch.setitem(sys.modules, "sentence_transformers", stub_module)
    monkeypatch.delenv("HF_HUB_OFFLINE", raising=False)
    monkeypatch.delenv("TRANSFORMERS_OFFLINE", raising=False)

    pipe = ep.EmbeddingPipeline(ep.VectorStoreConfig())
    pipe.load_model()

    assert os.environ["HF_HUB_OFFLINE"] == "1"
    assert os.environ["TRANSFORMERS_OFFLINE"] == "1"
    assert captured["device"] == "cpu"
    assert captured["local_files_only"] is True

    pipe.unload_model()
    assert pipe._model is None
