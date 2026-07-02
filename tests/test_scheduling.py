from datetime import datetime

import pytest
from sqlalchemy.orm import Session, sessionmaker

from chatbot_core.config import TenantConfig
from chatbot_core.scheduling.exceptions import SlotUnavailableError, UnknownServiceError
from chatbot_core.scheduling.models import Appointment
from chatbot_core.scheduling.service import SchedulingService


@pytest.fixture
def scheduling(
    session_factory: sessionmaker[Session], tenant: TenantConfig, fixed_now: datetime
) -> SchedulingService:
    return SchedulingService(session_factory, tenant, now_fn=lambda: fixed_now)


def test_available_slots_respect_hours_and_duration(scheduling: SchedulingService) -> None:
    slots = scheduling.available_slots("corte", days_ahead=0)
    # Lunes 09:00-12:00, paso 30 min, servicio de 30 min → 6 slots.
    assert slots == {"2026-07-06": ["09:00", "09:30", "10:00", "10:30", "11:00", "11:30"]}

    slots_60 = scheduling.available_slots("tinte", days_ahead=0)
    # 60 min de duración: el último inicio posible es 11:00.
    assert slots_60["2026-07-06"][-1] == "11:00"


def test_book_and_slot_disappears(scheduling: SchedulingService) -> None:
    appointment = scheduling.book(
        "corte", datetime(2026, 7, 6, 10, 0), "Ana Pérez", "+53 5555 0001"
    )
    assert appointment.id is not None
    assert appointment.service_name == "Corte de pelo"

    slots = scheduling.available_slots("corte", days_ahead=0)
    assert "10:00" not in slots["2026-07-06"]


def test_double_booking_rejected(scheduling: SchedulingService) -> None:
    starts = datetime(2026, 7, 6, 10, 0)
    scheduling.book("corte", starts, "Ana", "+53 5555 0001")
    with pytest.raises(SlotUnavailableError):
        scheduling.book("tinte", starts, "Luis", "+53 5555 0002")


def test_booking_in_past_rejected(scheduling: SchedulingService) -> None:
    with pytest.raises(SlotUnavailableError):
        scheduling.book("corte", datetime(2026, 7, 6, 7, 0), "Ana", "+53 5555 0001")


def test_booking_outside_hours_rejected(scheduling: SchedulingService) -> None:
    with pytest.raises(SlotUnavailableError):
        scheduling.book("corte", datetime(2026, 7, 6, 13, 0), "Ana", "+53 5555 0001")
    # Domingo: sin horario configurado.
    with pytest.raises(SlotUnavailableError):
        scheduling.book("corte", datetime(2026, 7, 12, 10, 0), "Ana", "+53 5555 0001")


def test_booking_off_grid_time_rejected(scheduling: SchedulingService) -> None:
    with pytest.raises(SlotUnavailableError):
        scheduling.book("corte", datetime(2026, 7, 6, 10, 15), "Ana", "+53 5555 0001")


def test_booking_beyond_horizon_rejected(scheduling: SchedulingService) -> None:
    with pytest.raises(SlotUnavailableError):
        scheduling.book("corte", datetime(2026, 7, 20, 10, 0), "Ana", "+53 5555 0001")


def test_unknown_service_rejected(scheduling: SchedulingService) -> None:
    with pytest.raises(UnknownServiceError):
        scheduling.book("masaje", datetime(2026, 7, 6, 10, 0), "Ana", "+53 5555 0001")


def test_cancel_frees_slot_and_requires_matching_phone(
    scheduling: SchedulingService,
) -> None:
    starts = datetime(2026, 7, 6, 10, 0)
    appointment = scheduling.book("corte", starts, "Ana", "+53 5555 0001")

    with pytest.raises(SlotUnavailableError):
        scheduling.cancel(appointment.id, "+53 9999 9999")

    cancelled = scheduling.cancel(appointment.id, "+53 5555 0001")
    assert cancelled.status == "cancelled"

    # El slot vuelve a estar disponible y se puede volver a reservar.
    slots = scheduling.available_slots("corte", days_ahead=0)
    assert "10:00" in slots["2026-07-06"]
    scheduling.book("corte", starts, "Luis", "+53 5555 0002")


def test_find_appointments_by_phone(scheduling: SchedulingService) -> None:
    scheduling.book("corte", datetime(2026, 7, 6, 10, 0), "Ana", "+53 5555 0001")
    scheduling.book("tinte", datetime(2026, 7, 7, 9, 0), "Ana", "+53 5555 0001")

    found = scheduling.find_appointments("+53 5555 0001")
    assert len(found) == 2
    assert all(isinstance(a, Appointment) for a in found)
    assert scheduling.find_appointments("+53 0000 0000") == []
