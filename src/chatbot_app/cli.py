"""Canal CLI: chat interactivo en terminal e ingesta del corpus.

Uso:
    uv run chatbot ingest   # indexar el corpus del tenant activo
    uv run chatbot chat     # conversar en la terminal
"""

from __future__ import annotations

import uuid

import typer

from chatbot_app.bootstrap import build_context, ingest_tenant

app = typer.Typer(help="Chatbot multi-tenant: RAG + citas", no_args_is_help=True)


@app.command()
def ingest() -> None:
    """(Re)indexa la base de conocimiento del tenant activo."""
    count = ingest_tenant()
    typer.echo(f"Ingesta completa: {count} chunks indexados.")


@app.command()
def chat() -> None:
    """Conversación interactiva en la terminal (canal de pruebas del MVP)."""
    context = build_context()
    session_id = uuid.uuid4().hex[:12]
    typer.echo(
        f"Chat con {context.tenant.name} [{context.settings.llm_model}] — "
        "escribe 'salir' para terminar.\n"
    )
    while True:
        try:
            message = typer.prompt("Tú", prompt_suffix="> ")
        except (typer.Abort, EOFError):
            break
        if message.strip().lower() in {"salir", "exit", "quit"}:
            break
        result = context.pipeline.handle(session_id, message, channel="cli")
        typer.echo(f"\nBot> {result.reply}\n")


if __name__ == "__main__":
    app()
