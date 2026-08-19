"""Tests for CLI subcommands."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from engine.cli import main, cmd_info


class TestCLIInfo:
    def test_info_prints_config(self, tiny_transformer_gguf: Path, capsys):
        """info command prints model config."""
        with patch("sys.argv", ["engine", "info", str(tiny_transformer_gguf)]):
            main()
        captured = capsys.readouterr()
        assert "GGUF v3" in captured.out
        assert "Tensors:" in captured.out
        assert "vocab=" in captured.out

    def test_info_tensor_types(self, tiny_transformer_gguf: Path, capsys):
        with patch("sys.argv", ["engine", "info", str(tiny_transformer_gguf)]):
            main()
        captured = capsys.readouterr()
        assert "F16:" in captured.out

    def test_info_missing_file(self, tmp_path: Path, capsys):
        with patch("sys.argv", ["engine", "info", str(tmp_path / "nope.gguf")]):
            with pytest.raises(SystemExit):
                main()


class TestCLIRun:
    def test_run_basic(self, tiny_transformer_gguf: Path, tiny_model_dir: Path, capsys):
        """run command generates text."""
        # Copy tokenizer files next to the GGUF
        import shutil
        for f in tiny_model_dir.iterdir():
            shutil.copy2(f, tiny_transformer_gguf.parent / f.name)

        with patch("sys.argv", [
            "engine", "run", str(tiny_transformer_gguf),
            "-p", "hello", "-n", "3",
        ]):
            main()
        captured = capsys.readouterr()
        assert ">" in captured.out  # output prompt marker
        assert "tokens:" in captured.out

    def test_run_json_output(self, tiny_transformer_gguf: Path, tiny_model_dir: Path, capsys):
        import shutil
        for f in tiny_model_dir.iterdir():
            shutil.copy2(f, tiny_transformer_gguf.parent / f.name)

        with patch("sys.argv", [
            "engine", "run", str(tiny_transformer_gguf),
            "-p", "test", "-n", "2", "--json",
        ]):
            main()
        captured = capsys.readouterr()
        # JSON output should be parseable
        lines = [l for l in captured.out.strip().split("\n") if l.strip().startswith("{")]
        assert len(lines) > 0

    def test_run_greedy(self, tiny_transformer_gguf: Path, tiny_model_dir: Path, capsys):
        import shutil
        for f in tiny_model_dir.iterdir():
            shutil.copy2(f, tiny_transformer_gguf.parent / f.name)

        with patch("sys.argv", [
            "engine", "run", str(tiny_transformer_gguf),
            "-p", "test", "-n", "3", "-t", "0",
        ]):
            main()
        captured = capsys.readouterr()
        assert ">" in captured.out

    def test_run_missing_file(self, tmp_path: Path, capsys):
        with patch("sys.argv", [
            "engine", "run", str(tmp_path / "nope.gguf"), "-p", "hi",
        ]):
            with pytest.raises(SystemExit):
                main()


class TestCLIBench:
    def test_bench_prints_table(self, tiny_transformer_gguf: Path, tiny_model_dir: Path, capsys):
        import shutil
        for f in tiny_model_dir.iterdir():
            shutil.copy2(f, tiny_transformer_gguf.parent / f.name)

        with patch("sys.argv", [
            "engine", "bench", str(tiny_transformer_gguf),
            "--budgets", "0,64", "-n", "2",
        ]):
            main()
        captured = capsys.readouterr()
        assert "Budget" in captured.out
        assert "Tok/s" in captured.out

    def test_bench_with_prompt(self, tiny_transformer_gguf: Path, tiny_model_dir: Path, capsys):
        import shutil
        for f in tiny_model_dir.iterdir():
            shutil.copy2(f, tiny_transformer_gguf.parent / f.name)

        with patch("sys.argv", [
            "engine", "bench", str(tiny_transformer_gguf),
            "-p", "test prompt", "--budgets", "0", "-n", "2",
        ]):
            main()
        captured = capsys.readouterr()
        assert "test prompt" in captured.out
