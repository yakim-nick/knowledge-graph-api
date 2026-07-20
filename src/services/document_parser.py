from __future__ import annotations

import logging

import tiktoken

from src.models.schemas import DocumentChunk

logger = logging.getLogger(__name__)


class DocumentParser:
    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200) -> None:
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self._tokenizer = tiktoken.get_encoding("cl100k_base")

    def _count_tokens(self, text: str) -> int:
        return len(self._tokenizer.encode(text))

    def _split_by_tokens(self, text: str) -> list[str]:
        tokens = self._tokenizer.encode(text)
        chunks: list[str] = []
        start = 0
        while start < len(tokens):
            end = min(start + self.chunk_size, len(tokens))
            chunk_tokens = tokens[start:end]
            chunks.append(self._tokenizer.decode(chunk_tokens))
            start += self.chunk_size - self.chunk_overlap
        return chunks

    async def parse(self, content: bytes, filename: str) -> list[DocumentChunk]:
        raw_text = content.decode("utf-8", errors="replace")
        token_count = self._count_tokens(raw_text)
        if token_count == 0:
            logger.warning(f"Empty document: {filename}")
            return []

        if token_count <= self.chunk_size:
            return [
                DocumentChunk(
                    text=raw_text.strip(),
                    index=0,
                    document_name=filename,
                )
            ]

        text_sections = self._split_by_tokens(raw_text)
        chunks = [
            DocumentChunk(
                text=section.strip(),
                index=i,
                document_name=filename,
            )
            for i, section in enumerate(text_sections)
        ]
        logger.info(
            f"Parsed {filename}: {len(chunks)} chunks "
            f"({token_count} tokens, chunk_size={self.chunk_size})"
        )
        return chunks
