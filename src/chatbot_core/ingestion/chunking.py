"""Chunking por párrafos con límite de tamaño y solapamiento.

Estrategia simple y determinista: agrupa párrafos hasta `max_chars`; si un párrafo
excede el límite, se parte por caracteres con `overlap` para no cortar contexto.
"""

from __future__ import annotations

from chatbot_core.types import Chunk, Document


def _split_long_text(text: str, max_chars: int, overlap: int) -> list[str]:
    # Garantizar progreso hacia adelante aunque overlap >= max_chars.
    safe_overlap = min(overlap, max_chars - 1)
    parts: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        parts.append(text[start:end])
        if end == len(text):
            break
        start = end - safe_overlap
    return parts


def chunk_document(doc: Document, max_chars: int = 1200, overlap: int = 150) -> list[Chunk]:
    paragraphs = [p.strip() for p in doc.text.split("\n\n") if p.strip()]

    pieces: list[str] = []
    current: list[str] = []
    current_len = 0
    for para in paragraphs:
        if len(para) > max_chars:
            if current:
                pieces.append("\n\n".join(current))
                current, current_len = [], 0
            pieces.extend(_split_long_text(para, max_chars, overlap))
            continue
        if current_len + len(para) > max_chars and current:
            pieces.append("\n\n".join(current))
            current, current_len = [], 0
        current.append(para)
        current_len += len(para)
    if current:
        pieces.append("\n\n".join(current))

    return [
        Chunk(id=f"{doc.id}::{i}", text=piece, metadata=dict(doc.metadata))
        for i, piece in enumerate(pieces)
    ]
