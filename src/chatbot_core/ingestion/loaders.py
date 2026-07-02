"""Carga de documentos del corpus de un tenant: markdown, texto plano y PDF."""

from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader

from chatbot_core.types import Document

TEXT_SUFFIXES = {".md", ".txt"}
PDF_SUFFIXES = {".pdf"}


def _load_pdf(path: Path) -> str:
    reader = PdfReader(str(path))
    return "\n\n".join(page.extract_text() or "" for page in reader.pages)


def load_documents(docs_dir: Path) -> list[Document]:
    """Carga recursivamente todos los documentos soportados de un directorio."""
    if not docs_dir.exists():
        raise FileNotFoundError(f"No existe el directorio de documentos: {docs_dir}")

    documents: list[Document] = []
    for path in sorted(docs_dir.rglob("*")):
        if not path.is_file():
            continue
        suffix = path.suffix.lower()
        if suffix in TEXT_SUFFIXES:
            text = path.read_text(encoding="utf-8")
        elif suffix in PDF_SUFFIXES:
            text = _load_pdf(path)
        else:
            continue
        if not text.strip():
            continue
        relative = path.relative_to(docs_dir).as_posix()
        documents.append(Document(id=relative, text=text, metadata={"source": relative}))
    return documents
