"""Embedder vía LiteLLM: en el MVP usa Ollama (bge-m3, multilingüe); en cloud, el que toque."""

from __future__ import annotations

import litellm


class LiteLLMEmbedder:
    def __init__(self, model: str, api_base: str | None = None) -> None:
        self._model = model
        self._api_base = api_base

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        response = litellm.embedding(
            model=self._model,
            input=texts,
            api_base=self._api_base,
        )
        # LiteLLM devuelve los embeddings en el orden de entrada.
        return [item["embedding"] for item in response["data"]]
