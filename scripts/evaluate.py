"""Evaluación end-to-end del chatbot contra el dataset del tenant activo.

Corre cada pregunta por el pipeline real (LLM incluido) y verifica:
- casos con `expected_keywords`: la respuesta contiene todas las palabras clave;
- casos con `expect_refusal`: la respuesta parece un rechazo (no responde el tema).

Uso como gate: correr antes y después de cambiar modelo/prompt y comparar.

    uv run python scripts/evaluate.py
"""

from __future__ import annotations

import sys
import time
import unicodedata
import uuid
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from chatbot_app.bootstrap import build_context  # noqa: E402

REFUSAL_MARKERS = [
    "solo puedo ayudarte",
    "no puedo",
    "no dispongo",
    "no tengo esa informacion",
    "no tengo informacion",
    "fuera de",
    "lo siento",
]


def _normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def looks_like_refusal(reply: str) -> bool:
    normalized = _normalize(reply)
    return any(marker in normalized for marker in REFUSAL_MARKERS)


def main() -> int:
    context = build_context()
    dataset_path = Path("evaluations") / f"{context.tenant.id}.yaml"
    cases = yaml.safe_load(dataset_path.read_text(encoding="utf-8"))["cases"]

    print(f"Evaluando {len(cases)} casos | tenant={context.tenant.id} "
          f"| modelo={context.settings.llm_model}\n")

    passed = 0
    for case in cases:
        session = f"eval-{uuid.uuid4().hex[:8]}"  # sesión limpia por caso
        started = time.perf_counter()
        result = context.pipeline.handle(session, case["question"], channel="eval")
        elapsed = time.perf_counter() - started

        if case.get("expect_refusal"):
            ok = result.refused or looks_like_refusal(result.reply)
            detail = "esperaba rechazo"
        else:
            keywords = case.get("expected_keywords", [])
            normalized_reply = _normalize(result.reply)
            missing = [k for k in keywords if _normalize(k) not in normalized_reply]
            ok = not missing
            detail = f"faltan keywords: {missing}" if missing else "keywords presentes"

        passed += ok
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] {case['id']} ({elapsed:.1f}s) — {detail}")
        if not ok:
            print(f"        pregunta:  {case['question']}")
            print(f"        respuesta: {result.reply[:300]}")

    total = len(cases)
    print(f"\nResultado: {passed}/{total} ({100 * passed / total:.0f}%)")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
