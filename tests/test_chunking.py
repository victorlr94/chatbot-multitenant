from chatbot_core.ingestion.chunking import chunk_document
from chatbot_core.types import Document


def test_short_document_single_chunk() -> None:
    doc = Document(id="a.md", text="Hola mundo.\n\nSegundo párrafo.", metadata={"source": "a.md"})
    chunks = chunk_document(doc, max_chars=1000)
    assert len(chunks) == 1
    assert "Hola mundo." in chunks[0].text
    assert chunks[0].metadata["source"] == "a.md"


def test_paragraphs_grouped_under_limit() -> None:
    paragraphs = [f"Párrafo {i} " + "x" * 80 for i in range(10)]
    doc = Document(id="b.md", text="\n\n".join(paragraphs))
    chunks = chunk_document(doc, max_chars=200)
    assert len(chunks) > 1
    assert all(len(c.text) <= 250 for c in chunks)


def test_long_paragraph_split_with_overlap() -> None:
    doc = Document(id="c.md", text="a" * 500)
    chunks = chunk_document(doc, max_chars=200, overlap=50)
    assert len(chunks) >= 3
    # El solapamiento hace que el final de un chunk aparezca al inicio del siguiente.
    assert chunks[0].text[-50:] == chunks[1].text[:50]


def test_chunk_ids_are_unique() -> None:
    doc = Document(id="d.md", text="\n\n".join(["parrafo " * 30] * 5))
    chunks = chunk_document(doc, max_chars=100)
    ids = [c.id for c in chunks]
    assert len(ids) == len(set(ids))
