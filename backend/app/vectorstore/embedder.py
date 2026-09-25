"""Embedding import surface.

The implementation lives in ``app.vectorstore.embedding_pipeline`` (a
sentence-transformers wrapper with lazy model loading and dimension
verification); this module re-exports it so
``from app.vectorstore.embedder import EmbeddingPipeline`` is the stable import
path. Previously a zero-byte file, which made that import fail with a bare
``ImportError`` and no hint where the code had gone.
"""

from app.vectorstore.embedding_pipeline import EmbeddingPipeline

__all__ = ["EmbeddingPipeline"]
