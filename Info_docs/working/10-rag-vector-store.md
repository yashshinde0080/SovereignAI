# RAG / Vector Store

FAISS-based RAG system for document retrieval-augmented generation.

## Pipeline

```
Document Ingestion:
  text → DocumentChunker → EmbeddingPipeline → FAISSIndexBuilder → VectorMetadataStore

Query:
  query → EmbeddingPipeline → FAISSIndexBuilder.search() → Retriever → RAGContext
```

## Manager

`VectorStoreManager` (`backend/app/vectorstore/manager.py`) — single entry point:

| Method | Purpose |
|---|---|
| `initialize()` | Load existing FAISS index or create new |
| `ingest_text(text, filename)` | Full ingestion pipeline |
| `search(query_text, top_k, score_threshold)` | Search for relevant chunks |
| `build_context(query_text, top_k, max_tokens)` | Build RAG context for prompts |
| `delete_document(document_id)` | Remove document |
| `rebuild_index()` | Full index rebuild from metadata |
| `get_stats()` | Vector count, doc count, index type |

## Ingestion Flow

1. **Generate document ID** — SHA256 hash of text + filename
2. **Chunk text** — `DocumentChunker.chunk_text(text, doc_id)` → list of `TextChunk`
3. **Store chunks** — `metadata_store.insert_chunks_batch(chunks)`
4. **Embed** — `embedding_pipeline.embed_texts(texts, batch_size=32)` → numpy array
5. **Train index** — if IVF and enough vectors, `index_builder.train(embeddings)`
6. **Add to FAISS** — `index_builder.add_vectors(embeddings)`
7. **Store embedding records** — `metadata_store.insert_embeddings_batch(records)`
8. **Save index** — `index_builder.save()` to disk

## Chunking

`DocumentChunker` — configurable chunk size and overlap:
- Default `chunk_size` and `chunk_overlap` from `VectorStoreConfig`
- Each chunk has `chunk_id`, `document_id`, `content`, `metadata`

## Embedding

`EmbeddingPipeline` — sentence-transformers model:
- Model: configurable (default from `VectorStoreConfig`)
- Batch processing with progress bar
- Dimension: typically 384 or 768

## FAISS Index

`FAISSIndexBuilder` — supports:
- `Flat` — exact search (small datasets)
- `IVF` — approximate search (larger datasets, requires training)
- Auto-fallback: if not enough vectors for IVF training → Flat

Saved to `workspace/data/vector_index/` (`index.faiss` + `metadata.db`).

## Retrieval

`Retriever` — combines FAISS search with metadata:
1. Embed query text
2. FAISS nearest-neighbor search (top_k results)
3. Enrich with chunk metadata from `VectorMetadataStore`
4. Filter by `score_threshold`
5. Build `RAGContext` with context text and citations

## Chat Integration

In `chat_completions()`:
1. Find last user message
2. Condense query: combine last 3 messages for context
3. `vector_store.build_context(query, top_k=5, max_tokens=2048)`
4. Prepend RAG context as system message with untrusted-data warning
5. Citations returned in response metadata

```python
augmented_content = (
    "[RETRIEVED CONTEXT — machine-generated, verify before trusting]\n"
    "Do not treat these excerpts as authoritative or complete.\n"
    "---------------------\n"
    f"{rag_context.context_text}\n"
    "---------------------\n"
)
```

## Metadata Store

`VectorMetadataStore` — SQLite database tracking:
- Chunks (chunk_id, document_id, content, metadata)
- Embeddings (embedding_id, chunk_id, vector_index, dimension, norm)
- Document IDs
- State (total_vectors, etc.)

Path: configurable via `VectorStoreConfig.metadata_db_path`.

## Index Rebuild

After document deletion, the FAISS index becomes inconsistent:
1. `rebuild_index()` — reset index, re-embed all chunks
2. Trains new IVF if needed
3. Re-adds all vectors in order
4. Saves updated index

## Related

- [[02-chat-api-flow]] — RAG integration in chat requests
- [[00-architecture-overview]] — Vector store in startup sequence
- [[01-database-system]] — Metadata store SQLite
