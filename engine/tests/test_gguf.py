"""Tests for GGUF parser."""

from pathlib import Path

import pytest

from engine.gguf import GGUFParser, GGML_TYPE_NAMES


class TestGGUFParser:
    def test_parse_header(self, tiny_gguf: Path):
        with GGUFParser(tiny_gguf) as gp:
            d = gp.data
            assert d is not None
            assert d.version == 3
            assert d.n_tensors > 0
            assert "general.alignment" in d.metadata
            assert d.metadata["general.alignment"] == 32

    def test_tensor_count(self, tiny_gguf: Path):
        with GGUFParser(tiny_gguf) as gp:
            d = gp.data
            # 3 shared + 2 layers × 2 = 7 tensors
            assert d.n_tensors == 21  # 3 shared + 2 layers × 9 tensors

    def test_tensor_names(self, tiny_gguf: Path):
        with GGUFParser(tiny_gguf) as gp:
            names = gp.tensor_names()
            assert "token_embd.weight" in names
            assert "output_norm.weight" in names
            assert "output.weight" in names
            assert "blk.0.attn_norm.weight" in names
            assert "blk.1.ffn_down.weight" in names

    def test_tensor_shapes(self, tiny_gguf: Path):
        with GGUFParser(tiny_gguf) as gp:
            for t in gp.data.tensors:
                if t.name == "token_embd.weight":
                    assert t.shape == (256, 16)
                elif t.name == "output_norm.weight":
                    assert t.shape == (16,)
                elif t.name == "blk.0.attn_norm.weight":
                    assert t.shape == (16,)

    def test_get_tensor(self, tiny_gguf: Path):
        import numpy as np
        with GGUFParser(tiny_gguf) as gp:
            t = gp.get_tensor("token_embd.weight")
            assert t.shape == (256, 16)
            assert t.dtype == np.float16

    def test_get_tensor_not_found(self, tiny_gguf: Path):
        with GGUFParser(tiny_gguf) as gp:
            with pytest.raises(KeyError, match="nonexistent"):
                gp.get_tensor("nonexistent.weight")

    def test_not_a_gguf(self, tmp_path: Path):
        fake = tmp_path / "not_gguf.bin"
        fake.write_bytes(b"NOTAGGUF" + b"\x00" * 100)
        with pytest.raises(ValueError, match="Not a GGUF file"):
            parser = GGUFParser(fake)
            parser.load()

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            GGUFParser("/nonexistent/model.gguf")

    def test_context_manager(self, tiny_gguf: Path):
        parser = GGUFParser(tiny_gguf)
        with parser:
            assert parser.data is not None
        assert parser._mm is None  # closed
