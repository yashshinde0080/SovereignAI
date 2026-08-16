"""Pins the honest FullRAM fit check in ``MemoryManager.suggest_mode``.

Measured 2026-08-16 (reviews/benchmark-fullram-2026-08-16.md): FullRAM /
transformers materializes weights in the compute dtype, so a Q4 GGUF uses
~4x its file size in RAM (469 MB file -> ~2 GB RSS delta on both the CPU
fp32 and CUDA fp16 paths) and ~2x its file size in VRAM (fp16 storage).
Full fp16/fp32 repos materialize at ~1-2x.

These tests lock in that behavior so "auto" means FullRAM only for models
that actually fit, and so a ``None`` metadata never crashes the legacy path
(regression: ``a and b or c`` precedence evaluated ``model_metadata.get``
on None).
"""
import pytest

from app.core.memory_manager import MemoryManager

MB = 1024 ** 2
GB = 1024 ** 3

GGUF_05B = 469 * MB          # qwen2.5-0.5b Q4_K_M file size, measured box
GGUF_3B = int(2.1 * GB)      # qwen2.5-3b Q4_K_M file size
FULL_05B = 1 * GB            # full fp16 safetensors repo for a 0.5B

GGUF_META = {"quant_method": "gguf", "family": "gguf"}
FULL_META = {"quant_method": "none", "family": "qwen2"}


class _FakeVMem:
    def __init__(self, available_bytes):
        self.available = available_bytes


def _make_mm(monkeypatch, available_ram_gb, cuda=False, free_vram_gb=4.0):
    mm = MemoryManager()
    monkeypatch.setattr(
        "psutil.virtual_memory",
        lambda: _FakeVMem(int(available_ram_gb * GB)),
    )
    monkeypatch.setattr("torch.cuda.is_available", lambda: cuda)
    if cuda:
        # torch.cuda.mem_get_info() returns (free, total) — the code reads the
        # FIRST element as free VRAM, so both entries must be the free amount.
        monkeypatch.setattr(
            "torch.cuda.mem_get_info",
            lambda: (int(free_vram_gb * GB), int(free_vram_gb * GB)),
        )
    return mm


def test_gguf_fullram_needs_4x_file_size(monkeypatch):
    """Same 469 MB file, 2 GB available: GGUF (4x -> 2.16 GB need) must NOT
    pick fullram; full-repo metadata (2x -> 1.08 GB need) fits."""
    mm = _make_mm(monkeypatch, available_ram_gb=2.0, cuda=False)

    assert mm.suggest_mode(GGUF_05B, GGUF_META) == "layerstream"
    assert mm.suggest_mode(GGUF_05B, FULL_META) == "fullram"


def test_gguf_detected_by_quant_method_or_family(monkeypatch):
    """Both metadata signals route to the 4x residency, independently."""
    mm = _make_mm(monkeypatch, available_ram_gb=2.0, cuda=False)

    assert mm.suggest_mode(GGUF_05B, {"quant_method": "gguf"}) == "layerstream"
    assert mm.suggest_mode(GGUF_05B, {"family": "gguf"}) == "layerstream"


def test_gguf_fits_when_ram_available(monkeypatch):
    """Boundary: 3 GB available covers the 2.16 GB GGUF need -> fullram."""
    mm = _make_mm(monkeypatch, available_ram_gb=3.0, cuda=False)

    assert mm.suggest_mode(GGUF_05B, GGUF_META) == "fullram"


def test_3b_gguf_never_fullram_on_8gb_class_ram(monkeypatch):
    """A 3B Q4 (2.1 GB file -> ~9.7 GB fp32) must not be handed to FullRAM
    even with 6 GB available — that is the measured OOM the old 1.1x check
    would have caused."""
    mm = _make_mm(monkeypatch, available_ram_gb=6.0, cuda=False)

    assert mm.suggest_mode(GGUF_3B, GGUF_META) == "layerstream"


def test_cuda_vram_check_uses_gguf_fp16_residency(monkeypatch):
    """On CUDA, GGUF is materialized fp16 (~2x file) in VRAM: a 3B Q4 needs
    4.83 GB > 4 GB VRAM so it falls through to the RAM check; a full fp16
    0.5B needs 1.15 GB and fits."""
    mm = _make_mm(monkeypatch, available_ram_gb=1.0, cuda=True, free_vram_gb=4.0)

    assert mm.suggest_mode(GGUF_3B, GGUF_META) == "layerstream"
    assert mm.suggest_mode(FULL_05B, FULL_META) == "fullram"


def test_no_metadata_falls_back_to_legacy_threshold(monkeypatch):
    """Regression: ``None`` metadata used to raise AttributeError on the
    ``or model_metadata.get("id")`` arm (operator precedence — the crash sat
    outside the try/except). Must fall through to the threshold path."""
    mm = _make_mm(monkeypatch, available_ram_gb=2.0, cuda=False)

    result = mm.suggest_mode(GGUF_05B, None)

    assert result == "fullram"  # legacy assumption: 469 MB * 2 * 1.15 < 2 GB


def test_metadata_without_name_or_id_skips_llmfit(monkeypatch):
    """Metadata carrying only quant_method/family must not crash and must
    reach the residency logic (no llmfit ImportError dance required)."""
    mm = _make_mm(monkeypatch, available_ram_gb=2.0, cuda=False)

    assert mm.suggest_mode(GGUF_05B, {"quant_method": "gguf"}) == "layerstream"
    assert mm.suggest_mode(GGUF_05B, {"family": "gguf"}) == "layerstream"
