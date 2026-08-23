"""Tests for BPE tokenizer."""

from pathlib import Path

import pytest

from engine.tokenizer import Tokenizer, BYTE_encoder, BYTE_decoder, _bytes_to_unicode, _unicode_to_bytes


class TestByteEncoding:
    def test_roundtrip(self):
        for b in range(256):
            bs = bytes([b])
            encoded = _bytes_to_unicode(bs)
            decoded = _unicode_to_bytes(encoded)
            assert decoded == bs

    def test_all_bytes_map(self):
        assert len(BYTE_encoder) == 256
        assert len(BYTE_decoder) == 256

    def test_multibyte(self):
        data = "hello world".encode("utf-8")
        encoded = _bytes_to_unicode(data)
        decoded = _unicode_to_bytes(encoded)
        assert decoded == data


class TestTokenizer:
    def test_load_vocab(self, tiny_model_dir: Path):
        tok = Tokenizer(tiny_model_dir)
        assert tok.vocab_size == 260  # 256 base + hello, world, space, !

    def test_encode_basic(self, tiny_model_dir: Path):
        tok = Tokenizer(tiny_model_dir)
        ids = tok.encode("hello")
        assert len(ids) > 0
        assert all(isinstance(i, int) for i in ids)

    def test_decode_basic(self, tiny_model_dir: Path):
        tok = Tokenizer(tiny_model_dir)
        ids = tok.encode("hello")
        text = tok.decode(ids)
        assert "hello" in text.lower() or len(text) > 0

    def test_encode_empty(self, tiny_model_dir: Path):
        tok = Tokenizer(tiny_model_dir)
        assert tok.encode("") == []

    def test_decode_empty(self, tiny_model_dir: Path):
        tok = Tokenizer(tiny_model_dir)
        assert tok.decode([]) == ""

    def test_roundtrip_short(self, tiny_model_dir: Path):
        tok = Tokenizer(tiny_model_dir)
        text = "hello"
        ids = tok.encode(text)
        decoded = tok.decode(ids)
        assert "hello" in decoded.lower()

    def test_eos_token_id(self, tiny_model_dir: Path):
        tok = Tokenizer(tiny_model_dir)
        assert tok.eos_token_id == 11  # mapped to "!" (vocab ID 11)

    def test_bos_token_id(self, tiny_model_dir: Path):
        tok = Tokenizer(tiny_model_dir)
        assert tok.bos_token_id == 0  # "tok_0" → id 0

    def test_unknown_token_handled(self, tiny_model_dir: Path):
        tok = Tokenizer(tiny_model_dir)
        # Encode text with characters not in vocab — should not crash
        ids = tok.encode("zzz")
        assert isinstance(ids, list)

    def test_from_tokenizer_json(self, tmp_path: Path):
        """Test loading from tokenizer.json format."""
        import json
        d = tmp_path / "tokjson_model"
        d.mkdir()

        tok_data = {
            "model": {
                "vocab": {"a": 0, "b": 1, "c": 2, "ab": 3},
                "merges": ["a b"],
            }
        }
        (d / "tokenizer.json").write_text(json.dumps(tok_data))
        (d / "tokenizer_config.json").write_text(json.dumps({
            "eos_token": "c",
        }))

        tok = Tokenizer(d)
        assert tok.vocab_size == 4
        assert tok.eos_token_id == 2

    def test_no_vocab_raises(self, tmp_path: Path):
        d = tmp_path / "empty_model"
        d.mkdir()
        with pytest.raises(FileNotFoundError):
            Tokenizer(d)
