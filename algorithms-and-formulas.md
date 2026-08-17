# SovereignAI Edge — Top 3 Algorithms & Formulas (Research Paper Reference)

> Direct-from-source reference of the three load-bearing algorithms in the
> SovereignAI Edge inference stack. Every formula below is grounded in the
> shipped code; file:line citation given per equation. For a research paper,
> cite the artifact + the upstream paper where noted.

## Algorithm Index
1. **LayerStream — Layer-by-Layer Weight-Swap Inference** (`layer_executor.execute_forward`)
2. **TurboQuant — Compressed KV Cache** (PolarQuant + QJL + Affine + bit-packing)
3. **Top-K + Top-P (Nucleus) Sampling** (`Sampler.sample`)

---

## Algorithm 1 — LayerStream Layer-by-Layer Inference

**Purpose:** run LLM inference when full model does not fit in RAM/VRAM. Only one
layer's weights resident at a time; swap from disk per forward pass.
Source: `backend/app/engines/layerstream/layer_executor.py:206-350`,
`loader.py:13-142`.

### 1.1 Data flow per forward pass

```
input_ids (batch, seq)
  │
  ├─ embed load + assign_weights + embed(input_ids) + offload_weights
  ├─ precompute RoPE (cos, sin) if rotary_emb exists        [meta-tensor fix]
  for i in 0..num_layers-1:
  │   ├─ prefetch_async(layer_paths[i+1 .. i+prefetch_depth])   # ThreadPoolExecutor
  │   ├─ loader.get_weights(layer_paths[i])                      # block on prefetch
  │   ├─ assign_weights(layer, state_dict)                        # _load_into_module
  │   ├─ layer(hidden_states, position_ids, attn_mask, past_kv, cache_position, position_embeddings)
  │   └─ offload_weights(layer)                                  # free dense params
  ├─ norm load + apply + offload
  └─ lm_head load + apply + offload → logits[:, -1:, :]
```

### 1.2 Key formulas
**Token cost model** (measured 2026-08-14, Qwen3.5-0.8B, `reviews/benchmark-2026-08-14.md`):
- Total wall time per generate call: $T = T_{\text{load}} + T_{\text{compute}}$
- $T_{\text{load}} = \sum_{\ell=1}^{L} \overline{t}_{\text{read}}(\ell) \approx L \cdot \overline{t}_{\text{read}}$
- $T_{\text{compute}} \approx 98\%$ of $T$ on CPU (disk read is not the bottleneck at 9 ms/layer avg)
- Throughput: $\text{tok/s} = \frac{N_{\text{gen}}}{T_{\text{total}}}$

For measured run: $L = 864$ layer loads, $\overline{t}_{\text{read}} = 9\text{ ms}$, $T_{\text{load}} = 7.73\text{ s}$, $T_{\text{compute}} = 77.83\text{ s}$, $N_{\text{gen}} = 32$, $\text{tok/s} = 0.40$.

### 1.3 Peak RAM accounting
LayerStream bounds resident memory:
$$\text{RSS}_{\text{peak}} \approx \text{RSS}_{\text{base}} + W_{\text{embed}} + \max_\ell W_\ell + \text{KV}_{\text{size}}$$
where $W_\ell$ is layer $\ell$ weight size (int4/int8 dequantized on device), $\max_\ell W_\ell$ because only one layer resident at a time, $\text{KV}_{\text{size}}$ capped (TurboQuant off, 2048 MB; on, compressed).

Measured: 1.9 GB model → 2.30 GB peak RSS (base 0.46 GB). Confirms bounded RAM.

### 1.4 Prefetch + LRU loader cache (`loader.py`)
- `prefetch_depth = 3` (default): `ThreadPoolExecutor.submit(_load_file)` for next 3 layers
- LRU byte-budget cache: evict non-pinned entries (`_enforce_budget`) until under budget
- Pinned paths (exempt from eviction): `embed`, `norm`, `lm_head`

Pinned vs evictable invariant (not a formula, a correctness property):
$$\forall t: W_{\text{resident}}(t) \le \text{cache\_budget} + \sum_{p \in \text{pinned}} W_p$$

---

## Algorithm 2 — TurboQuant Compressed KV Cache

**Purpose:** compress attention K/V so long-context decode fits in less RAM.
Source: `backend/app/engines/shared/turboquant/{polarquant,qjl,codebook,affine,kv_cache}.py`.
Paper: arXiv 2504.19874 (TurboQuant, ICLR 2026, Google Research). KIVI: arXiv 2402.02750.

Two quantization schemes selected by `config.quant_scheme`:
- `polar` (default): unit-normalize → random orthogonal rotation → scalar codebook + QJL residual
- `affine`: KIVI-style per-channel K / per-token V scales, no rotation/QJL

### 2.1 Scheme A — PolarQuant

Stage 0 — rotation matrix (cached per `head_dim`), `polarquant.py:6-15`:
$$A \sim \mathcal{N}(0, I_d), \quad Q, R = \text{QR}(A), \quad D = \text{diag}(\text{sign}(\text{diag}(R)))$$
$$R_{\text{rot}} = Q D \quad \text{(random orthogonal, } R^T = R^{-1}\text{)}$$

Stage 1 — normalize + rotate + scalar quantize, `kv_cache.py:194-204`:
$$\hat{x} = \frac{x}{\|x\|_2 + \epsilon} \quad \text{(unit-normalize, } \epsilon = 10^{-8}\text{)}$$
$$\tilde{x} = \hat{x} R_{\text{rot}}^T \quad \text{(apply rotation)}$$

Codebook — **uniform centroids on** $[-1, 1]$, `codebook.py:17-20` (NOT Beta Lloyd-Max; that version was broken — missing `sqrt()` mapping clustered centroids near $\pm 1$):
$$c_j = -1 + \frac{2j}{N - 1}, \quad j = 0, \dots, N-1, \quad N = 2^{b}$$
Quantize to nearest centroid:
$$\text{idx}_i = \arg\min_j |\tilde{x}_i - c_j|$$
$$\tilde{x}_{\text{ quant}} = c_{\text{idx}}$$

Uniform-codebook MSE per coordinate (theoretical, `codebook.py` docstring):
$$\text{MSE}_{\text{coord}} = \frac{1}{12} \left(\frac{2}{N - 1}\right)^2$$

Stage 2 — QJL residual correction, `qjl.py:6-38` + `kv_cache.py:206-214`:
$$r = \tilde{x} - \tilde{x}_{\text{quant}} \quad \text{(residual after scalar quant)}$$

QJL projection (Rademacher, `qjl.py:21-24`):
$$P \in \mathbb{R}^{d' \times d}, \quad P_{ij} \in \{-1, +1\}, \quad P_{ij} = \frac{1}{\sqrt{d'}} \cdot (2 \cdot \mathbb{1}[Z_{ij} = 1] - 1), \quad Z \sim \text{Bern}(0.5)$$

Encode (`qjl.py:27-38`):
$$z = \text{sign}(r P^T) \in \{-1, +1\}^{d'}$$

Decode with empirically-tuned scale $c = 1/32$ (`qjl.py:58`, NOT textbook $1/d'$ or $1/\sqrt{d'}$ — see ablation note):
$$\hat{r} = c \cdot z P, \quad c = \frac{1}{32}$$

Ablation result (`qjl.py:42-57`, 3.5 bits, attention NMSE):
| scale | NMSE |
|---|---|
| QJL off | 0.494 |
| shipped (1/d') | 0.463 |
| $c = 1/32$ | **0.275** |
| $c = 1/16$ | 0.574 (noise floor cliff) |

Stage 3 — reconstruct + rescale, `kv_cache.py:282-304`:
$$\tilde{x}_{\text{recon}} = c_{\text{idx}} + \hat{r}$$
$$x_{\text{recon}} = \tilde{x}_{\text{recon}} R_{\text{rot}} \cdot \|x\|_2$$

Storage breakdown (head_dim $d$, $N = 2^b$ levels, QJL dim $d'$, `kv_cache.py:97-110`):
| component | bits/coord | note |
|---|---|---|
| PolarQuant index | $b$ | bit-packed, $k$ per uint32 word where $k = \lfloor 32 / \log_2 N \rfloor$ |
| QJL code | 1 | bit-packed, 32 per uint32 word |
| per-vector scale | 16 (fp16) | one $\|x\|_2$ per (h, seq) vector |
| **total** | $\approx b + 1 + 16/d$ | at $b=3.5, d=64 \Rightarrow 4.75$ bits/coord |

Per-vector normalization + fp16 scale is the divergence from paper — paper assumes full $3.5$ bits total (2.5-bit PolarQuant + 1-bit QJL) with no per-vector scale, targeting ~6x. Shipped bit-packing gives measured **~3.3-4.1x** at $d = 64$-$128$ (`kv_cache.py:97-104`), paper's 6x needs codebooks that absorb magnitudes directly.

### 2.2 Scheme B — Affine (KIVI-style)

Per-group symmetric affine quantization, `affine.py:18-43`.

Scale (K over seq dim, axis=1; V over head dim, axis=2):
$$s = \max |x|_{\text{axis}}, \quad s \leftarrow \max(s, 10^{-12})$$
$$h = \frac{N - 1}{2} \quad \text{(half-range in level units)}$$

Quantize (`affine.py:40-41`, **round not truncate** — truncating adds half-step bias, 3x worse NMSE):
$$\text{idx} = \text{round}\left(\frac{x}{s} \cdot h + h\right), \quad \text{clip to } [0, N-1]$$

Dequantize (`affine.py:50-52`, exact inverse):
$$\hat{x} = \frac{\text{idx} - h}{h} \cdot s$$

K/V asymmetric bit budgets (`kv_cache.py:323-331`):
- K: `k_bits` via `config.k_bits`, scale per (h, token) channel — K is harder
- V: `v_bits` via `config.v_bits`, scale per (h, dim) token
- Eval-gate best variant (`reviews/eval_gate_pythia_2026-08-10.json`): `4k6v` (k=4, v=6) — still fails needle, perplexity 555 vs baseline 39 (14x worse)

Empirical: affine 5-28x lower NMSE than polar at same bit rate on real Qwen2-0.5B K/V (`affine.py` docstring, `benchmarks/kv_structure_probe.py`) — raw channels vary ~10x in scale; rotated unit-vector coordinates forced into $[-1, 1]$ destroys magnitude structure.

### 2.3 Incremental update (fixes shipped O(n²))
`kv_cache.py:106-113`: replace re-quantize-everything with raw-token hot buffer.
- `update()` appends raw K/V to per-layer buffer (O(chunk) work)
- Buffer flushes to quantized chunk at `chunk_size = 64` tokens
- History never re-quantized → each token quantized exactly once
- Incremental updates bit-exact with one-shot update under same chunking
- Chunk count $\mathcal{O}(n / \text{chunk\_size})$, was $\mathcal{O}(n^2)$

### 2.4 Bit-packing (`kv_cache.py:13-66`)
PolarQuant indices: $k = \lfloor 32 / \log_2 N \rfloor$ codes per uint32 word.
$$\text{packed} = \sum_{i=0}^{k-1} \text{idx}_i \cdot N^i$$
QJL codes: 1 bit each, 32 per uint32 word (`qjl.py:71-85`):
$$\text{packed} = \sum_{i=0}^{31} b_i \cdot 2^i, \quad b_i = \frac{z_i + 1}{2} \in \{0, 1\}$$
Unpack: `bits = (word >> i) & 1`, `z = 2 \cdot \text{bits} - 1`.

---

## Algorithm 3 — Top-K + Top-P (Nucleus) Sampling

**Purpose:** sample next token from logits without mutating inference-graph tensors.
Source: `backend/app/engines/layerstream/sampler.py:1-36`.

### 3.1 Greedy (temperature ≤ 0)
$$\text{next} = \arg\max_w \text{logits}_w$$

### 3.2 Temperature scaling
$$\text{logits}'_w = \frac{\text{logits}_w}{T}, \quad T > 0$$

### 3.3 Top-K masking (`sampler.py:18-20`)
Keep top-$K$ logits, set rest to $-\infty$:
$$v = \text{topk}(\text{logits}', K), \quad \text{logits}'_w = \begin{cases} \text{logits}'_w & \text{logits}'_w \ge v_{[-1]} \\ -\infty & \text{otherwise} \end{cases}$$

### 3.4 Top-P nucleus filtering (`sampler.py:23-32`)
1. Sort logits descending: $\sigma_1 \ge \sigma_2 \ge \dots$
2. Cumulative softmax probs: $c_i = \sum_{j \le i} \frac{e^{\sigma_j}}{\sum_k e^{\sigma_k}}$
3. Remove tokens where cumulative prob > top_p (but keep first token always):
$$\text{remove}_i = \begin{cases} \text{false} & i = 1 \\ c_{i-1} > p & i > 1 \end{cases}$$
   (shift right by one so the first token crossing threshold is kept)
4. Scatter removal mask back to original index order, set removed logits to $-\infty$

### 3.5 Sampling
$$\text{probs} = \text{softmax}(\text{logits}'), \quad \text{next} \sim \text{Categorical}(\text{probs})$$
Using `torch.multinomial(probs, num_samples=1)`.

Critical correctness detail (`sampler.py:10`): `logits = logits[:, -1, :].clone()` — operates only on the last position of the sequence and clones first so the pre-softmax graph tensors are never mutated.

Order of application: temperature → Top-K → Top-P → softmax → multinomial. Top-K narrows the candidate set before Top-P, so the nucleus is computed over the already-filtered distribution (standard chained nucleus).

Default args: $T = 0.7$, $p = 0.9$, $K = 50$.

---

## Algorithm Implementation Status (verified 2026-08-17)

| Algorithm | Shipping | Default | Tests |
|---|---|---|---|
| LayerStream layer-swap (Algo 1) | yes | secondary | 1 @slow round-trip (`test_layerstream_roundtrip.py`) |
| TurboQuant PolarQuant (Algo 2A) | yes | **OFF** (`config.py: turboquant_enabled=False`) | 33 tests pass |
| TurboQuant Affine (Algo 2B) | yes | off (same flag) | included in 33 |
| Top-K + Top-P sampler (Algo 3) | yes | primary sampling path | exercised via @slow round-trip |

PolarQuant codebook shipped as **uniform centroids** (not Beta Lloyd-Max), QJL decode scale tuned to $c = 1/32$ (not textbook $1/d'$ or $1/\sqrt{d'}$). Eval gates (`reviews/eval_gate_*.json`) FAIL on Qwen2-0.5B and Pythia-70m — default-off stays until a quantizer shows <1% vector error on real K/V at ≥1B params.
