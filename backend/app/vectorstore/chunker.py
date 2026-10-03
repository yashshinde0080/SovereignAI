"""
Document chunker.
Splits documents into overlapping chunks for embedding.
No naive split. Proper boundary detection.
"""

import re
import logging
from typing import List

from app.schemas.vector_schemas import TextChunk

logger = logging.getLogger("sovereign.vectorstore.chunker")


class DocumentChunker:
    """
    Split text into overlapping chunks.
    Respects sentence boundaries when possible.
    """

    # Common abbreviations whose trailing dot must not end a sentence
    _ABBREVIATIONS = (
        "dr", "mr", "mrs", "ms", "prof", "sr", "jr", "st", "vs",
        "etc", "inc", "ltd", "co", "corp", "fig", "eq", "no", "vol",
        "ch", "pp", "al", "approx", "dept", "univ", "e.g", "i.e",
    )
    _PROTECT_CHAR = "\x01"  # sentinel for a protected period
    _CODE_FENCE = re.compile(r"```.*?(?:```|\Z)", re.DOTALL)

    def __init__(self, chunk_size: int = 512,
                 chunk_overlap: int = 64,
                 max_chunks: int = 10000):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap  # tokens; chars via len/3 estimate
        self.max_chunks = max_chunks

        # Sentence boundary pattern (period already end-of-sentence — the
        # splitter masks abbreviations/decimals/initials before splitting)
        self._sentence_pattern = re.compile(
            r'(?<=[.!?])[\'\")\]]*\s+(?=[A-Z"\'(0-9])'
        )

    @property
    def _overlap_chars(self) -> int:
        """Token-based overlap converted to chars via the len/3 estimate."""
        return self.chunk_overlap * 3

    def chunk_text(self, text: str,
                   document_id: str) -> List[TextChunk]:
        """
        Split text into overlapping chunks.

        Strategy:
        1. Try to split on sentence boundaries.
        2. If chunk too large, fall back to character split.
        3. Always maintain overlap.
        """
        if not text or not text.strip():
            return []

        # Clean text — fenced code blocks bypass prose cleaning so their
        # newlines survive (they are split atomically later)
        parts = []
        pos = 0
        for m in self._CODE_FENCE.finditer(text):
            if m.start() > pos:
                parts.append(self._clean_text(text[pos:m.start()]))
            parts.append(self._clean_code(m.group(0)))
            pos = m.end()
        if pos < len(text):
            parts.append(self._clean_text(text[pos:]))
        text = "\n".join(p for p in parts if p)

        # Split into sentences first
        sentences = self._split_sentences(text)

        # Build chunks from sentences
        chunks = self._build_chunks(sentences, document_id, text)

        if len(chunks) > self.max_chunks:
            logger.warning(
                f"Document {document_id}: {len(chunks)} chunks exceeds "
                f"max {self.max_chunks}. Truncating."
            )
            chunks = chunks[:self.max_chunks]

        logger.info(
            f"Document {document_id}: {len(chunks)} chunks created"
        )
        return chunks

    def _clean_text(self, text: str) -> str:
        """Clean prose while preserving paragraph structure.
        Never called on code blocks — see _clean_code."""
        text = text.replace('\x00', '')
        text = re.sub(r'\r\n?', '\n', text)
        # PDF hyphenated line breaks: "exam-\nple" -> "example"
        text = re.sub(r'(\w)-\n(\w)', r'\1\2', text)
        # Collapse horizontal whitespace only
        text = re.sub(r'[ \t]+', ' ', text)
        # PDF line breaks: single newline inside a paragraph -> space
        text = re.sub(r'(?<!\n)\n(?!\n)', ' ', text)
        # 3+ newlines -> paragraph break
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()

    def _clean_code(self, text: str) -> str:
        """Clean code blocks minimally — keep newlines intact."""
        return text.replace('\x00', '').replace('\r\n', '\n').replace('\r', '\n')

    def _protect_periods(self, text: str) -> str:
        """Mask periods that must not be treated as sentence ends:
        decimals (3.14), initials (J. Smith), known abbreviations (Dr., e.g.)."""
        text = re.sub(r'(?<=\d)\.(?=\d)', self._PROTECT_CHAR, text)
        text = re.sub(r'\b([A-Z])\.(?=\s+[A-Z])', r'\1' + self._PROTECT_CHAR, text)
        for abbr in self._ABBREVIATIONS:
            text = re.sub(
                r'\b' + re.escape(abbr) + r'\.(?=\s)',
                lambda m: m.group(0)[:-1] + self._PROTECT_CHAR,
                text, flags=re.IGNORECASE,
            )
        return text

    def _split_prose(self, text: str) -> List[str]:
        masked = self._protect_periods(text)
        parts = self._sentence_pattern.split(masked)
        return [
            self._unprotect(p).strip()
            for p in parts if p.strip()
        ]

    def _unprotect(self, text: str) -> str:
        return text.replace(self._PROTECT_CHAR, '.')

    def _split_sentences(self, text: str) -> List[str]:
        """Split into sentences; fenced code blocks are atomic."""
        sentences: List[str] = []
        pos = 0
        for m in self._CODE_FENCE.finditer(text):
            if m.start() > pos:
                sentences.extend(self._split_prose(text[pos:m.start()]))
            sentences.append(m.group(0).strip())
            pos = m.end()
        if pos < len(text):
            sentences.extend(self._split_prose(text[pos:]))
        return [s for s in sentences if s]

    def _build_chunks(self, sentences: List[str],
                      document_id: str,
                      original_text: str) -> List[TextChunk]:
        """
        Build chunks from sentences with overlap.
        """
        chunks = []
        current_chunk = []
        current_length = 0
        chunk_index = 0
        char_position = 0

        for sentence in sentences:
            sentence_length = len(sentence)

            # If single sentence exceeds chunk size, force split it
            if sentence_length > self.chunk_size:
                # Flush current chunk first
                if current_chunk:
                    chunk_text = ' '.join(current_chunk)
                    start_char = original_text.find(
                        current_chunk[0], max(0, char_position - 100)
                    )
                    if start_char == -1:
                        start_char = char_position

                    chunks.append(TextChunk(
                        chunk_id=self._generate_chunk_id(
                            document_id, chunk_index
                        ),
                        document_id=document_id,
                        content=chunk_text,
                        chunk_index=chunk_index,
                        start_char=start_char,
                        end_char=start_char + len(chunk_text),
                        token_count=self._estimate_tokens(chunk_text)
                    ))
                    chunk_index += 1
                    current_chunk = []
                    current_length = 0

                # Force split long sentence
                sub_chunks = self._force_split(
                    sentence, document_id, chunk_index, char_position
                )
                chunks.extend(sub_chunks)
                chunk_index += len(sub_chunks)
                char_position += sentence_length
                continue

            # Check if adding sentence would exceed chunk size
            if current_length + sentence_length + 1 > self.chunk_size:
                # Emit current chunk
                if current_chunk:
                    chunk_text = ' '.join(current_chunk)
                    start_char = original_text.find(
                        current_chunk[0], max(0, char_position - 100)
                    )
                    if start_char == -1:
                        start_char = char_position

                    chunks.append(TextChunk(
                        chunk_id=self._generate_chunk_id(
                            document_id, chunk_index
                        ),
                        document_id=document_id,
                        content=chunk_text,
                        chunk_index=chunk_index,
                        start_char=start_char,
                        end_char=start_char + len(chunk_text),
                        token_count=self._estimate_tokens(chunk_text)
                    ))
                    chunk_index += 1

                    # Overlap: keep trailing sentences up to the token budget
                    # (chunk_overlap tokens ≈ chunk_overlap*3 chars)
                    overlap_chars = 0
                    overlap_sentences = []
                    for s in reversed(current_chunk):
                        if overlap_chars + len(s) <= self._overlap_chars:
                            overlap_sentences.insert(0, s)
                            overlap_chars += len(s) + 1
                        else:
                            break

                    current_chunk = overlap_sentences
                    current_length = sum(
                        len(s) + 1 for s in current_chunk
                    )

            current_chunk.append(sentence)
            current_length += sentence_length + 1
            char_position += sentence_length + 1

        # Flush remaining
        if current_chunk:
            chunk_text = ' '.join(current_chunk)
            start_char = max(0, len(original_text) - len(chunk_text))
            chunks.append(TextChunk(
                chunk_id=self._generate_chunk_id(
                    document_id, chunk_index
                ),
                document_id=document_id,
                content=chunk_text,
                chunk_index=chunk_index,
                start_char=start_char,
                end_char=start_char + len(chunk_text),
                token_count=self._estimate_tokens(chunk_text)
            ))

        return chunks

    def _force_split(self, text: str, document_id: str,
                     start_index: int,
                     char_offset: int) -> List[TextChunk]:
        """Force split text that exceeds chunk size."""
        chunks = []
        pos = 0
        idx = start_index

        while pos < len(text):
            end = min(pos + self.chunk_size, len(text))

            # Try to find a word boundary
            if end < len(text):
                space_pos = text.rfind(' ', pos, end)
                if space_pos > pos:
                    end = space_pos

            chunk_content = text[pos:end].strip()
            if chunk_content:
                chunks.append(TextChunk(
                    chunk_id=self._generate_chunk_id(document_id, idx),
                    document_id=document_id,
                    content=chunk_content,
                    chunk_index=idx,
                    start_char=char_offset + pos,
                    end_char=char_offset + end,
                    token_count=self._estimate_tokens(chunk_content)
                ))
                idx += 1

            # Move with overlap (token budget → chars via len/3)
            pos = max(pos + 1, end - self._overlap_chars)

        return chunks

    def _generate_chunk_id(self, document_id: str,
                           chunk_index: int) -> str:
        """Generate deterministic chunk ID."""
        return f"{document_id}_chunk_{chunk_index:06d}"

    def _estimate_tokens(self, text: str) -> int:
        """
        Token estimate: len/3 (safe margin over the optimistic len/4 —
        undercounting busts the context budget). No tokenizer loaded at
        chunk time; swap for a real count if the embedder's tokenizer is
        ever available here.
        """
        return max(1, len(text) // 3)