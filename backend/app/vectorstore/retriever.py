"""
Retriever.
Takes a query, searches FAISS, returns ranked results with content.
Handles score thresholds, document filtering, and context construction.
"""

import logging
from typing import List

import numpy as np

from .config import VectorStoreConfig
from .index_builder import FAISSIndexBuilder
from .store import VectorMetadataStore
from .embedding_pipeline import EmbeddingPipeline
from app.schemas.vector_schemas import SearchQuery, SearchResult, RAGContext

logger = logging.getLogger("sovereign.vectorstore.retriever")


class Retriever:
    """
    Retrieve relevant chunks for a query.
    Combines FAISS search with metadata lookup.
    """

    def __init__(self, config: VectorStoreConfig,
                 index: FAISSIndexBuilder,
                 metadata_store: VectorMetadataStore,
                 embedding_pipeline: EmbeddingPipeline):
        self.config = config
        self.index = index
        self.metadata_store = metadata_store
        self.embedding_pipeline = embedding_pipeline

    def search(self, query: SearchQuery) -> List[SearchResult]:
        """
        Search for relevant chunks.

        Steps:
        1. Embed query text
        2. Search FAISS index
        3. Lookup metadata for results
        4. Apply filters and thresholds
        5. Return ranked results
        """
        if self.index.total_vectors == 0:
            logger.warning("Index is empty. No results.")
            return []

        # Step 1: Embed query
        query_vector = self.embedding_pipeline.embed_single(
            query.query_text
        )
        query_vector = query_vector.reshape(1, -1)

        # Step 2: Search FAISS — over-fetch candidates so the score filter,
        # dedup, and MMR rerank have something left to keep
        top_k = query.top_k or self.config.top_k_default
        distances, indices = self.index.search(query_vector, top_k * 3)

        distances = distances[0]  # First (only) query
        indices = indices[0]

        # Step 3: Lookup metadata
        valid_indices = [int(i) for i in indices if i >= 0]
        if not valid_indices:
            return []

        chunk_data_list = self.metadata_store.get_chunks_by_vector_indices(
            valid_indices
        )

        # Step 4: Build results with filtering
        results = []
        for i, (idx, dist) in enumerate(zip(indices, distances)):
            if idx < 0:
                continue

            # Score conversion
            # For IP (normalized = cosine similarity): higher is better
            # For L2: lower is better, convert to similarity
            if self.config.normalize_embeddings:
                score = float(dist)  # Already cosine similarity
            else:
                score = 1.0 / (1.0 + float(dist))  # Convert L2 to similarity

            # Apply threshold: explicit query threshold, else the config floor
            # (score 0.0 must not mean "accept everything")
            threshold = query.score_threshold or self.config.min_score
            if threshold > 0 and score < threshold:
                continue

            # Get chunk data
            position = valid_indices.index(int(idx)) if int(idx) in valid_indices else -1
            if position < 0 or position >= len(chunk_data_list):
                continue

            chunk_data = chunk_data_list[position]
            if chunk_data is None:
                continue

            # Apply document filter
            if (query.filter_document_id and
                    chunk_data["document_id"] != query.filter_document_id):
                continue

            results.append(SearchResult(
                chunk_id=chunk_data["chunk_id"],
                document_id=chunk_data["document_id"],
                content=chunk_data["content"],
                score=score,
                chunk_index=chunk_data["chunk_index"],
                metadata=chunk_data["metadata"]
            ))

        # Sort by score descending
        results.sort(key=lambda r: r.score, reverse=True)

        # MMR rerank (maximal marginal relevance): keep the top_k most
        # relevant AND least-redundant results. Greedy, cosine space
        # (vectors are L2-normalized), candidate vectors via FAISS
        # reconstruct — no extra deps.
        results = self._mmr_rerank(results, top_k, query_vector[0])

        logger.info(
            f"Search returned {len(results)} results "
            f"for query: '{query.query_text[:50]}...'"
        )
        return results

    def _mmr_rerank(self, results: List[SearchResult],
                    top_k: int, query_vec: "np.ndarray") -> List[SearchResult]:
        """Greedy MMR: iteratively pick the result maximizing
        λ·sim(q, r) − (1−λ)·max sim(r, already-picked)."""
        if len(results) <= 1:
            return results

        try:
            vecs = np.stack([
                self.index.reconstruct(int(self._vector_index_of(r)))
                for r in results
            ])
        except Exception:
            # reconstruct unavailable (IVFPQ etc.) → skip rerank, keep ranking
            return results[:top_k]

        lam = self.config.mmr_lambda
        q = query_vec / (np.linalg.norm(query_vec) or 1.0)
        picked: List[int] = []
        candidates = list(range(len(results)))
        while candidates and len(picked) < top_k:
            best, best_val = None, -1e9
            for c in candidates:
                relevance = float(np.dot(q, vecs[c]))
                redundancy = (
                    max(float(np.dot(vecs[c], vecs[p])) for p in picked)
                    if picked else 0.0
                )
                val = lam * relevance - (1 - lam) * redundancy
                if val > best_val:
                    best, best_val = c, val
            picked.append(best)
            candidates.remove(best)
        return [results[i] for i in picked]

    def _vector_index_of(self, result: SearchResult) -> int:
        """FAISS position of a result via its embedding record."""
        rec = self.metadata_store.get_embedding_by_chunk_id(result.chunk_id)
        if rec is None:
            raise KeyError(result.chunk_id)
        return rec["vector_index"]

    def build_rag_context(self, query: SearchQuery,
                          max_tokens: int = 2048) -> RAGContext:
        """
        Build RAG context from search results.
        Respects token budget.
        Deduplicates content.
        """
        results = self.search(query)

        context_parts = []
        total_tokens = 0
        seen_chunks = set()
        filtered_results = []

        for result in results:
            if result.chunk_id in seen_chunks:
                continue
            seen_chunks.add(result.chunk_id)

            chunk_tokens = max(1, len(result.content) // 3)

            if total_tokens + chunk_tokens > max_tokens:
                # Check if we can fit a partial chunk
                remaining_tokens = max_tokens - total_tokens
                if remaining_tokens > 50:  # Worth including partial
                    doc_name = result.metadata.get("filename", result.document_id)
                    truncated = result.content[:remaining_tokens * 3]
                    formatted_chunk = f"[Source: {doc_name}#{result.chunk_index}]\n{truncated}"
                    context_parts.append(formatted_chunk)
                    total_tokens += remaining_tokens
                    filtered_results.append(result)
                break

            doc_name = result.metadata.get("filename", result.document_id)
            formatted_chunk = f"[Source: {doc_name}#{result.chunk_index}]\n{result.content}"
            context_parts.append(formatted_chunk)
            total_tokens += chunk_tokens
            filtered_results.append(result)

        context_text = "\n\n---\n\n".join(context_parts)

        return RAGContext(
            query=query.query_text,
            results=filtered_results,
            total_tokens=total_tokens,
            context_text=context_text
        )