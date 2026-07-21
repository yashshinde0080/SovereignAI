---
tags: [algorithm, reference, NLP, RAG, inference]
source: "[[Docs/implemented_algorithms.md]]"
created: 2026-07-21
updated: 2026-07-21
---

# Implemented Algorithms

SovereignAI implements 25 core algorithms spanning NLP, vector retrieval, neural network execution, memory management, and frontend orchestration. These algorithms power the full stack from document ingestion through inference to UI rendering.

## RAG and Vector Database (9 algorithms)

The retrieval-augmented generation pipeline uses sentence boundary detection and recursive character chunking for document splitting, sliding window overlap for semantic continuity, token budget estimation for efficient chunk sizing, FAISS indexing with cosine similarity and L2 distance for vector search, sentence-transformer embeddings for text encoding, and context construction with deduplication for prompt assembly.

## Core Engine and Memory Management (7 algorithms)

The LayerStream engine's layer-wise model offloading algorithm is the cornerstone custom algorithm, enabling deep models on low-end hardware by computing transformer layers sequentially. It is supported by LRU cache eviction for layer lifecycle management, asynchronous prefetching to mask I/O latency, memory-mapped zero-copy loading via `mmap_loader.py`, dynamic hardware detection that selects between FullRAM and LayerStream, transformer forward pass activations, and BPE tokenization.

## LLM Decoding and Inference (4 algorithms)

The inference pipeline implements top-p (nucleus) sampling for probabilistic token selection, temperature scaling to control output creativity, greedy search decoding (argmax) as a structural fallback, and hardware quality scoring thresholds for capacity evaluation.

## Frontend and Event System (5 algorithms)

The frontend leverages React's Virtual DOM reconciliation for efficient chat log rendering, cryptographic UUID generation (RFC 4122) for unique identifiers, debouncing and throttling for API call stability, exponential backoff reconnection for offline resilience, and asynchronous token stream buffering for real-time text display.

## Key Points

- 25 algorithms documented across 4 categories: RAG/Vector, Engine/Memory, LLM Decoding, Frontend
- Layer-wise model offloading is the signature custom algorithm enabling low-memory inference
- FAISS indexing and cosine similarity form the backbone of RAG retrieval
- Asynchronous prefetching is critical to masking disk I/O latency in LayerStream
- Frontend algorithms ensure smooth streaming token display and offline resilience

## Related

- [[Engine Algorithms]] — Pseudocode for FullRAM and LayerStream execution algorithms
- [[Engines Overview]] — Architecture of both inference engines
- [[LayerStream]] — Memory-bounded engine that uses layer offloading
- [[RAG]] — Document ingestion and retrieval pipeline
- [[FullRAM]] — High-performance monolithic engine
