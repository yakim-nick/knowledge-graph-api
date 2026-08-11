"""Split raw document bytes into token-bounded chunks for extraction and embedding."""

from __future__ import annotations

import logging

import tiktoken

from src.models.schemas import DocumentChunk

logger = logging.getLogger(__name__)


class DocumentParser:
    """Chunk documents into overlapping token windows sized for the LLM context."""

    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200) -> None:
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self._tokenizer = tiktoken.get_encoding("cl100k_base")

    def _count_tokens(self, text: str) -> int:
        """Return the number of tokens in *text* using the configured tokenizer."""
        return len(self._tokenizer.encode(text))

    def _split_by_tokens(self, text: str) -> list[str]:
        """Split *text* into overlapping token windows of chunk_size tokens.

        The window slides forward by ``chunk_size - chunk_overlap`` tokens so
        consecutive chunks share context and no entity is cut off mid-sentence.
        """
        tokens = self._tokenizer.encode(text)
        chunks: list[str] = []
        start = 0
        while start < len(tokens):
            end = min(start + self.chunk_size, len(tokens))
            chunk_tokens = tokens[start:end]
            chunks.append(self._tokenizer.decode(chunk_tokens))
            start += self.chunk_size - self.chunk_overlap
        return chunks

    def _build_chunk(self, text: str, index: int, filename: str) -> DocumentChunk:
        """Wrap a text section into a DocumentChunk with its position and source file."""
        return DocumentChunk(text=text.strip(), index=index, document_name=filename)

    async def parse(self, content: bytes, filename: str) -> list[DocumentChunk]:
        """Decode *content* and return DocumentChunks, or [] for empty documents.

        Short documents are kept as a single chunk; longer ones are split into
        overlapping token windows.
        """
        raw_text = content.decode("utf-8", errors="replace")
        token_count = self._count_tokens(raw_text)
        if token_count == 0:
            logger.warning(f"Empty document: {filename}")
            return []

        if token_count <= self.chunk_size:
            return [self._build_chunk(raw_text, 0, filename)]

        text_sections = self._split_by_tokens(raw_text)
        chunks = [
            self._build_chunk(section, i, filename)
            for i, section in enumerate(text_sections)
        ]
        logger.info(
            f"Parsed {filename}: {len(chunks)} chunks "
            f"({token_count} tokens, chunk_size={self.chunk_size})"
        )
        return chunks
