"""Sincronización opcional con calendarios externos (Google Calendar, etc.).

La DB propia es la fuente de verdad; la sincronización es best-effort y no
bloquea la reserva. La implementación de Google Calendar es una fase futura:
mientras tanto, NoopCalendarSync mantiene el contrato.
"""

from __future__ import annotations

from typing import Protocol

from chatbot_core.scheduling.models import Appointment


class CalendarSync(Protocol):
    def appointment_created(self, appointment: Appointment) -> None: ...

    def appointment_cancelled(self, appointment: Appointment) -> None: ...


class NoopCalendarSync:
    def appointment_created(self, appointment: Appointment) -> None:
        return None

    def appointment_cancelled(self, appointment: Appointment) -> None:
        return None
