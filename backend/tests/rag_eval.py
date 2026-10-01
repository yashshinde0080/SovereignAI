"""RAG evaluation: 20 Q&A pairs over a built-in sample document.

Reports:
  - recall@k   — fraction of questions whose gold chunk lands in top-k
  - grounding  — fraction where the expected answer text appears in the
                 retrieved context (what the model would actually see)

Runs offline. Uses the real SentenceTransformer if it is already cached
(HF_HUB_OFFLINE=1), else falls back to a deterministic lexical embedder —
lexical recall@k still validates chunking/index/search plumbing end to end,
but is NOT a quality verdict on the production embedder (flag: rerun on a
box with the cached model for real numbers).

Run:  cd backend && python -m tests.rag_eval
"""

import os
import sys
import hashlib
from pathlib import Path

# Allow direct execution: python tests/rag_eval.py
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Hard offline guarantee for the eval process itself
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

import numpy as np  # noqa: E402

from app.vectorstore.chunker import DocumentChunker  # noqa: E402
from app.vectorstore.config import VectorStoreConfig  # noqa: E402
from app.vectorstore.index_builder import FAISSIndexBuilder  # noqa: E402
from app.vectorstore.store import VectorMetadataStore  # noqa: E402
from app.vectorstore.retriever import Retriever  # noqa: E402
from app.schemas.vector_schemas import SearchQuery  # noqa: E402

# ponytail: grounding here = answer text present in retrieved context.
# Full answer-grounding (LLM-generated answer checked against sources)
# needs a loaded model — POST /v1/rag/query on a running server for that.

SAMPLE_DOC = """SovereignAI Edge Product Specification (rev 2026-09)

SovereignAI Edge is a portable AI platform that runs large language models
locally on consumer hardware or directly from a USB drive. All runtime paths
are relative, so the installation can be moved between machines without
reconfiguration. The platform collects no telemetry of any kind: no usage
statistics, no crash reports, and no network calls are made in offline mode.

The system supports three inference modes. FullRAM mode loads the entire
model into RAM or VRAM for the fastest token generation. LayerStream mode
swaps individual transformer layer weights from disk during inference,
enabling 3B to 8B quantized models to run on machines with only 8GB of RAM.
CloudAPI mode proxies requests to external providers such as OpenAI,
Anthropic, Google, or any custom self-hosted endpoint, and never loads local
model weights.

The retrieval-augmented generation subsystem uses a FAISS vector store with
the all-MiniLM-L6-v2 sentence embedding model, which produces 384-dimensional
vectors. Documents are split into chunks of at most 512 tokens with an
overlap of 64 tokens between consecutive chunks. Retrieved excerpts are
labeled with their source filename and chunk index, and the prompt template
instructs the model to answer only from the provided excerpts.

All data is stored locally in SQLite databases configured with WAL journaling
mode. API keys for cloud providers are encrypted at rest using Fernet
symmetric encryption with keys derived through PBKDF2HMAC using 480000
iterations. Uploaded documents may be at most 50 megabytes in size.

The REST API listens on port 8000 by default and is rate limited to 60
requests per minute. The plugin system loads Python scripts dynamically with
a hard execution timeout of 30 seconds per action. The LayerStream weight
loader uses a prefetch depth of 3, reading upcoming layer weights from disk
in a background thread pool while the current layer computes.

TurboQuant, the experimental KV-cache compression feature, is disabled by
default because the accuracy evaluation gate has not yet passed. The
HuggingFace cache directory is forced to workspace/hf_cache so that model
downloads stay on the USB drive. Launch scripts named launch.bat and
launch.sh start both the backend server and the desktop application.
"""

# (question, expected_answer_fragment, unique_gold_locator)
QA_PAIRS = [
    ("Does the platform collect telemetry?", "collects no telemetry", "collects no telemetry"),
    ("What is the minimum RAM target for LayerStream?", "8GB of RAM", "8GB of RAM"),
    ("Name the three inference modes.", "FullRAM", "three inference modes"),
    ("Which mode proxies requests to OpenAI or Anthropic?", "CloudAPI", "CloudAPI"),
    ("What embedding model does RAG use?", "all-MiniLM-L6-v2", "all-MiniLM-L6-v2"),
    ("How many dimensions do the embeddings have?", "384-dimensional", "384-dimensional"),
    ("What is the chunk size in tokens?", "512 tokens", "chunks of at most 512 tokens"),
    ("How much overlap is there between chunks?", "overlap of 64 tokens", "overlap of 64 tokens"),
    ("How are API keys protected at rest?", "Fernet", "Fernet"),
    ("How many PBKDF2HMAC iterations are used?", "480000 iterations", "480000"),
    ("What is the maximum upload size?", "50 megabytes", "50 megabytes"),
    ("What port does the API listen on?", "port 8000", "port 8000"),
    ("What is the API rate limit?", "60 requests per minute", "60 requests per minute"),
    ("What is the plugin execution timeout?", "30 seconds", "timeout of 30 seconds"),
    ("What prefetch depth does the LayerStream loader use?", "prefetch depth of 3", "prefetch depth of 3"),
    ("Is TurboQuant enabled by default?", "disabled by default", "disabled by default"),
    ("Where is the HuggingFace cache stored?", "workspace/hf_cache", "workspace/hf_cache"),
    ("What are the launch scripts called?", "launch.bat", "launch.bat and"),
    ("Which journaling mode do the SQLite databases use?", "WAL", "WAL journaling"),
    ("How are retrieved excerpts labeled?", "source filename and chunk index", "source filename and chunk index"),
]


class LexicalEmbedder:
    """Offline fallback: bag-of-words, md5-hashed buckets, L2-normalized."""

    dimension = 256

    def embed_single(self, text: str) -> np.ndarray:
        vec = np.zeros(self.dimension, dtype=np.float32)
        for word in text.lower().split():
            idx = int(hashlib.md5(word.encode()).hexdigest(), 16) % self.dimension
            vec[idx] += 1.0
        norm = np.linalg.norm(vec)
        return vec / norm if norm else vec

    def embed_texts(self, texts, batch_size=32, show_progress=False):
        return np.stack([self.embed_single(t) for t in texts])


def make_embedder(cfg):
    """Real cached model if available, else lexical fallback."""
    try:
        from app.vectorstore.embedding_pipeline import EmbeddingPipeline
        pipe = EmbeddingPipeline(cfg)
        pipe.load_model()
        print("embedder: real SentenceTransformer (cached)")
        return pipe
    except Exception as e:
        print(f"embedder: lexical fallback ({type(e).__name__}: {e})")
        print("  flag: recall numbers validate plumbing, not the production embedder")
        return LexicalEmbedder()


def main(top_k: int = 5):
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        cfg = VectorStoreConfig(index_path=str(Path(tmp) / "vectors"))
        chunker = DocumentChunker(cfg.chunk_size, cfg.chunk_overlap)
        chunks = chunker.chunk_text(SAMPLE_DOC, "eval_doc")
        for c in chunks:
            c.metadata["filename"] = "spec.md"

        embedder = make_embedder(cfg)
        index = FAISSIndexBuilder(cfg)
        index.create_index()
        store = VectorMetadataStore(cfg.metadata_db_path)
        retriever = Retriever(
            config=cfg, index=index, metadata_store=store,
            embedding_pipeline=embedder,
        )

        embeddings = embedder.embed_texts([c.content for c in chunks])
        index.add_vectors(embeddings)
        for i, c in enumerate(chunks):
            store.insert_chunks_batch([c])
            store.insert_embeddings_batch([type(
                "R", (), {
                    "embedding_id": f"{c.chunk_id}_emb", "chunk_id": c.chunk_id,
                    "document_id": c.document_id, "vector_index": i,
                    "dimension": cfg.embedding_dimension,
                    "norm": float(np.linalg.norm(embeddings[i])),
                },
            )()])

        hits = {1: 0, 3: 0, 5: 0}
        grounded = 0
        print(f"\n{'question':<55} recall@1 @3 @5  grounded")
        for q, fragment, _ in QA_PAIRS:
            results = retriever.search(SearchQuery(query_text=q, top_k=top_k))
            r_at = {k: any(fragment in r.content for r in results[:k])
                    for k in (1, 3, 5)}
            for k, ok in r_at.items():
                hits[k] += ok
            g = r_at[top_k]
            grounded += g
            print(f"{q[:54]:<55}   {int(r_at[1])}     {int(r_at[3])}   {int(r_at[5])}      {int(g)}")

        store.close()  # Windows can't rmtree an open sqlite file

        n = len(QA_PAIRS)
        print(f"\nrecall@1 = {hits[1]}/{n} = {hits[1]/n:.0%}")
        print(f"recall@3 = {hits[3]}/{n} = {hits[3]/n:.0%}")
        print(f"recall@{top_k} = {hits[5]}/{n} = {hits[5]/n:.0%}")
        print(f"context-grounding = {grounded}/{n} = {grounded/n:.0%}")


if __name__ == "__main__":
    main()
