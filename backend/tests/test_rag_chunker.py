"""Chunker edge cases: abbreviations, decimals, initials, code blocks,
PDF line breaks, token-based overlap, token estimate."""

import pytest

from app.vectorstore.chunker import DocumentChunker


@pytest.fixture
def chunker():
    return DocumentChunker(chunk_size=512, chunk_overlap=64)


def test_empty_text_returns_no_chunks(chunker):
    assert chunker.chunk_text("", "d1") == []
    assert chunker.chunk_text("   \n  ", "d1") == []


def test_abbreviation_not_split(chunker):
    """Dr./e.g./etc. must not end a sentence."""
    text = "Dr. Smith went to Washington. He liked it there."
    sents = chunker._split_sentences(text)
    assert len(sents) == 2
    assert sents[0] == "Dr. Smith went to Washington."


def test_decimal_not_split(chunker):
    text = "Pi is 3.14 and tau is 6.28. Two constants."
    sents = chunker._split_sentences(text)
    assert len(sents) == 2
    assert "3.14 and tau is 6.28." in sents[0]


def test_initials_not_split(chunker):
    text = "J. K. Rowling wrote it. Then she stopped."
    sents = sentences = chunker._split_sentences(text)
    assert len(sents) == 2
    assert sents[0] == "J. K. Rowling wrote it."


def test_code_block_stays_atomic(chunker):
    """Fenced code must not be cleaned or split across sentences."""
    text = (
        "Intro paragraph here.\n\n"
        "```python\n"
        "def f(x):\n    return x.  # 1.5 then\n    'A. B'\n"
        "```\n\n"
        "Closing paragraph. With two sentences."
    )
    chunks = chunker.chunk_text(text, "d1")
    code_chunk = next(c for c in chunks if "def f(x):" in c.content)
    assert "```python" in code_chunk.content
    assert "```" in code_chunk.content
    # newlines inside the fence survived cleaning
    assert "\n" in code_chunk.content


def test_pdf_line_breaks_merged(chunker):
    """Single newlines inside a paragraph become spaces; hyphen breaks join.
    Goes through _clean_text, like the real chunk_text pipeline."""
    text = "The quick brown\nfox jumps over the lazy\ndog. Second sentence here."
    sents = chunker._split_sentences(chunker._clean_text(text))
    assert len(sents) == 2
    assert sents[0].startswith("The quick brown fox")


def test_hyphenated_line_break_joined(chunker):
    text = "This is an exam-\nple of hyphenation. Next one."
    sents = chunker._split_sentences(chunker._clean_text(text))
    assert "example" in sents[0]
    assert "-\n" not in sents[0]


def test_overlap_is_token_budgeted(chunker):
    """chunk_overlap=64 tokens ≈ 192 chars — trailing sentences of chunk N
    must reappear at the start of chunk N+1."""
    sents = [f"Sentence number {i} with some padding words here." for i in range(40)]
    text = " ".join(sents)
    chunks = chunker.chunk_text(text, "d1")
    assert len(chunks) > 1
    # the last ~30 chars of chunk 0 are repeated inside chunk 1
    assert chunks[0].content[-30:] in chunks[1].content


def test_force_split_overlap_uses_token_budget():
    c = DocumentChunker(chunk_size=64, chunk_overlap=16)
    text = "word " * 500
    chunks = c.chunk_text(text, "d1")
    assert len(chunks) > 1
    # token-based overlap (16 tokens ≈ 48 chars): consecutive chunks share content
    assert chunks[0].content[-30:] in chunks[1].content


def test_token_estimate_len3(chunker):
    assert chunker._estimate_tokens("a" * 99) == 33
    assert chunker._estimate_tokens("") == 1


def test_chunk_ids_sequential_after_split(chunker):
    text = "Word. " * 1000
    chunks = chunker.chunk_text(text, "d1")
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))
    assert chunks[0].chunk_id == "d1_chunk_000000"
