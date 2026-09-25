"""Vector index import surface.

The implementation lives in ``app.vectorstore.index_builder``; this module
re-exports it so ``from app.vectorstore.index import FAISSIndexBuilder`` is the
stable import path. Previously a zero-byte file, which made that import fail
with a bare ``ImportError`` and no hint where the code had gone.
"""

from app.vectorstore.index_builder import FAISSIndexBuilder

__all__ = ["FAISSIndexBuilder"]
