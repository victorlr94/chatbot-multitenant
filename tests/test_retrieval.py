from pathlib import Path

from tests.conftest import FakeEmbedder

from chatbot_core.agent.tools.knowledge import NO_RESULTS_MESSAGE, build_search_kb_tool
from chatbot_core.retrieval.chroma_store import ChromaVectorStore
from chatbot_core.retrieval.retriever import Retriever
from chatbot_core.types import Chunk


def _store_with_corpus(tmp_path: Path) -> tuple[ChromaVectorStore, FakeEmbedder]:
    store = ChromaVectorStore(tmp_path / "chroma", collection_name="test")
    embedder = FakeEmbedder()
    chunks = [
        Chunk(
            id="precios::0",
            text="la limpieza dental cuesta 40 usd",
            metadata={"source": "precios.md"},
        ),
        Chunk(
            id="horarios::0",
            text="abrimos lunes a viernes de 9 a 18",
            metadata={"source": "horarios.md"},
        ),
        Chunk(
            id="garantia::0",
            text="los empastes tienen garantia de un año",
            metadata={"source": "politicas.md"},
        ),
    ]
    store.add(chunks, embedder.embed([c.text for c in chunks]))
    return store, embedder


def test_query_returns_most_similar_first(tmp_path: Path) -> None:
    store, embedder = _store_with_corpus(tmp_path)
    retriever = Retriever(store, embedder, k=2, min_score=0.0)

    results = retriever.retrieve("cuanto cuesta la limpieza dental")

    assert results
    assert results[0].chunk.metadata["source"] == "precios.md"
    assert results[0].score >= results[-1].score


def test_min_score_filters_unrelated(tmp_path: Path) -> None:
    store, embedder = _store_with_corpus(tmp_path)
    retriever = Retriever(store, embedder, k=3, min_score=0.99)

    assert retriever.retrieve("astronomia cuantica interplanetaria") == []


def test_empty_store_returns_nothing(tmp_path: Path) -> None:
    store = ChromaVectorStore(tmp_path / "chroma", collection_name="empty")
    retriever = Retriever(store, FakeEmbedder(), k=3, min_score=0.0)

    assert retriever.retrieve("cualquier cosa") == []


def test_clear_resets_collection(tmp_path: Path) -> None:
    store, _ = _store_with_corpus(tmp_path)
    assert store.count() == 3
    store.clear()
    assert store.count() == 0


def test_search_kb_tool_formats_sources(tmp_path: Path) -> None:
    store, embedder = _store_with_corpus(tmp_path)
    tool = build_search_kb_tool(Retriever(store, embedder, k=2, min_score=0.0))

    output = tool.handler({"query": "cuanto cuesta la limpieza dental"})

    assert "[fuente: precios.md" in output
    assert "40 usd" in output


def test_search_kb_tool_reports_no_results(tmp_path: Path) -> None:
    store, embedder = _store_with_corpus(tmp_path)
    tool = build_search_kb_tool(Retriever(store, embedder, k=2, min_score=0.99))

    assert tool.handler({"query": "tema sin relacion alguna"}) == NO_RESULTS_MESSAGE
    assert "Error" in tool.handler({})
