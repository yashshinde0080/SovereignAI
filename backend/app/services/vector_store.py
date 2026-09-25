"""Vector store adapter.

``VectorStoreManager`` (``app.vectorstore.manager``) is the canonical RAG
store: chunking, sentence-transformers embeddings, FAISS indexing and a SQLite
metadata database.

This module used to be a second, independent implementation that persisted to
``index.json`` + ``vectors.npy`` and generated embeddings with
``np.random.seed(hash(text))`` — i.e. it returned random vectors, so every
"similarity" search over it was noise. Any caller that reached it silently got
meaningless results rather than an error, which is the worst failure mode for a
retrieval store.

It is kept as a thin adapter so the ``(text, metadata) -> doc_id`` / dict-shaped
result contract stays available, while all real work routes through the one
implementation. Prefer injecting ``VectorStoreManager`` directly in new code.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.vectorstore.config import VectorStoreConfig
from app.vectorstore.manager import VectorStoreManager

logger = logging.getLogger("sovereign.services.vector_store")


class VectorStore:
    """Adapter exposing the legacy contract over ``VectorStoreManager``."""

    def __init__(self, store_dir: Path):
        self.store_dir = Path(store_dir)
        config = VectorStoreConfig(index_path=str(self.store_dir))
        self._manager = VectorStoreManager(config=config)
        self._manager.initialize()

    @property
    def manager(self) -> VectorStoreManager:
        """The canonical store doing the work."""
        return self._manager

    async def add_document(
        self,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Ingest a document. Returns its document id."""
        metadata = metadata or {}
        filename = metadata.get("filename") or "document.txt"
        return self._manager.ingest_text(
            text=text,
            filename=filename,
            metadata=metadata,
        )

    async def search(
        self,
        query: str,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """Ranked chunks for a query, as plain dicts."""
        return [
            {
                "text": r.content,
                "score": r.score,
                "metadata": r.metadata,
                "document_id": r.document_id,
            }
            for r in self._manager.search(query_text=query, top_k=top_k)
        ]

    async def list_documents(self) -> List[Dict[str, Any]]:
        return self._manager.list_documents()

    async def delete_document(self, doc_id: str) -> bool:
        """Delete a document. Returns whether it existed."""
        existed = any(
            d.get("id") == doc_id or d.get("document_id") == doc_id
            for d in self._manager.list_documents()
        )
        if existed:
            self._manager.delete_document(doc_id)
        return existed

    def get_stats(self) -> Dict[str, Any]:
        return self._manager.get_stats()

    def shutdown(self):
        self._manager.shutdown()
