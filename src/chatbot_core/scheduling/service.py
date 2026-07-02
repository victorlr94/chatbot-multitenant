"""Motor de citas: disponibilidad desde reglas del tenant y reserva con anti doble-booking.

Los datetimes son naive en la zona horaria del tenant (MVP de un solo recurso y una
sola zona). La reserva hace chequeo dentro de la transacción y el índice único parcial
de `Appointment` actúa como backstop ante carreras.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from chatbot_core.config import ServiceConfig, TenantConfig
from chatbot_core.scheduling.calendar_sync import CalendarSync, NoopCalendarSync
from chatbot_core.scheduling.exceptions import SlotUnavailableError, UnknownServiceError
from chatbot_core.scheduling.models import (
    STATUS_CANCELLED,
    STATUS_CONFIRMED,
    Appointment,
)


def _parse_range(value: str) -> tuple[time, time]:
    start_raw, end_raw = value.split("-", 1)
    return time.fromisoformat(start_raw.strip()), time.fromisoformat(end_raw.strip())


class SchedulingService:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        tenant: TenantConfig,
        calendar_sync: CalendarSync | None = None,
        now_fn: Callable[[], datetime] | None = None,
    ) -> None:
        self._sessions = session_factory
        self._tenant = tenant
        self._config = tenant.scheduling
        self._calendar = calendar_sync or NoopCalendarSync()
        self._now_fn = now_fn or self._default_now

    def _default_now(self) -> datetime:
        return datetime.now(ZoneInfo(self._config.timezone)).replace(tzinfo=None)

    # ------------------------------------------------------------------ consultas

    def list_services(self) -> list[ServiceConfig]:
        return list(self._config.services)

    def get_service(self, service_id: str) -> ServiceConfig:
        for service in self._config.services:
            if service.id == service_id:
                return service
        raise UnknownServiceError(
            f"Servicio desconocido: '{service_id}'. "
            f"Disponibles: {[s.id for s in self._config.services]}"
        )

    def available_slots(
        self, service_id: str, days_ahead: int | None = None
    ) -> dict[str, list[str]]:
        """Slots libres por fecha ISO → lista de horas 'HH:MM', respetando el horizonte."""
        service = self.get_service(service_id)
        now = self._now_fn()
        horizon = min(
            days_ahead if days_ahead is not None else self._config.booking_horizon_days,
            self._config.booking_horizon_days,
        )

        with self._sessions() as session:
            taken = self._booked_starts(session, now, now + timedelta(days=horizon + 1))

        slots: dict[str, list[str]] = {}
        for day_offset in range(horizon + 1):
            day = (now + timedelta(days=day_offset)).date()
            ranges = self._config.hours.get(day.weekday(), [])
            day_slots: list[str] = []
            for range_raw in ranges:
                range_start, range_end = _parse_range(range_raw)
                cursor = datetime.combine(day, range_start)
                range_end_dt = datetime.combine(day, range_end)
                step = timedelta(minutes=self._config.slot_step_min)
                duration = timedelta(minutes=service.duration_min)
                while cursor + duration <= range_end_dt:
                    if cursor > now and cursor not in taken:
                        day_slots.append(cursor.strftime("%H:%M"))
                    cursor += step
            if day_slots:
                slots[day.isoformat()] = day_slots
        return slots

    def find_appointments(self, customer_phone: str) -> list[Appointment]:
        with self._sessions() as session:
            rows = session.scalars(
                select(Appointment).where(
                    Appointment.tenant_id == self._tenant.id,
                    Appointment.customer_phone == customer_phone,
                    Appointment.status == STATUS_CONFIRMED,
                    Appointment.starts_at >= self._now_fn(),
                )
            )
            return list(rows)

    # ------------------------------------------------------------------ comandos

    def book(
        self,
        service_id: str,
        starts_at: datetime,
        customer_name: str,
        customer_phone: str,
    ) -> Appointment:
        service = self.get_service(service_id)
        self._validate_slot(service, starts_at)

        appointment = Appointment(
            tenant_id=self._tenant.id,
            service_id=service.id,
            service_name=service.name,
            starts_at=starts_at,
            duration_min=service.duration_min,
            customer_name=customer_name.strip(),
            customer_phone=customer_phone.strip(),
            status=STATUS_CONFIRMED,
        )
        with self._sessions() as session:
            existing = session.scalar(
                select(Appointment.id).where(
                    Appointment.tenant_id == self._tenant.id,
                    Appointment.starts_at == starts_at,
                    Appointment.status == STATUS_CONFIRMED,
                )
            )
            if existing is not None:
                raise SlotUnavailableError(
                    f"El horario {starts_at:%Y-%m-%d %H:%M} ya está ocupado."
                )
            session.add(appointment)
            try:
                session.commit()
            except IntegrityError as exc:
                session.rollback()
                raise SlotUnavailableError(
                    f"El horario {starts_at:%Y-%m-%d %H:%M} ya está ocupado."
                ) from exc
            session.refresh(appointment)
            session.expunge(appointment)

        self._calendar.appointment_created(appointment)
        return appointment

    def cancel(self, appointment_id: int, customer_phone: str) -> Appointment:
        """Cancela una cita; exige el teléfono usado al reservar como verificación mínima."""
        with self._sessions() as session:
            appointment = session.get(Appointment, appointment_id)
            if (
                appointment is None
                or appointment.tenant_id != self._tenant.id
                or appointment.customer_phone != customer_phone.strip()
                or appointment.status != STATUS_CONFIRMED
            ):
                raise SlotUnavailableError(
                    "No se encontró una cita activa con ese número y teléfono."
                )
            appointment.status = STATUS_CANCELLED
            session.commit()
            session.refresh(appointment)
            session.expunge(appointment)

        self._calendar.appointment_cancelled(appointment)
        return appointment

    # ------------------------------------------------------------------ helpers

    def _booked_starts(self, session: Session, start: datetime, end: datetime) -> set[datetime]:
        rows = session.scalars(
            select(Appointment.starts_at).where(
                Appointment.tenant_id == self._tenant.id,
                Appointment.status == STATUS_CONFIRMED,
                Appointment.starts_at >= start,
                Appointment.starts_at < end,
            )
        )
        return set(rows)

    def _validate_slot(self, service: ServiceConfig, starts_at: datetime) -> None:
        now = self._now_fn()
        if starts_at <= now:
            raise SlotUnavailableError("No se pueden reservar horarios en el pasado.")
        if starts_at > now + timedelta(days=self._config.booking_horizon_days):
            raise SlotUnavailableError(
                f"Solo se puede reservar hasta {self._config.booking_horizon_days} días adelante."
            )
        duration = timedelta(minutes=service.duration_min)
        for range_raw in self._config.hours.get(starts_at.weekday(), []):
            range_start, range_end = _parse_range(range_raw)
            range_start_dt = datetime.combine(starts_at.date(), range_start)
            range_end_dt = datetime.combine(starts_at.date(), range_end)
            offset_min = (starts_at - range_start_dt).total_seconds() / 60
            if (
                range_start_dt <= starts_at
                and starts_at + duration <= range_end_dt
                and offset_min % self._config.slot_step_min == 0
            ):
                return
        raise SlotUnavailableError(
            f"El horario {starts_at:%Y-%m-%d %H:%M} está fuera del horario de atención."
        )
