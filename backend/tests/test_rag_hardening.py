"""Regression tests for the RAG defects reproduced before the fix.

Each test maps to a root cause found by running the pipeline, not by reading it:

1. Concurrent uploads corrupted the store. Ingest is a read-modify-write across
   FAISS and SQLite with nothing serializing it, so parallel uploads claimed the
   same vector slots. Measured before the fix: 8 parallel uploads left 24 FAISS
   vectors against 3 metadata rows, and 4 of the 8 documents could not be
   retrieved at all.
2. Ingesting content whose every chunk was already indexed raised
   ``ValueError: not enough values to unpack`` from ``zip(*[])`` — a 500 on a
   legitimate re-upload.
3. A failing embedder left the chunk rows already committed (they were written
   before embedding). Those chunks listed as a document but were unreachable by
   search, and the health check called the store "in sync" because it only
   compared FAISS against embedding rows.
4. An embedding-model change surfaced as a bare FAISS ``AssertionError`` with an
   empty message.

Fixtures are inline and use a deterministic fake embedder (no model download),
matching the existing per-file fake-engine pattern in this suite.
"""

import json
import threading
import zlib

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.schemas.vector_schemas import TextChunk
from app.vectorstore.config import VectorStoreConfig
from app.vectorstore.manager import VectorStoreManager


# 512 buckets keeps bag-of-words hash collisions well below the 0.15 score
# floor, so a wrong-document match in these tests is a real regression rather
# than embedder noise.
DIM = 512


class _FakeEmbedder:
    """Bag-of-words embedder, L2-normalized, deterministic across processes.

    zlib.crc32 rather than hash(): Python's str hash is salted per process, so
    hash() would make word->bucket placement vary per test run.
    """

    def __init__(self, dimension=DIM):
        self._dimension = dimension

    def _vec(self, text):
        v = np.zeros(self._dimension, dtype=np.float32)
        for w in text.lower().split():
            w = w.strip(".,!?;:")
            if w:
                v[zlib.crc32(w.encode()) % self._dimension] += 1.0
        n = np.linalg.norm(v)
        return v / n if n else v

    def embed_texts(self, texts, batch_size=32, show_progress=False):
        return np.stack([self._vec(t) for t in texts])

    def embed_single(self, text):
        return self._vec(text)

    def unload_model(self):
        pass

    @property
    def dimension(self):
        return self._dimension


def _manager(tmp_path, dimension=DIM):
    """A manager on a temp path whose embedder is the fake one.

    The fake is installed on the existing pipeline object (not swapped in), so
    the retriever — built in __init__ holding that same reference — sees it too.
    """
    cfg = VectorStoreConfig(
        index_path=str(tmp_path / "vector_index"),
        embedding_dimension=dimension,
        index_type="Flat",
    )
    vs = VectorStoreManager(config=cfg)
    fake = _FakeEmbedder(dimension)
    vs.embedding_pipeline.embed_texts = fake.embed_texts
    vs.embedding_pipeline.embed_single = fake.embed_single
    vs.embedding_pipeline.unload_model = fake.unload_model
    vs.initialize()
    return vs


# --------------------------------------------------------------------------- #
# 1. Concurrent ingest
# --------------------------------------------------------------------------- #

def test_concurrent_ingest_keeps_store_retrievable(tmp_path):
    """Parallel uploads must not clobber each other's vector slots."""
    vs = _manager(tmp_path)
    try:
        def upload(i):
            vs.ingest_text(
                f"Document number {i} about topic alpha{i} beta{i}. " * 30,
                f"doc{i}.txt",
            )

        threads = [threading.Thread(target=upload, args=(i,)) for i in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        stats = vs.get_stats()
        assert stats["total_vectors"] == stats["total_embeddings"], stats
        assert stats["total_chunks"] == stats["total_embeddings"], stats
        assert stats["in_sync"] is True, stats

        # Every document must still be findable by its own unique token.
        for i in range(8):
            hits = vs.search(f"alpha{i}", top_k=1)
            assert hits, f"doc{i} became unretrievable"
            assert hits[0].metadata["filename"] == f"doc{i}.txt"
    finally:
        vs.shutdown()


def test_concurrent_ingest_does_not_lose_documents(tmp_path):
    """Same race, asserting the document list agrees with what is retrievable."""
    vs = _manager(tmp_path)
    try:
        def upload(i):
            vs.ingest_text(f"Unique subject omega{i} repeated. " * 25, f"f{i}.txt")

        threads = [threading.Thread(target=upload, args=(i,)) for i in range(6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        listed = vs.list_documents()
        assert len(listed) == 6
        retrievable = [
            d for i, d in enumerate(sorted(listed, key=lambda x: x["filename"]))
            if any(h.document_id == d["id"] for h in vs.search(f"omega{i}", top_k=1))
        ]
        assert len(retrievable) == len(listed)
    finally:
        vs.shutdown()


# --------------------------------------------------------------------------- #
# 2. All-duplicate ingest
# --------------------------------------------------------------------------- #

def test_all_duplicate_chunks_do_not_raise(tmp_path):
    """A re-upload whose every chunk already exists must index nothing, not 500."""
    vs = _manager(tmp_path)
    try:
        text = "Alpha beta gamma delta. " * 40

        # Pre-seed the exact chunk hashes this text produces, under another
        # document id — i.e. the content is already indexed elsewhere.
        probe = vs.chunker.chunk_text(text, "seed_doc")
        assert probe
        for i, c in enumerate(probe):
            c.chunk_id = f"seed_doc_chunk_{i:06d}"
            c.document_id = "seed_doc"
        vs.metadata_store.insert_chunks_batch(probe)

        before = vs.metadata_store.get_total_embeddings()
        doc_id = vs.ingest_text(text, "reupload.txt")   # used to raise ValueError

        assert doc_id
        assert vs.metadata_store.get_total_embeddings() == before
        # (in_sync is not asserted here: the pre-seeded chunk rows above are
        # deliberate orphans, so it is correctly False.)
    finally:
        vs.shutdown()


# --------------------------------------------------------------------------- #
# 3. Orphan chunks
# --------------------------------------------------------------------------- #

def test_embedding_failure_commits_nothing(tmp_path):
    """A failed embedder must leave no chunk rows behind."""
    vs = _manager(tmp_path)
    try:
        def boom(texts, **kw):
            raise RuntimeError("embedding model unavailable")

        vs.embedding_pipeline.embed_texts = boom

        with pytest.raises(RuntimeError, match="unavailable"):
            vs.ingest_text("Some document about something. " * 20, "crash.txt")

        stats = vs.get_stats()
        assert stats["total_chunks"] == 0, "chunk rows were committed before embedding"
        assert stats["orphan_chunks"] == 0
        assert stats["in_sync"] is True
        assert vs.list_documents() == [], "a phantom document survived a failed ingest"
    finally:
        vs.shutdown()


def test_orphan_chunks_are_repaired_at_startup(tmp_path):
    """Chunk rows with no embedding row must be re-embedded by the self-heal."""
    vs = _manager(tmp_path)
    try:
        # Simulate the crash: chunk rows written, embedding rows never written.
        vs.metadata_store.insert_chunks_batch([TextChunk(
            chunk_id="orphan_chunk_000000",
            document_id="orphan_doc",
            content="Lonely facts about penguins and icebergs.",
            chunk_index=0,
            start_char=0,
            end_char=40,
            metadata={"filename": "orphan.txt"},
        )])
        assert vs.metadata_store.get_orphan_chunk_count() == 1
        stats = vs.get_stats()
        assert stats["in_sync"] is False, "orphan chunks must not read as in sync"
        assert stats["orphan_chunks"] == 1
    finally:
        vs.shutdown()

    # A fresh manager on the same path repairs it on startup.
    revived = _manager(tmp_path)
    try:
        assert revived.metadata_store.get_orphan_chunk_count() == 0
        assert revived.get_stats()["in_sync"] is True
        hits = revived.search("penguins icebergs", top_k=1)
        assert hits and hits[0].metadata["filename"] == "orphan.txt"
    finally:
        revived.shutdown()


# --------------------------------------------------------------------------- #
# 4. Embedding-model / dimension change
# --------------------------------------------------------------------------- #

def test_dimension_change_is_reported_not_asserted(tmp_path):
    """Writing wider vectors must name both widths, not raise a bare assert."""
    vs = _manager(tmp_path)
    try:
        vs.ingest_text("Baseline document about rivers and valleys. " * 20, "a.txt")
        index_dim = vs.index_builder.dimension
        assert index_dim == DIM

        # The embedding model is swapped for a wider one.
        vs.embedding_pipeline.embed_texts = _FakeEmbedder(DIM * 2).embed_texts

        with pytest.raises(RuntimeError) as exc:
            vs.ingest_text("Another document about mountains and peaks. " * 20, "b.txt")
        message = str(exc.value)
        assert str(index_dim) in message and str(DIM * 2) in message
        assert "/v1/rag/rebuild" in message
    finally:
        vs.shutdown()


def test_rebuild_adopts_the_new_embedding_width(tmp_path):
    """Rebuild is the escape hatch for a changed embedding model."""
    vs = _manager(tmp_path)
    try:
        vs.ingest_text("Document about rivers and valleys. " * 20, "a.txt")

        wider = _FakeEmbedder(DIM * 2)
        vs.embedding_pipeline.embed_texts = wider.embed_texts
        vs.embedding_pipeline.embed_single = wider.embed_single

        vs.rebuild_index()

        assert vs.index_builder.dimension == DIM * 2
        assert vs.config.embedding_dimension == DIM * 2
        stats = vs.get_stats()
        assert stats["in_sync"] is True, stats
        assert vs.search("rivers valleys", top_k=1)

        # The store is usable again at the new width.
        vs.ingest_text("More about rivers and valleys and bridges. " * 20, "b.txt")
        assert vs.get_stats()["in_sync"] is True
    finally:
        vs.shutdown()


def test_index_records_its_embedding_model(tmp_path):
    """A recorded model name is what makes a later model change detectable."""
    vs = _manager(tmp_path)
    try:
        vs.ingest_text("Document about rivers. " * 20, "a.txt")
        assert vs.metadata_store.get_state("embedding_model") == vs.config.embedding_model
        assert vs.get_stats()["index_embedding_model"] == vs.config.embedding_model
    finally:
        vs.shutdown()


# --------------------------------------------------------------------------- #
# 5. Privacy: query text must not reach the logs
# --------------------------------------------------------------------------- #

def test_search_logs_no_query_text(tmp_path, caplog):
    vs = _manager(tmp_path)
    try:
        secret = "PROJECT-BLACKBIRD-CONFIDENTIAL-PHRASE"
        vs.ingest_text(f"{secret} appears in this document about contracts. " * 20, "c.txt")

        with caplog.at_level("DEBUG"):
            vs.search(secret, top_k=3)

        blob = "\n".join(r.getMessage() for r in caplog.records)
        assert secret not in blob, "the query text leaked into the logs"
    finally:
        vs.shutdown()


# --------------------------------------------------------------------------- #
# 6. Degraded mode: no vector store
# --------------------------------------------------------------------------- #

@pytest.fixture()
def client():
    # No context manager: skips lifespan, so app.state is ours to wire.
    from app.main import app
    return TestClient(app)


@pytest.mark.parametrize("method,path", [
    ("get", "/v1/rag/stats"),
    ("get", "/v1/rag/documents"),
    ("get", "/v1/rag/documents/whatever/chunks"),
    ("post", "/v1/rag/rebuild"),
    ("delete", "/v1/rag/documents/whatever"),
])
def test_rag_endpoints_report_503_without_a_store(client, method, path):
    """An unavailable RAG store is a 503, never an AttributeError 500."""
    from app.main import app
    app.state.vector_store = None
    response = getattr(client, method)(path)
    assert response.status_code == 503
    # The app renders HTTPException through the OpenAI-shaped error handler.
    assert "Vector store" in response.text


def test_stats_reports_orphan_chunks_and_sync(client, tmp_path):
    vs = _manager(tmp_path)
    try:
        from app.main import app
        app.state.vector_store = vs
        vs.ingest_text("A document about telescopes and optics. " * 20, "t.txt")
        body = client.get("/v1/rag/stats").json()
        assert body["in_sync"] is True
        assert body["orphan_chunks"] == 0
        assert body["index_dimension"] == DIM
    finally:
        from app.main import app
        app.state.vector_store = None
        vs.shutdown()


# --------------------------------------------------------------------------- #
# 7. Persistence across a restart
# --------------------------------------------------------------------------- #

def test_documents_survive_a_restart(tmp_path):
    """Ingest, drop the manager, rebuild one on the same path, still retrieve."""
    first = _manager(tmp_path)
    try:
        first.ingest_text("Alpha about foxes and woodlands. " * 20, "alpha.txt")
        first.ingest_text("Beta about rockets and fuel. " * 20, "beta.txt")
        assert len(first.list_documents()) == 2
    finally:
        first.shutdown()

    second = _manager(tmp_path)
    try:
        assert len(second.list_documents()) == 2
        stats = second.get_stats()
        assert stats["in_sync"] is True, stats
        hits = second.search("rockets fuel", top_k=1)
        assert hits and hits[0].metadata["filename"] == "beta.txt"
    finally:
        second.shutdown()


def test_delete_is_reflected_in_retrieval(tmp_path):
    vs = _manager(tmp_path)
    try:
        d1 = vs.ingest_text("Alpha about foxes and woodlands. " * 20, "alpha.txt")
        d2 = vs.ingest_text("Beta about rockets and fuel. " * 20, "beta.txt")

        vs.delete_document(d1)

        assert [d["id"] for d in vs.list_documents()] == [d2]
        # The deleted document must stop surfacing anywhere in the results.
        for r in vs.search("foxes woodlands", top_k=5):
            assert r.document_id != d1
        hits = vs.search("rockets fuel", top_k=1)
        assert hits and hits[0].document_id == d2
        assert vs.get_stats()["in_sync"] is True
    finally:
        vs.shutdown()


# --------------------------------------------------------------------------- #
# 8. Online provider: retrieved context must reach the configured model
# --------------------------------------------------------------------------- #

class _FakeCloudResponse:
    def __init__(self, status, json_data=None):
        self.status = status
        self._json = json_data or {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def json(self):
        return self._json

    async def text(self):
        return json.dumps(self._json)


class _FakeCloudSession:
    """Mimics aiohttp: post() returns an async context manager."""

    def __init__(self, response):
        self._response = response
        self.posts = []

    def post(self, url, headers=None, json=None, **kwargs):
        self.posts.append({"url": url, "headers": headers, "json": json})
        return self._response


def test_retrieved_context_reaches_the_cloud_provider(client, tmp_path):
    """The online path must receive the same labeled evidence the local path does.

    RAG hands the prompt to whatever engine is active; a cloud provider is just
    another BaseEngine. This asserts the retrieved excerpts (with their
    [Source: file#chunk] labels) are in the request body actually sent upstream,
    that citations come back verified against the retrieved chunks, and that the
    provider key does not leak into the API response.
    """
    from app.engines.cloud.engine import CloudAPIEngine
    from app.main import app

    vs = _manager(tmp_path)
    app.state.vector_store = vs
    try:
        vs.ingest_text("Evidence must be retained for seven years. " * 20, "policy.pdf")

        engine = CloudAPIEngine(
            model_path="openai/gpt-4o",
            hardware={},
            memory_manager=None,
            provider={
                "name": "OpenAI", "provider_type": "openai",
                "api_key": "sk-test-secret", "base_url": None,
            },
            model_id="gpt-4o",
        )
        engine.loaded = True
        session = _FakeCloudSession(_FakeCloudResponse(200, json_data={
            "choices": [{
                "message": {"content": "Seven years [Source: policy.pdf#0]."},
                "finish_reason": "stop",
            }],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }))
        engine._http = session
        app.state.active_engine = engine

        response = client.post(
            "/v1/rag/query",
            json={"query": "how long must evidence be retained?", "top_k": 3},
        )
        assert response.status_code == 200, response.text
        body = response.json()

        sent = json.dumps(session.posts[0]["json"])
        assert session.posts, "the cloud provider was never called"
        assert "[Source: policy.pdf#" in sent, (
            "retrieved evidence never reached the online model"
        )
        assert "seven years" in sent.lower()

        assert body["generated_response"]
        assert body["citations"], "the grounded citation was not verified"
        assert body["citations"][0]["filename"] == "policy.pdf"
        assert "retained for seven years" in body["citations"][0]["quote"].lower()

        # The provider credential must never reach the client.
        assert "sk-test-secret" not in response.text
    finally:
        from app.main import app as _app
        _app.state.vector_store = None
        _app.state.active_engine = None
        vs.shutdown()


def test_query_without_evidence_does_not_call_a_cloud_provider(client, tmp_path):
    """No retrieved evidence means no upstream request (no cost, no fabrication)."""
    from app.engines.cloud.engine import CloudAPIEngine
    from app.main import app

    vs = _manager(tmp_path)
    app.state.vector_store = vs
    try:
        engine = CloudAPIEngine(
            model_path="openai/gpt-4o", hardware={}, memory_manager=None,
            provider={"name": "OpenAI", "provider_type": "openai",
                      "api_key": "sk-test-secret", "base_url": None},
            model_id="gpt-4o",
        )
        engine.loaded = True
        session = _FakeCloudSession(_FakeCloudResponse(200, json_data={}))
        engine._http = session
        app.state.active_engine = engine

        response = client.post("/v1/rag/query", json={"query": "unanswerable question"})
        assert response.status_code == 200
        body = response.json()
        assert body["insufficient_evidence"] is True
        assert body["generated_response"] is None
        assert session.posts == [], "an empty context still hit the paid API"
    finally:
        from app.main import app as _app
        _app.state.vector_store = None
        _app.state.active_engine = None
        vs.shutdown()


def test_delete_unknown_document_raises_value_error(tmp_path):
    vs = _manager(tmp_path)
    try:
        vs.ingest_text("Alpha about foxes and woodlands. " * 20, "alpha.txt")
        with pytest.raises(ValueError):
            vs.delete_document("doc_does_not_exist")
        # The failed delete must not have damaged the index.
        assert vs.get_stats()["in_sync"] is True
        hits = vs.search("foxes woodlands", top_k=1)
        assert hits and "foxes" in hits[0].content.lower()
    finally:
        vs.shutdown()
