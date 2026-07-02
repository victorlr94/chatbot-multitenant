"""VectorStore sobre ChromaDB embebido (persistente en disco), una colección por tenant."""

from __future__ import annotations

from pathlib import Path

import chromadb

from chatbot_core.types import Chunk, ScoredChunk


class ChromaVectorStore:
    def __init__(self, path: Path, collection_name: str) -> None:
        self._client = chromadb.PersistentClient(path=str(path))
        self._collection_name = collection_name
        # Distancia coseno para que score = 1 - distancia sea comparable entre modelos.
        self._collection = self._client.get_or_create_collection(
            name=collection_name, metadata={"hnsw:space": "cosine"}
        )

    def add(self, chunks: list[Chunk], embeddings: list[list[float]]) -> None:
        if not chunks:
            return
        self._collection.add(
            ids=[c.id for c in chunks],
            documents=[c.text for c in chunks],
            metadatas=[dict(c.metadata) for c in chunks],
            embeddings=embeddings,
        )

    def query(self, embedding: list[float], k: int) -> list[ScoredChunk]:
        if self.count() == 0:
            return []
        result = self._collection.query(
            query_embeddings=[embedding],
            n_results=min(k, self.count()),
            include=["documents", "metadatas", "distances"],
        )
        ids = result["ids"][0]
        documents = (result.get("documents") or [[]])[0] or []
        metadatas = (result.get("metadatas") or [[]])[0] or []
        distances = (result.get("distances") or [[]])[0] or []

        scored: list[ScoredChunk] = []
        for chunk_id, text, meta, distance in zip(
            ids, documents, metadatas, distances, strict=True
        ):
            metadata = {str(k_): str(v) for k_, v in (meta or {}).items()}
            chunk = Chunk(id=chunk_id, text=text, metadata=metadata)
            scored.append(ScoredChunk(chunk=chunk, score=1.0 - float(distance)))
        return scored

    def clear(self) -> None:
        self._client.delete_collection(self._collection_name)
        self._collection = self._client.get_or_create_collection(
            name=self._collection_name, metadata={"hnsw:space": "cosine"}
        )

    def count(self) -> int:
        return int(self._collection.count())
