# Algorithms Implemented and Used in SovereignAI

This document outlines the 25 core algorithms utilized and implemented across the SovereignAI platform, spanning Natural Language Processing (NLP), Vector Retrieval, Neural Network Execution, Memory Management, and Frontend Orchestration.

## Retrieval-Augmented Generation (RAG) & Vector Database

1. **Sentence Boundary Detection Algorithm**
   * **Description**: Implemented using Regular Expressions in `chunker.py`, this algorithmic approach accurately splits long documents along grammatical sentence boundaries (e.g., periods, exclamation marks) without breaking sentences in half.

2. **Recursive Character Chunking Algorithm**
   * **Description**: A fallback algorithm in `chunker.py` (`_force_split`) that forcefully partitions massive blocks of text into smaller segments based on explicit token lengths/character offsets when natural sentence boundaries cannot be found.

3. **Sliding Window Overlap Algorithm**
   * **Description**: Ensures semantic continuity when processing large documents. By carrying over a designated number of trailing sentences from a preceding chunk into the next one, it prevents the loss of context across artificial boundaries.

4. **Token Budget Estimation Algorithm**
   * **Description**: A heuristic algorithm (approximated as `Length / 4`) implemented to quickly gauge the token footprint of text chunks without spinning up a heavy neural tokenizer, prioritizing execution speed.

5. **FAISS (Facebook AI Similarity Search) Indexing Algorithm**
   * **Description**: Manages the construction of high-dimensional vector spaces. It allows rapidly indexing document embeddings and performing Approximate Nearest Neighbor (ANN) searches natively.

6. **Cosine Similarity Algorithm**
   * **Description**: A fundamental vector metric utilized by the `retriever.py` to calculate the mathematical cosine of the angle between two high-dimensional embedding vectors, thereby gauging their semantic relationship.

7. **L2 (Euclidean) Distance Algorithm**
   * **Description**: Supported as an alternative spatial metric within the FAISS indices to track the straight-line distance between document vectors and the query vector.

8. **Sentence-Transformer Embedding Algorithm (e.g., MiniLM/BERT)**
   * **Description**: Used in `embedding_pipeline.py` to route raw semantic strings continuously through a dense Transformer architecture, translating textual relationships into abstract multi-dimensional math arrays.

9. **Context Construction & Deduplication Algorithm**
   * **Description**: Implemented within the retriever module to incrementally build the final RAG LLM prompt. It actively tracks `chunk_id` signatures to reject duplicate vectors while fitting precisely within the model's hardcoded token budget.

## Core Engine & Memory Management

10. **Layer-wise Model Offloading (LayerStream) Algorithm**
    * **Description**: The cornerstone custom algorithm of SovereignAI's `LayerStreamEngine`. Instead of loading the full LLM into VRAM, it computes transformer layers sequentially, mapping and unmapping layer buffers strictly on demand to support deep models on low-end hardware.

11. **LRU (Least Recently Used) Cache Eviction Algorithm**
    * **Description**: Residing in `scheduler.py`, this keeps track of layer timestamps (`last_used = time.time()`). Once the maximum active layer threshold is breached, it targets and evicts the sequentially oldest layer residing in active RAM.

12. **Asynchronous Prefetching Algorithm**
    * **Description**: An anticipatory loading mechanism present in `prefetch.py`. While the inference engine computes Layer `N`, this algorithm immediately schedules I/O threads to load Layer `N+1` and `N+2` into memory, masking hardware latency.

13. **Memory-Mapped (Mmap) Zero-Copy Loading Algorithm**
    * **Description**: Found in `mmap_loader.py`, this I/O algorithm allows SovereignAI to map massive neural network weight files directly into addressable memory space. It bypasses the standard OS swap buffer entirely.

14. **Dynamic Hardware Detection Algorithm**
    * **Description**: Analyzes local system architecture (CPU cores, Available RAM, disk performance, VRAM limits) at initialization to algorithmically route system logic toward either the `FullRAM` or `LayerStream` execution environments.

15. **Transformer Forward Pass Activation Algorithm**
    * **Description**: The matrix-multiplication sequence executed in `_compute_layer`. It systematically passes dynamic token activations over the frozen weight matrices of attention blocks and feed-forward networks (FFN).

16. **Byte-Pair Encoding (BPE) Tokenization Algorithm**
    * **Description**: Employed natively to statistically identify sub-word structures, transforming the raw strings into discrete integer sequences that standard language models can process mathematically.

## LLM Decoding & Inference Utilities

17. **Top-P (Nucleus) Sampling Algorithm**
    * **Description**: A probabilistic decoding algorithm explicitly implemented in the sampling methods. It intelligently bounds generation by selecting only the minimal pool of vocabulary tokens whose combined probability weight surpasses the continuous mass threshold `P`.

18. **Temperature Scaling Algorithm**
    * **Description**: Actively divides raw prediction logits by a floating factor (Temperature). A smaller temperature uniquely sharpens the probability curves closer to 1.0/0.0, whilst a higher factor flattens them to increase language creativity.

19. **Greedy Search Decoding Algorithm**
    * **Description**: The engine's structural fallback triggered when `Temperature = 0.0`. It simplifies probability distributions by strictly retrieving `argmax(logits)`—always selecting the statistically highest token.

20. **Hardware Quality Scoring Threshold Algorithm**
    * **Description**: A dynamic threshold calculation algorithm integrated into the backend service APIs that evaluates machine capacity against normalized standards; converting resource metrics into a final percentage UI score (>90% threshold adaptations).

## Frontend & Event System Optimizations

21. **Virtual DOM Reconciliation Algorithm**
    * **Description**: Employed intrinsically by the React framework to batch and calculate the minimal isolated HTML node changes—preventing GUI lockup when dynamically rendering large, complex, and streaming chat logs.

22. **Cryptographic UUID Generation Algorithm (RFC 4122)**
    * **Description**: Uses Python's internal random entropy pool (e.g. `uuid.uuid4()`) to universally construct un-collidable identifiers for chunks, RAG documents, and message interactions.

23. **Debouncing & Throttling Algorithm**
    * **Description**: Ensures stability across the frontend component structure (such as the `useChat.ts` hook). It delays synchronous API function invocations precisely until a defined period of system inactivity transpires.

24. **Exponential Backoff Reconnection Algorithm**
    * **Description**: Manages unstable offline states by exponentially increasing the delay time between internal server retry attempts, preventing frontend clients from overflowing a recovering local API service.

25. **Asynchronous Token Stream (SSE) Buffering Algorithm**
    * **Description**: Yields partial textual representations from the isolated LLM inference Python process asynchronously. The tokens are funneled through the WebSocket/SSE buffer before actively concatenating onto the UI user state.
