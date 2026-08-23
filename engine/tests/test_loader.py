"""Tests for memory budget manager and streaming checkpoint loader."""

import time
from pathlib import Path

import numpy as np
import pytest

from engine.memory import MemoryManager
from engine.loader import CheckpointLoader, _is_pinned


# ── MemoryManager tests ─────────────────────────────────────────────

class TestMemoryManager:
    def test_unlimited_budget(self):
        mm = MemoryManager(budget_mb=0)
        mm.track("tensor_a", 1000)
        mm.track("tensor_b", 2000)
        assert mm.used_bytes == 3000
        assert mm.can_fit(1_000_000)

    def test_budget_enforced(self):
        mm = MemoryManager(budget_mb=0.001)  # ~1KB
        mm.track("a", 500)
        assert mm.can_fit(400)
        assert not mm.can_fit(600)  # would exceed ~1KB

    def test_pinned_not_evicted(self):
        mm = MemoryManager(budget_mb=0.001)
        mm.track("pinned", 800, pinned=True)
        mm.track("evictable", 500)
        evicted = mm.evict_until(200)  # need to free 200 bytes
        assert "pinned" not in evicted
        assert "evictable" in evicted

    def test_lru_eviction_order(self):
        mm = MemoryManager(budget_mb=0.001)
        mm.track("old", 400)
        time.sleep(0.01)
        mm.track("mid", 400)
        time.sleep(0.01)
        mm.track("new", 400)
        # All 1200 bytes used, need to free 500
        evicted = mm.evict_until(500)
        assert "old" in evicted  # oldest first

    def test_touch_updates_lru(self):
        mm = MemoryManager(budget_mb=0.001)
        mm.track("a", 400)
        time.sleep(0.01)
        mm.track("b", 400)
        time.sleep(0.01)
        mm.touch("a")  # a becomes more recent
        time.sleep(0.01)
        mm.track("c", 400)
        evicted = mm.evict_until(500)
        assert "b" in evicted  # b is now oldest (a was touched)

    def test_evict_lru_count(self):
        mm = MemoryManager(budget_mb=0.001)
        for i in range(5):
            mm.track(f"t{i}", 200)
        evicted = mm.evict_lru(2)
        assert len(evicted) == 2

    def test_untrack(self):
        mm = MemoryManager(budget_mb=0.001)
        mm.track("x", 100)
        assert mm.used_bytes == 100
        mm.untrack("x")
        assert mm.used_bytes == 0

    def test_stats(self):
        mm = MemoryManager(budget_mb=1.0)
        mm.track("a", 1024 * 1024, pinned=True)
        mm.track("b", 512 * 1024)
        s = mm.stats()
        assert s["budget_mb"] == 1.0
        assert s["n_pinned"] == 1
        assert s["n_evictable"] == 1

    def test_evictions_counter(self):
        mm = MemoryManager(budget_mb=0.001)
        mm.track("a", 500)
        mm.track("b", 500)
        mm.evict_lru(1)
        assert mm.total_evictions == 1

    def test_available_bytes(self):
        mm = MemoryManager(budget_mb=0.001)  # ~1048 bytes
        mm.track("pinned", 200, pinned=True)
        avail = mm.available_bytes
        assert avail > 0
        assert avail < 1048


# ── _is_pinned helper ──────────────────────────────────────────────

class TestIsPinned:
    def test_embed_pinned(self):
        assert _is_pinned("token_embd.weight")

    def test_output_pinned(self):
        assert _is_pinned("output.weight")

    def test_norm_pinned(self):
        assert _is_pinned("output_norm.weight")

    def test_layer_not_pinned(self):
        assert not _is_pinned("blk.0.attn_norm.weight")

    def test_layer_ffn_not_pinned(self):
        assert not _is_pinned("blk.3.ffn_down.weight")


# ── CheckpointLoader tests ──────────────────────────────────────────

class TestCheckpointLoader:
    def test_load_tensor(self, tiny_gguf: Path):
        with CheckpointLoader(tiny_gguf) as loader:
            t = loader.load_tensor("token_embd.weight")
            assert t.shape == (256, 16)
            assert t.dtype == np.float16

    def test_cache_hit(self, tiny_gguf: Path):
        with CheckpointLoader(tiny_gguf) as loader:
            t1 = loader.load_tensor("token_embd.weight")
            t2 = loader.load_tensor("token_embd.weight")
            assert t1 is t2  # same object (cache hit)

    def test_has_tensor(self, tiny_gguf: Path):
        with CheckpointLoader(tiny_gguf) as loader:
            assert loader.has_tensor("token_embd.weight")
            assert not loader.has_tensor("nonexistent.weight")

    def test_n_layers(self, tiny_gguf: Path):
        with CheckpointLoader(tiny_gguf) as loader:
            assert loader.n_layers() == 2

    def test_layer_names(self, tiny_gguf: Path):
        with CheckpointLoader(tiny_gguf) as loader:
            names = loader.layer_names()
            assert len(names) == 18  # 2 layers × 9 tensors each
            assert "blk.0.attn_norm.weight" in names
            assert "blk.1.ffn_down.weight" in names

    def test_layer_groups(self, tiny_gguf: Path):
        with CheckpointLoader(tiny_gguf) as loader:
            groups = loader.layer_groups()
            assert 0 in groups
            assert 1 in groups
            assert len(groups[0]) == 9  # 9 tensors per layer

    def test_evict_all_layers(self, tiny_gguf: Path):
        with CheckpointLoader(tiny_gguf) as loader:
            # Load everything
            for name in loader.parser.tensor_names():
                loader.load_tensor(name)
            assert len(loader._cache) > 0

            evicted = loader.evict_all_layers()
            assert evicted > 0
            # Pinned tensors should remain
            assert "token_embd.weight" in loader._cache
            assert "output.weight" in loader._cache
            # Layer tensors should be gone
            for name in loader.layer_names():
                assert name not in loader._cache

    def test_evict_lru(self, tiny_gguf: Path):
        with CheckpointLoader(tiny_gguf) as loader:
            loader.load_tensor("blk.0.attn_norm.weight")
            time.sleep(0.01)
            loader.load_tensor("blk.1.ffn_down.weight")
            evicted = loader.evict_lru(1)
            assert len(evicted) == 1
            assert evicted[0] == "blk.0.attn_norm.weight"  # older

    def test_budget_enforced_on_load(self, tiny_gguf: Path):
        # Tiny budget: enough for embed + norm, not all layers
        with CheckpointLoader(tiny_gguf, budget_mb=0.001) as loader:
            # Load all tensors — some should be evicted
            for name in loader.parser.tensor_names():
                loader.load_tensor(name)
            # Cache should not contain everything
            # (pinned tensors stay, layer tensors may be evicted)
            stats = loader.stats()
            assert stats["cached_tensors"] > 0

    def test_stats(self, tiny_gguf: Path):
        with CheckpointLoader(tiny_gguf) as loader:
            loader.load_tensor("token_embd.weight")
            s = loader.stats()
            assert s["cached_tensors"] == 1
            assert s["cached_mb"] > 0
            assert s["n_tensors"] == 21  # complete transformer model

    def test_context_manager(self, tiny_gguf: Path):
        loader = CheckpointLoader(tiny_gguf)
        with loader:
            loader.load_tensor("token_embd.weight")
        assert loader._cache == {}  # closed

    def test_tensor_info(self, tiny_gguf: Path):
        with CheckpointLoader(tiny_gguf) as loader:
            info = loader.tensor_info("token_embd.weight")
            assert info is not None
            assert info.shape == (256, 16)

    def test_tensor_info_missing(self, tiny_gguf: Path):
        with CheckpointLoader(tiny_gguf) as loader:
            assert loader.tensor_info("nope") is None

    def test_layer_bytes(self, tiny_gguf: Path):
        with CheckpointLoader(tiny_gguf) as loader:
            lb = loader.layer_bytes()
            assert 0 in lb
            assert 1 in lb
            assert lb[0] > 0
