"""Retriever: consulta el vector store y filtra por score mínimo.

El umbral protege contra respuestas fabricadas: si nada supera `min_score`,
el agente debe decir que no tiene esa información, no inventarla.
"""

from __future__ import annotations

from chatbot_core.retrieval.base import Embedder, VectorStore
from chatbot_core.types import ScoredChunk


class Retriever:
    def __init__(
        self,
        store: VectorStore,
        embedder: Embedder,
        k: int = 4,
        min_score: float = 0.35,
    ) -> None:
        self._store = store
        self._embedder = embedder
        self._k = k
        self._min_score = min_score

    def retrieve(self, query: str) -> list[ScoredChunk]:
        embedding = self._embedder.embed([query])[0]
        results = self._store.query(embedding, self._k)
        return [r for r in results if r.score >= self._min_score]
