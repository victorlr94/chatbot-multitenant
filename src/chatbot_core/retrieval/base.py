"""Contratos de la capa de retrieval: embeddings y vector store intercambiables."""

from __future__ import annotations

from typing import Protocol

from chatbot_core.types import Chunk, ScoredChunk


class Embedder(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...


class VectorStore(Protocol):
    def add(self, chunks: list[Chunk], embeddings: list[list[float]]) -> None: ...

    def query(self, embedding: list[float], k: int) -> list[ScoredChunk]: ...

    def clear(self) -> None:
        """Vacía la colección (re-ingesta desde cero)."""
        ...

    def count(self) -> int: ...
