"""Citation verification + insufficient-evidence handling for POST /v1/rag/query.

TestClient is used WITHOUT a context manager on purpose (no lifespan, no
workspace side effects) — app.state is wired explicitly, same as
test_chat_api_http.py.
"""

import pytest
from fastapi.testclient import TestClient

from app.api.rag import _verify_citations
from app.main import app
from app.schemas.vector_schemas import RAGContext, SearchResult


def _result(chunk_index, filename, content="Evidence must be retained for 7 years.",
            doc_id="doc_1", score=0.9):
    return SearchResult(
        chunk_id=f"{doc_id}_chunk_{chunk_index:06d}",
        document_id=doc_id,
        content=content,
        score=score,
        chunk_index=chunk_index,
        metadata={"filename": filename},
    )


class _FakeVS:
    """Returns a fixed result set; records the query it was asked for."""

    def __init__(self, results):
        self._results = results
        self.queries = []

    def build_context(self, query_text, top_k=5, max_tokens=2048, score_threshold=0.0):
        self.queries.append(query_text)
        return RAGContext(
            query=query_text,
            results=self._results,
            total_tokens=7,
            context_text="\n\n".join(r.content for r in self._results),
        )


class _FakeEngine:
    def __init__(self, answer="ok"):
        self.answer = answer
        self.calls = []

    async def generate(self, input_data, **kwargs):
        self.calls.append((input_data, kwargs))
        return {"output": self.answer}


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture()
def wire():
    """Wire fakes into the real app.state, clean up after."""

    def _wire(vs, engine):
        app.state.vector_store = vs
        app.state.active_engine = engine
        return engine

    yield _wire
    app.state.vector_store = None
    app.state.active_engine = None


# --- _verify_citations unit ---

def test_verify_citations_keeps_only_retrieved_sources():
    results = [_result(3, "policy.pdf"), _result(7, "policy.pdf", doc_id="doc_2")]
    answer = "Required [Source: policy.pdf#3]. Also [Source: policy.pdf#7]."
    cites, unverified = _verify_citations(answer, results)
    assert [c["chunk_index"] for c in cites] == [3, 7]
    assert unverified == 0


def test_verify_citations_drops_fabricated_source():
    """A clause the model names but we never retrieved must not be echoed."""
    results = [_result(3, "policy.pdf")]
    answer = "Per the regulation [Source: gdpr.pdf#99] evidence is required."
    cites, unverified = _verify_citations(answer, results)
    assert cites == []
    assert unverified == 1


def test_verify_citations_deduplicates_repeats():
    results = [_result(3, "policy.pdf")]
    answer = "[Source: policy.pdf#3] ... [Source: policy.pdf#3]"
    cites, unverified = _verify_citations(answer, results)
    assert len(cites) == 1
    assert unverified == 0  # a repeat is not an unverified citation


def test_verify_citations_quote_comes_from_retrieved_chunk():
    results = [_result(3, "policy.pdf", content="Retain records for seven years.")]
    cites, _ = _verify_citations("[Source: policy.pdf#3]", results)
    assert cites[0]["quote"] == "Retain records for seven years."
    assert cites[0]["document_id"] == "doc_1"


def test_verify_citations_tolerates_no_answer():
    assert _verify_citations("", [_result(3, "policy.pdf")]) == ([], 0)
    assert _verify_citations(None, []) == ([], 0)


# --- endpoint behavior ---

def test_query_without_evidence_skips_generation(client, wire):
    engine = wire(_FakeVS([]), _FakeEngine("I made this up."))
    r = client.post("/v1/rag/query", json={"query": "what evidence is required?"})
    assert r.status_code == 200

    body = r.json()
    assert body["insufficient_evidence"] is True
    assert body["generated_response"] is None
    assert body["citations"] == []
    assert engine.calls == []  # no LLM call burned on an empty context


def test_query_returns_only_verified_citations(client, wire):
    engine = wire(
        _FakeVS([_result(3, "policy.pdf")]),
        _FakeEngine(
            "Evidence is required [Source: policy.pdf#3]. "
            "See also [Source: made_up.pdf#1]."
        ),
    )
    r = client.post("/v1/rag/query", json={"query": "what evidence?"})
    assert r.status_code == 200

    body = r.json()
    assert body["insufficient_evidence"] is False
    assert body["unverified_citation_count"] == 1
    assert len(body["citations"]) == 1
    assert body["citations"][0]["filename"] == "policy.pdf"
    assert body["citations"][0]["chunk_index"] == 3
    assert len(engine.calls) == 1


def test_query_without_generation_does_not_call_the_engine(client, wire):
    """generate_response=false is retrieval-only — no generation spent."""
    engine = wire(_FakeVS([_result(3, "policy.pdf")]), _FakeEngine("unused"))
    r = client.post("/v1/rag/query",
                    json={"query": "evidence?", "generate_response": False})
    assert r.status_code == 200
    body = r.json()
    assert body["generated_response"] is None
    assert body["insufficient_evidence"] is False
    assert len(body["results"]) == 1
    assert engine.calls == []


def test_query_without_engine_still_retrieves(client, wire):
    """No model loaded → retrieval still answers, not a 500."""
    wire(_FakeVS([_result(3, "policy.pdf")]), None)
    r = client.post("/v1/rag/query", json={"query": "evidence?"})
    assert r.status_code == 200
    body = r.json()
    assert body["generated_response"] is None
    assert len(body["results"]) == 1
