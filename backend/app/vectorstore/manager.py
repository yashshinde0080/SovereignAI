"""
Vector Store Manager.
Single entry point for all vector operations.
Document ingestion → Chunking → Embedding → Indexing → Search.
"""

import hashlib
import logging
import threading
import numpy as np
from typing import List, Optional

from .config import VectorStoreConfig
from .chunker import DocumentChunker
from .embedding_pipeline import EmbeddingPipeline
from .index_builder import FAISSIndexBuilder
from .store import VectorMetadataStore
from .retriever import Retriever
from app.schemas.vector_schemas import (
    EmbeddingRecord, SearchQuery,
    SearchResult, RAGContext
)

logger = logging.getLogger("sovereign.vectorstore")


class VectorStoreManager:
    """
    Central vector store manager.

    Usage:
        vs = VectorStoreManager()
        vs.initialize()

        # Ingest document
        doc_id = vs.ingest_text("Full document text here", "doc.pdf")

        # Search
        results = vs.search("What is the main idea?")

        # RAG context
        context = vs.build_context("What is the main idea?")

        vs.shutdown()
    """

    # Class-level fallback so an instance built without __init__ (tests build
    # the manager attribute-by-attribute) still has a lock to write under.
    # __init__ replaces it with a per-instance one.
    _write_lock = threading.RLock()

    def __init__(self, config: Optional[VectorStoreConfig] = None):
        self.config = config or VectorStoreConfig()
        self.chunker = DocumentChunker(
            chunk_size=self.config.chunk_size,
            chunk_overlap=self.config.chunk_overlap,
            max_chunks=self.config.max_chunks_per_document
        )
        self.embedding_pipeline = EmbeddingPipeline(self.config)
        self.index_builder = FAISSIndexBuilder(self.config)
        self.metadata_store = VectorMetadataStore(
            self.config.metadata_db_path
        )
        self.retriever = Retriever(
            config=self.config,
            index=self.index_builder,
            metadata_store=self.metadata_store,
            embedding_pipeline=self.embedding_pipeline
        )
        self._initialized = False
        # Embedding model the on-disk index was built with, when recorded.
        self._index_embedding_model: Optional[str] = None
        # Serializes every write path (ingest / delete / rebuild). Ingest is a
        # read-modify-write across two stores: it reads the next FAISS slot and
        # appends, then writes metadata rows. Unserialized, two concurrent
        # uploads both pick the same slot range and both append — measured: 8
        # parallel uploads left 24 FAISS vectors against 3 metadata rows, and 4
        # of the 8 documents were unretrievable. Reentrant because
        # delete_document() rebuilds.
        self._write_lock = threading.RLock()

    def initialize(self):
        """
        Initialize vector store.
        Load existing index or create new.
        """
        logger.info("Initializing vector store")

        # Try to load existing index
        loaded = self.index_builder.load()

        if not loaded:
            logger.info("[rag.init] no existing index; will create on first ingest")

        # Two different embedding models produce vectors that are not
        # comparable, so sharing one index silently degrades retrieval to noise.
        # The model name is recorded when the index is (re)built; a change is
        # reported loudly instead of being averaged into the same file.
        self._index_embedding_model = self.metadata_store.get_state("embedding_model")
        if (self._index_embedding_model
                and self._index_embedding_model != self.config.embedding_model):
            logger.warning(
                "[rag.init] index was built with embedding model %r but the "
                "configured model is %r. Vectors from different models are not "
                "comparable, so retrieval will be meaningless until the index "
                "is rebuilt (POST /v1/rag/rebuild re-embeds every chunk).",
                self._index_embedding_model, self.config.embedding_model,
            )

        # Self-heal FAISS/metadata desync (stale vectors from deletes, or a
        # crash between metadata write and index save). Metadata is the source
        # of truth: on mismatch, rebuild the index from it. Left unsynced, the
        # next ingest reuses already-occupied vector positions and every
        # search silently returns nothing ("can't access sources").
        index_vectors = self.index_builder.total_vectors
        metadata_vectors = self.metadata_store.get_total_embeddings()
        # A chunk row with no embedding row is invisible to the count check
        # below but still lists as a document with nothing retrievable. Only a
        # rebuild (which re-embeds from metadata) can repair it.
        orphan_chunks = self.metadata_store.get_orphan_chunk_count()
        if index_vectors != metadata_vectors or orphan_chunks:
            logger.warning(
                "[rag.heal] desync: index=%d vectors, metadata=%d embeddings, "
                "%d chunk(s) without embeddings. Rebuilding from metadata.",
                index_vectors, metadata_vectors, orphan_chunks,
            )
            try:
                self.rebuild_index()
            except Exception as e:
                logger.error("[rag.heal] rebuild failed (%s); resetting index to match metadata.", e)
                self.index_builder.reset()

        self._initialized = True
        logger.info(
            f"Vector store initialized. "
            f"Vectors: {self.index_builder.total_vectors}"
        )

    def ingest_text(self, text: str, filename: str,
                    document_id: Optional[str] = None,
                    metadata: Optional[dict] = None) -> str:
        """
        Full ingestion pipeline:
        1. Generate document ID
        2. Chunk text
        3. Generate embeddings
        4. Add to FAISS index
        5. Store metadata

        Returns: document_id
        """
        if not self._initialized:
            raise RuntimeError("Vector store not initialized")

        # Generate document ID
        if document_id is None:
            document_id = self._generate_document_id(text, filename)

        # One writer at a time: the dedup scan, the FAISS slot read, the index
        # append and the metadata write are one logical transaction.
        with self._write_lock:
            return self._ingest_locked(text, filename, document_id, metadata)

    def _ingest_locked(self, text: str, filename: str,
                       document_id: str,
                       metadata: Optional[dict]) -> str:
        """Ingest body. The caller holds ``_write_lock``."""
        # Deterministic ID + INSERT OR REPLACE means a re-upload of the same
        # content would keep metadata flat while FAISS appends duplicate
        # vectors — desync. Skip instead.
        if self.metadata_store.get_chunks_by_document(document_id):
            logger.info(
                f"Document {filename} already indexed (id={document_id}); "
                f"skipping duplicate ingest."
            )
            return document_id

        logger.info(
            f"Ingesting document: {filename} (id={document_id})"
        )

        # Step 1: Chunk
        chunks = self.chunker.chunk_text(text, document_id)
        if not chunks:
            logger.warning(f"No chunks generated for {filename}")
            return document_id

        # Step 1b: content-hash dedup — identical chunks already indexed
        # (any document) are dropped before embedding.
        hashes = [self.metadata_store.content_hash(c.content) for c in chunks]
        existing = self.metadata_store.get_existing_hashes(hashes)
        if existing:
            # Keep the non-duplicates. `zip(*[])` used to raise "not enough
            # values to unpack" whenever EVERY chunk was already indexed — a
            # legitimate re-upload of known content failed with a 500.
            kept = [(c, h) for c, h in zip(chunks, hashes) if h not in existing]
            chunks = [c for c, _ in kept]
            hashes = [h for _, h in kept]
            logger.info(
                f"[rag.ingest] {filename}: skipped {len(existing)} duplicate chunks"
            )
        if not chunks:
            logger.info(f"[rag.ingest] {filename}: all chunks duplicates; nothing indexed")
            return document_id

        # Renumber sequentially after dedup so chunk_ids/indexes stay dense
        for i, c in enumerate(chunks):
            c.chunk_id = self.chunker._generate_chunk_id(document_id, i)
            c.chunk_index = i

        # Add filename to chunk metadata
        if metadata:
            for chunk in chunks:
                chunk.metadata.update(metadata)
                chunk.metadata["filename"] = filename
        else:
            for chunk in chunks:
                chunk.metadata["filename"] = filename

        # Step 2: Generate embeddings. Deliberately BEFORE the chunk rows are
        # written: chunks committed ahead of a failing embedder became orphan
        # rows (listed as a document, unreachable by search, invisible to the
        # index-vs-embedding count check). Nothing is persisted until the
        # vectors exist.
        texts = [chunk.content for chunk in chunks]
        embeddings = self.embedding_pipeline.embed_texts(
            texts, batch_size=32, show_progress=True
        )
        self._assert_dimension(embeddings)

        # Step 3: Store chunks in metadata DB
        self.metadata_store.insert_chunks_batch(chunks, hashes=hashes)

        # Step 4: Handle FAISS index
        # If index doesn't exist or needs training
        if self.index_builder.index is None:
            self.index_builder.create_index()

        # Train if needed (IVF indices)
        if not self.index_builder.is_trained:
            if embeddings.shape[0] >= self.config.nlist:
                self.index_builder.train(embeddings)
            else:
                # Not enough vectors for IVF training
                # Fall back to Flat index
                logger.warning(
                    "Not enough vectors for IVF training. "
                    "Using Flat index instead."
                )
                self.config.index_type = "Flat"
                self.index_builder.reset()
                self.index_builder.create_index()

        # FAISS slot of the first new vector, read from the index itself. The
        # metadata MAX(vector_index)+1 agrees only while the two are in sync;
        # under the write lock the index is authoritative, and using it here is
        # what keeps the two from drifting apart on the next ingest.
        start_index = self.index_builder.total_vectors

        # Add to FAISS
        self.index_builder.add_vectors(embeddings)

        # Step 5: Store embedding metadata
        embedding_records = []
        for i, chunk in enumerate(chunks):
            vector_index = start_index + i
            norm = float(np.linalg.norm(embeddings[i]))
            embedding_records.append(EmbeddingRecord(
                embedding_id=f"{chunk.chunk_id}_emb",
                chunk_id=chunk.chunk_id,
                document_id=document_id,
                vector_index=vector_index,
                dimension=self.config.embedding_dimension,
                norm=norm
            ))

        self.metadata_store.insert_embeddings_batch(embedding_records)

        # Step 6: Save index to disk
        self.index_builder.save()

        # Index-time only: free the embedder so it never competes with the
        # LLM for RAM (8GB target). Reloaded on demand at next ingest/query.
        self.embedding_pipeline.unload_model()

        # Save state
        self.metadata_store.save_state(
            "total_vectors",
            str(self.index_builder.total_vectors)
        )

        # Record which embedding model produced these vectors, so a later
        # model change is detectable rather than silently mixed in.
        self.metadata_store.save_state("embedding_model", self.config.embedding_model)
        self.metadata_store.save_state(
            "embedding_dimension", str(self.config.embedding_dimension)
        )
        self._index_embedding_model = self.config.embedding_model

        logger.info(
            f"[rag.ingest] indexed {filename}: {len(chunks)} chunks, "
            f"{len(embedding_records)} embeddings, "
            f"index now {self.index_builder.total_vectors} vectors"
        )
        return document_id

    def _assert_dimension(self, embeddings: np.ndarray):
        """Fail with an actionable message when the embedder and the index
        disagree about vector width.

        FAISS raises a bare ``AssertionError`` with an empty message here, so
        the cause was invisible. Also re-points the config at what the model
        actually emits, since config.embedding_dimension is what creates the
        index and stamps the embedding rows.
        """
        produced = int(embeddings.shape[1])
        index_dim = self.index_builder.dimension
        if index_dim is not None and index_dim != produced:
            raise RuntimeError(
                f"Embedding dimension mismatch: the stored index is "
                f"{index_dim}-dimensional but the embedding model produced "
                f"{produced}-dimensional vectors. The embedding model changed "
                f"without rebuilding the index. POST /v1/rag/rebuild re-embeds "
                f"the stored chunks at the new dimension."
            )
        self.config.embedding_dimension = produced

    def search(self, query_text: str,
               top_k: int = 5,
               score_threshold: float = 0.0,
               filter_document_id: Optional[str] = None
               ) -> List[SearchResult]:
        """
        Search for relevant chunks.
        """
        if not self._initialized:
            raise RuntimeError("Vector store not initialized")

        query = SearchQuery(
            query_text=query_text,
            top_k=top_k,
            score_threshold=score_threshold,
            filter_document_id=filter_document_id
        )
        return self.retriever.search(query)

    def build_context(self, query_text: str,
                      top_k: int = 5,
                      max_tokens: int = 2048,
                      score_threshold: float = 0.0) -> RAGContext:
        """
        Build RAG context for prompt construction.
        """
        if not self._initialized:
            raise RuntimeError("Vector store not initialized")

        query = SearchQuery(
            query_text=query_text,
            top_k=top_k,
            score_threshold=score_threshold
        )
        return self.retriever.build_rag_context(query, max_tokens)

    def delete_document(self, document_id: str):
        """
        Delete a document and its vectors.
        Rebuilds the index so FAISS positions stay in sync with metadata —
        otherwise stale vectors shift every future lookup off-by-N.
        """
        with self._write_lock:
            self.metadata_store.delete_document_data(document_id)
            self.rebuild_index()
        logger.info(f"[rag.delete] {document_id} deleted, index rebuilt.")

    def rebuild_index(self):
        """
        Full index rebuild from metadata store.
        Use after document deletion.
        """
        with self._write_lock:
            self._rebuild_locked()

    def _rebuild_locked(self):
        """Rebuild body. The caller holds ``_write_lock``."""
        logger.info("[rag.rebuild] starting full index rebuild")

        # Get all documents
        doc_ids = self.metadata_store.get_document_ids()

        if not doc_ids:
            logger.info("[rag.rebuild] no documents; resetting index")
            self.index_builder.reset()
            return

        # Re-embed all chunks — single batch query instead of N separate queries
        all_embeddings = []
        new_embedding_records = []

        chunks_by_doc = self.metadata_store.get_chunks_by_documents(doc_ids)
        vector_offset = 0  # cumulative vector count — NOT len(all_embeddings)

        for doc_id in doc_ids:
            chunks_data = chunks_by_doc.get(doc_id, [])
            texts = [c["content"] for c in chunks_data]

            if not texts:
                continue

            embeddings = self.embedding_pipeline.embed_texts(texts)

            for i, chunk_data in enumerate(chunks_data):
                vector_index = vector_offset + i
                norm = float(np.linalg.norm(embeddings[i]))
                new_embedding_records.append(EmbeddingRecord(
                    embedding_id=f"{chunk_data['chunk_id']}_emb",
                    chunk_id=chunk_data["chunk_id"],
                    document_id=doc_id,
                    vector_index=vector_index,
                    dimension=self.config.embedding_dimension,
                    norm=norm
                ))

            all_embeddings.append(embeddings)
            vector_offset += embeddings.shape[0]

        if not all_embeddings:
            logger.info("No embeddings to rebuild")
            return

        # Concatenate all embeddings
        combined = np.vstack(all_embeddings)

        # Fresh index, built at the width the model actually emits. rebuild is
        # the escape hatch for a changed embedding model, so it must not keep
        # the old config.embedding_dimension that the dead index was built with.
        self.config.embedding_dimension = int(combined.shape[1])
        self.index_builder.reset()
        self.index_builder.create_index()

        # Train if needed
        if not self.index_builder.is_trained:
            if combined.shape[0] >= self.config.nlist:
                self.index_builder.train(combined)
            else:
                self.config.index_type = "Flat"
                self.index_builder.reset()
                self.index_builder.create_index()

        # Old embedding rows must go before the new positions are written: the
        # rows are keyed on vector_index (UNIQUE) and a leftover row from a
        # deleted document would otherwise be silently overwritten by a
        # different chunk's new position, orphaning that chunk.
        self.metadata_store.delete_all_embeddings()

        # Add all vectors
        self.index_builder.add_vectors(combined)

        # Update embedding records
        self.metadata_store.insert_embeddings_batch(new_embedding_records)

        # Save
        self.index_builder.save()

        # Index-time only: free the embedder (same rationale as ingest)
        self.embedding_pipeline.unload_model()

        self.metadata_store.save_state("embedding_model", self.config.embedding_model)
        self.metadata_store.save_state(
            "embedding_dimension", str(self.config.embedding_dimension)
        )
        self._index_embedding_model = self.config.embedding_model

        logger.info(
            f"[rag.rebuild] index rebuilt: {self.index_builder.total_vectors} "
            f"vectors at dimension {self.config.embedding_dimension}"
        )

    def get_document_chunks(self, document_id: str) -> List[dict]:
        """Get all chunks (content + metadata) for a document, in order."""
        if not self._initialized:
            raise RuntimeError("Vector store not initialized")
        return self.metadata_store.get_chunks_by_document(document_id)

    def get_stats(self) -> dict:
        """Get vector store statistics."""
        index_vectors = self.index_builder.total_vectors
        total_chunks = self.metadata_store.get_total_chunks()
        total_embeddings = self.metadata_store.get_total_embeddings()
        return {
            "total_vectors": index_vectors,
            "total_chunks": total_chunks,
            "total_embeddings": total_embeddings,
            # Chunk rows with no embedding row: listed as documents but
            # unreachable by search. Reported so /v1/rag/stats can surface them.
            "orphan_chunks": self.metadata_store.get_orphan_chunk_count(),
            # A desync the old check missed: it compared only index vs
            # embeddings, so orphan chunks read as "in sync".
            "in_sync": (index_vectors == total_embeddings
                        and total_chunks == total_embeddings),
            "total_documents": len(self.metadata_store.get_document_ids()),
            "index_trained": self.index_builder.is_trained,
            "index_type": self.config.index_type,
            "embedding_model": self.config.embedding_model,
            # Model the index on disk was actually built with, when recorded.
            "index_embedding_model": self._index_embedding_model,
            "index_dimension": self.index_builder.dimension,
            "embedding_dimension": self.config.embedding_dimension,
            "chunk_size": self.config.chunk_size,
        }

    def shutdown(self):
        """Clean shutdown."""
        if self.index_builder.total_vectors > 0:
            self.index_builder.save()
        self.metadata_store.close()
        self.embedding_pipeline.unload_model()
        logger.info("Vector store shut down")

    def _generate_document_id(self, text: str, filename: str) -> str:
        """Generate deterministic document ID."""
        content_hash = hashlib.sha256(
            text.encode('utf-8')
        ).hexdigest()[:12]
        return f"doc_{content_hash}"

    def list_documents(self) -> List[dict]:
        """List all indexed documents."""
        if not self._initialized:
            raise RuntimeError("Vector store not initialized")
            
        doc_ids = self.metadata_store.get_document_ids()
        if not doc_ids:
            return []

        # Single batch query instead of N separate get_chunks_by_document calls
        chunks_by_doc = self.metadata_store.get_chunks_by_documents(doc_ids)
        result = []
        for doc_id in doc_ids:
            chunks = chunks_by_doc.get(doc_id, [])
            if not chunks:
                continue
            first_chunk = chunks[0]
            metadata = first_chunk.get("metadata", {})
            result.append({
                "id": doc_id,
                "filename": metadata.get("filename", "Unknown"),
                "chunks": len(chunks),
                "created_at": first_chunk.get("created_at", "Unknown")
            })
        return result
