"""Tools de agendamiento: exponen el motor de citas al agente.

Devuelven texto plano estructurado (no JSON crudo) porque los modelos pequeños
lo siguen mejor. Los errores de dominio se devuelven como mensajes explicativos
para que el agente los comunique, no como excepciones.
"""

from __future__ import annotations

from datetime import datetime, date
from typing import Any

_WEEKDAY_ES = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


def _date_label(d: date) -> str:
    return f"{d.isoformat()} ({_WEEKDAY_ES[d.weekday()]})"

from chatbot_core.agent.tools.base import Tool
from chatbot_core.scheduling.exceptions import SchedulingError
from chatbot_core.scheduling.service import SchedulingService
from chatbot_core.types import ToolSpec


def _parse_starts_at(date_raw: str, time_raw: str) -> datetime:
    return datetime.fromisoformat(f"{date_raw.strip()}T{time_raw.strip()}")


def _require(arguments: dict[str, Any], *names: str) -> list[str] | None:
    missing = [n for n in names if not str(arguments.get(n, "")).strip()]
    return missing or None


def build_scheduling_tools(scheduling: SchedulingService) -> list[Tool]:
    def get_services(_: dict[str, Any]) -> str:
        services = scheduling.list_services()
        if not services:
            return "Este negocio no tiene servicios agendables configurados."
        lines = [
            f"- id: {s.id} | {s.name} | duración: {s.duration_min} min"
            + (f" | {s.description}" if s.description else "")
            for s in services
        ]
        return "Servicios disponibles:\n" + "\n".join(lines)

    def get_available_slots(arguments: dict[str, Any]) -> str:
        if missing := _require(arguments, "service_id"):
            return f"Error: faltan parámetros: {missing}."
        days = arguments.get("days_ahead")
        try:
            slots = scheduling.available_slots(
                str(arguments["service_id"]), int(days) if days is not None else None
            )
        except SchedulingError as exc:
            return str(exc)
        if not slots:
            return "No hay horarios disponibles en el período consultado."
        lines = [
            f"- {_date_label(datetime.fromisoformat(d).date())}: {', '.join(times)}"
            for d, times in slots.items()
        ]
        return "Horarios disponibles (fecha: horas):\n" + "\n".join(lines)

    def book_appointment(arguments: dict[str, Any]) -> str:
        if missing := _require(
            arguments, "service_id", "date", "time", "customer_name", "customer_phone"
        ):
            return f"Error: faltan parámetros: {missing}. Pídele estos datos al usuario."
        try:
            starts_at = _parse_starts_at(str(arguments["date"]), str(arguments["time"]))
        except ValueError:
            return "Error: fecha u hora inválidas. Usa formato date=YYYY-MM-DD, time=HH:MM."
        try:
            appointment = scheduling.book(
                service_id=str(arguments["service_id"]),
                starts_at=starts_at,
                customer_name=str(arguments["customer_name"]),
                customer_phone=str(arguments["customer_phone"]),
            )
        except SchedulingError as exc:
            return str(exc)
        return (
            f"Cita confirmada. Número de cita: {appointment.id}. "
            f"{appointment.service_name} el {appointment.starts_at:%Y-%m-%d} a las "
            f"{appointment.starts_at:%H:%M} ({appointment.duration_min} min) "
            f"a nombre de {appointment.customer_name}."
        )

    def cancel_appointment(arguments: dict[str, Any]) -> str:
        if missing := _require(arguments, "appointment_id", "customer_phone"):
            return f"Error: faltan parámetros: {missing}. Pídele estos datos al usuario."
        try:
            appointment = scheduling.cancel(
                int(arguments["appointment_id"]), str(arguments["customer_phone"])
            )
        except (SchedulingError, ValueError) as exc:
            return str(exc)
        return (
            f"Cita {appointment.id} cancelada: {appointment.service_name} "
            f"del {appointment.starts_at:%Y-%m-%d %H:%M}."
        )

    def get_my_appointments(arguments: dict[str, Any]) -> str:
        if missing := _require(arguments, "customer_phone"):
            return f"Error: faltan parámetros: {missing}."
        appointments = scheduling.find_appointments(str(arguments["customer_phone"]))
        if not appointments:
            return "No hay citas próximas asociadas a ese teléfono."
        lines = [
            f"- cita {a.id}: {a.service_name} el {a.starts_at:%Y-%m-%d} a las "
            f"{a.starts_at:%H:%M} a nombre de {a.customer_name}"
            for a in appointments
        ]
        return "Citas próximas:\n" + "\n".join(lines)

    phone_param = {
        "type": "string",
        "description": "Teléfono del cliente (el usado al reservar)",
    }
    return [
        Tool(
            spec=ToolSpec(
                name="get_services",
                description=(
                    "Lista los IDs de servicios agendables para usar en las herramientas de citas. "
                    "Úsala SOLO durante el flujo de agendamiento (cuando el usuario quiere reservar). "
                    "Para preguntas informativas sobre servicios, precios o descripciones, usa search_kb."
                ),
                parameters={"type": "object", "properties": {}},
            ),
            handler=get_services,
        ),
        Tool(
            spec=ToolSpec(
                name="get_available_slots",
                description=(
                    "Consulta los horarios disponibles para un servicio. Úsala antes de "
                    "proponer o confirmar cualquier horario."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "service_id": {"type": "string", "description": "id del servicio"},
                        "days_ahead": {
                            "type": "integer",
                            "description": "Días hacia adelante a consultar (opcional)",
                        },
                    },
                    "required": ["service_id"],
                },
            ),
            handler=get_available_slots,
        ),
        Tool(
            spec=ToolSpec(
                name="book_appointment",
                description=(
                    "Reserva una cita. REQUISITOS ESTRICTOS antes de llamar: "
                    "(1) el usuario eligió explícitamente servicio, fecha y hora, "
                    "(2) el usuario dio su nombre y teléfono, "
                    "(3) el usuario respondió SÍ a la pregunta de confirmación en un turno anterior. "
                    "Si falta cualquiera de estos tres requisitos, NO llames esta herramienta — "
                    "primero recaba la información que falta. "
                    "Llama esta herramienta UNA SOLA VEZ por reserva."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "service_id": {"type": "string", "description": "id del servicio"},
                        "date": {"type": "string", "description": "Fecha YYYY-MM-DD"},
                        "time": {"type": "string", "description": "Hora HH:MM (24h)"},
                        "customer_name": {"type": "string", "description": "Nombre del cliente"},
                        "customer_phone": phone_param,
                    },
                    "required": ["service_id", "date", "time", "customer_name", "customer_phone"],
                },
            ),
            handler=book_appointment,
        ),
        Tool(
            spec=ToolSpec(
                name="cancel_appointment",
                description="Cancela una cita existente por su número de cita y teléfono.",
                parameters={
                    "type": "object",
                    "properties": {
                        "appointment_id": {"type": "integer", "description": "Número de cita"},
                        "customer_phone": phone_param,
                    },
                    "required": ["appointment_id", "customer_phone"],
                },
            ),
            handler=cancel_appointment,
        ),
        Tool(
            spec=ToolSpec(
                name="get_my_appointments",
                description="Lista las citas próximas de un cliente a partir de su teléfono.",
                parameters={
                    "type": "object",
                    "properties": {"customer_phone": phone_param},
                    "required": ["customer_phone"],
                },
            ),
            handler=get_my_appointments,
        ),
    ]
