"""Content-hash dedup: store-level hash lookup + end-to-end ingest skip."""

import numpy as np
import pytest

from app.schemas.vector_schemas import TextChunk
from app.vectorstore.store import VectorMetadataStore
from app.vectorstore.config import VectorStoreConfig
from app.vectorstore.manager import VectorStoreManager


@pytest.fixture
def store(tmp_path):
    s = VectorMetadataStore(str(tmp_path / "meta.db"))
    yield s
    s.close()


def _chunk(doc_id, idx, content):
    return TextChunk(
        chunk_id=f"{doc_id}_chunk_{idx:06d}",
        document_id=doc_id,
        content=content,
        chunk_index=idx,
        start_char=0,
        end_char=len(content),
    )


def test_content_hash_deterministic(store):
    assert store.content_hash("hello") == store.content_hash("hello")
    assert store.content_hash("hello") != store.content_hash("hellO")


def test_insert_stores_hash(store):
    c = _chunk("d1", 0, "unique chunk content")
    store.insert_chunks_batch([c])
    h = store.content_hash("unique chunk content")
    assert store.get_existing_hashes([h]) == {h}
    assert store.get_existing_hashes(["deadbeef"]) == set()


def test_existing_hashes_batch_over_500(store):
    """SQLite var limit: 600 hashes queried in chunks must not drop any."""
    chunks = [_chunk("d1", i, f"content-{i}") for i in range(600)]
    store.insert_chunks_batch(chunks)
    hashes = [store.content_hash(c.content) for c in chunks]
    hashes.append(store.content_hash("never-inserted"))
    found = store.get_existing_hashes(hashes)
    assert len(found) == 600
    assert store.content_hash("never-inserted") not in found


def _make_manager(tmp_path):
    cfg = VectorStoreConfig(
        index_path=str(tmp_path / "vectors"),
        embedding_model="paraphrase-albert-small-v1",  # never loaded: dedup short-circuits first
        embedding_dimension=4,
        index_type="Flat",
    )
    return VectorStoreManager(config=cfg)


def _stub_embedder(vs, monkeypatch):
    """Replace the real (offline-raising) embedder with a deterministic one.
    Dimension 4 matches the test config's embedding_dimension."""
    monkeypatch.setattr(
        vs.embedding_pipeline, "embed_texts",
        lambda texts, **kw: np.ones((len(texts), 4), dtype=np.float32),
    )


def test_ingest_skips_all_duplicate_content(tmp_path, monkeypatch):
    """Same text twice → same document id, second ingest indexes nothing new."""
    vs = _make_manager(tmp_path)
    vs.initialize()
    _stub_embedder(vs, monkeypatch)
    text = "Alpha beta gamma delta epsilon zeta. " * 30
    doc1 = vs.ingest_text(text, "a.txt")
    chunks1 = len(vs.get_document_chunks(doc1))
    assert chunks1 > 0

    # Bypass the deterministic-id short-circuit by renaming the document,
    # content identical → every chunk is a duplicate.
    doc2 = vs.ingest_text(text, "b.txt")
    assert doc2 == doc1  # same content hash → same generated id
    # Nothing new was embedded for the duplicate upload
    assert vs.metadata_store.get_total_embeddings() == chunks1
    vs.shutdown()


def test_dedup_renumbers_chunks(tmp_path, monkeypatch):
    """After dropping duplicates, chunk ids/indexes stay dense (0..n-1)."""
    vs = _make_manager(tmp_path)
    vs.initialize()
    _stub_embedder(vs, monkeypatch)
    dup = "Repeated sentence for dedup testing. " * 10
    unique_a = "Document one unique tail content. " * 10
    unique_b = "Document two unique tail content. " * 10

    doc1 = vs.ingest_text(dup + unique_a, "one.txt")
    doc2 = vs.ingest_text(unique_b + dup, "two.txt")
    assert doc2 != doc1

    idxs = [c["chunk_index"] for c in vs.get_document_chunks(doc2)]
    assert idxs == list(range(len(idxs)))
    assert vs.get_document_chunks(doc2)[0]["chunk_id"].endswith("_chunk_000000")
    vs.shutdown()
