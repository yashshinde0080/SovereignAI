"""Byte-Pair Encoding tokenizer.

Loads HuggingFace BPE format: vocab.json + merges.txt.
Uses GPT-2 byte-level encoding for token ↔ byte mapping.

Pipeline:
    text → pre-tokenize (regex split) → BPE merge → token IDs
    token IDs → vocab lookup → byte-decode → text
"""

from __future__ import annotations

import json
import re
from pathlib import Path


# ── GPT-2 byte encoder ──────────────────────────────────────────────
# Maps byte values 0-255 to unicode characters starting at ordinal 256.
# This gives a reversible byte→string mapping for BPE.
BYTE_encoder: dict[bytes, str] = {}
BYTE_decoder: dict[str, bytes] = {}
_bs = list(range(33, 127)) + list(range(161, 173)) + list(range(174, 256))
_cs = _bs[:]
for _n in range(256):
    if _n not in _bs:
        _bs.append(_n)
        _cs.append(256 + _n)
for _b, _c in zip(_bs, _cs):
    BYTE_encoder[bytes([_b])] = chr(_c)
    BYTE_decoder[chr(_c)] = bytes([_b])


def _bytes_to_unicode(b: bytes) -> str:
    """Convert bytes to GPT-2 byte-level unicode string."""
    return "".join(BYTE_encoder.get(bytes([x]), chr(x)) for x in b)


def _unicode_to_bytes(s: str) -> bytes:
    """Convert GPT-2 byte-level unicode string back to bytes."""
    return b"".join(BYTE_decoder[c] for c in s if c in BYTE_decoder)


# ── Pre-tokenization regex ────────────────────────────────────────
# GPT-2 pattern uses \p{L} (Unicode letter) which requires the `regex`
# module. We try `regex` first, fall back to stdlib `re` with an
# equivalent character class for portability.
def _build_pretokenize_re():
    try:
        import regex  # type: ignore[import-untyped]
        return regex.compile(
            r"""'s|'t|'re|'ve|'m|'ll|'d| ?\p{L}+| ?\p{N}+| ?[^\s\p{L}\p{N}]+|\s+""",
            regex.UNICODE,
        )
    except ImportError:
        # stdlib fallback: \w matches [a-zA-Z0-9_], close enough for Latin scripts
        return re.compile(
            r"""'s|'t|'re|'ve|'m|'ll|'d| ?[a-zA-Z]+| ?[0-9]+| ?[^\sa-zA-Z0-9]+|\s+""",
        )


_PRETOKENIZE_RE = _build_pretokenize_re()


def _fallback_pretokenize(text: str) -> list[str]:
    """Fallback pre-tokenizer when regex unicode properties are not available."""
    return re.findall(r"\w+|[^\w\s]+|\s+", text)


class Tokenizer:
    """BPE tokenizer loaded from a HuggingFace model directory."""

    def __init__(self, model_dir: str | Path):
        self.model_dir = Path(model_dir)
        self.vocab: dict[str, int] = {}
        self.merges: list[tuple[str, str]] = []
        self._decode_vocab: dict[int, str] = {}
        self.eos_token_id: int = 0
        self.bos_token_id: int = 1
        self.pad_token_id: int = 0
        self._load()

    def _load(self) -> None:
        """Load vocab.json, merges.txt, and tokenizer_config.json."""
        # ── Vocab ───────────────────────────────────────────────────
        vocab_path = self.model_dir / "vocab.json"
        if vocab_path.exists():
            with open(vocab_path, "r", encoding="utf-8") as f:
                self.vocab = json.load(f)
        else:
            # Try tokenizer.json (HuggingFace tokenizers library format)
            tj_path = self.model_dir / "tokenizer.json"
            if tj_path.exists():
                self._load_from_tokenizer_json(tj_path)
            else:
                raise FileNotFoundError(
                    f"No vocab.json or tokenizer.json in {self.model_dir}"
                )

        self._decode_vocab = {v: k for k, v in self.vocab.items()}

        # ── Merges ──────────────────────────────────────────────────
        merges_path = self.model_dir / "merges.txt"
        if merges_path.exists():
            with open(merges_path, "r", encoding="utf-8") as f:
                lines = f.read().strip().split("\n")
            # First line is usually "#version: 0.2", skip if so
            start = 0
            if lines and lines[0].startswith("#"):
                start = 1
            self.merges = []
            for line in lines[start:]:
                parts = line.strip().split(" ", 1)
                if len(parts) == 2:
                    self.merges.append((parts[0], parts[1]))
        else:
            self.merges = []

        # ── Special tokens from config ──────────────────────────────
        cfg_path = self.model_dir / "tokenizer_config.json"
        if cfg_path.exists():
            with open(cfg_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            eos = cfg.get("eos_token")
            if isinstance(eos, str) and eos in self.vocab:
                self.eos_token_id = self.vocab[eos]
            elif isinstance(eos, int):
                self.eos_token_id = eos

            bos = cfg.get("bos_token")
            if isinstance(bos, str) and bos in self.vocab:
                self.bos_token_id = self.vocab[bos]
            elif isinstance(bos, int):
                self.bos_token_id = bos

            pad = cfg.get("pad_token")
            if isinstance(pad, str) and pad in self.vocab:
                self.pad_token_id = self.vocab[pad]
            elif isinstance(pad, int):
                self.pad_token_id = pad

    def _load_from_tokenizer_json(self, path: Path) -> None:
        """Extract vocab from tokenizer.json (HuggingFace tokenizers format)."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # tokenizer.json has {"model": {"vocab": {"token": id}, "merges": [...]}}
        model = data.get("model", {})
        self.vocab = model.get("vocab", {})
        if isinstance(self.vocab, list):
            # Some formats store as list of [token, id] pairs
            self.vocab = {t: i for t, i in self.vocab}

        # Extract merges from tokenizer.json if merges.txt is missing
        raw_merges = model.get("merges", [])
        self.merges = []
        for m in raw_merges:
            parts = m.split(" ", 1)
            if len(parts) == 2:
                self.merges.append((parts[0], parts[1]))

    # ── Public API ──────────────────────────────────────────────────

    def encode(self, text: str, add_bos: bool = False) -> list[int]:
        """Encode text to token IDs using BPE."""
        if not text:
            return []

        # Pre-tokenize into chunks
        chunks = self._pretokenize(text)

        all_ids: list[int] = []
        if add_bos and self.bos_token_id:
            all_ids.append(self.bos_token_id)

        for chunk in chunks:
            # Convert chunk to byte-level unicode pieces
            piece_bytes = chunk.encode("utf-8")
            # Split into individual byte-encoded characters
            # Each byte becomes a GPT-2 unicode character
            symbols = [_bytes_to_unicode(bytes([b])) for b in piece_bytes]

            # Apply BPE merges
            symbols = self._bpe(symbols)

            # Look up IDs (clamp to vocab_size range)
            vsz = len(self.vocab)
            for s in symbols:
                tid = self.vocab.get(s, self.vocab.get(s.strip(), 0))
                all_ids.append(min(tid, vsz - 1) if vsz > 0 else 0)

        return all_ids

    def decode(self, ids: list[int]) -> str:
        """Decode token IDs back to text."""
        parts: list[str] = []
        for tid in ids:
            token = self._decode_vocab.get(tid, "")
            if token:
                parts.append(token)
        # Join and convert byte-level unicode back to bytes, then decode
        combined = "".join(parts)
        try:
            return _unicode_to_bytes(combined).decode("utf-8", errors="replace")
        except Exception:
            return combined

    @property
    def vocab_size(self) -> int:
        return len(self.vocab)

    # ── Internal ────────────────────────────────────────────────────

    def _pretokenize(self, text: str) -> list[str]:
        """Split text into chunks before BPE."""
        return _PRETOKENIZE_RE.findall(text)

    def _bpe(self, symbols: list[str]) -> list[str]:
        """Apply BPE merges to a list of symbols (byte-level unicode chars).

        Merge priority follows the order in merges.txt: highest priority
        (earliest in file) is merged first.
        """
        if not self.merges or len(symbols) <= 1:
            return symbols

        # Build merge priority: (pair) → rank (lower = higher priority)
        merge_rank = {pair: i for i, pair in enumerate(self.merges)}

        while len(symbols) >= 2:
            # Find the pair with lowest merge rank (highest priority)
            best_rank = float("inf")
            best_idx = -1
            for i in range(len(symbols) - 1):
                pair = (symbols[i], symbols[i + 1])
                rank = merge_rank.get(pair, float("inf"))
                if rank < best_rank:
                    best_rank = rank
                    best_idx = i

            if best_rank == float("inf"):
                break  # No more applicable merges

            # Merge the best pair
            merged = symbols[best_idx] + symbols[best_idx + 1]
            symbols = symbols[:best_idx] + [merged] + symbols[best_idx + 2:]

        return symbols
