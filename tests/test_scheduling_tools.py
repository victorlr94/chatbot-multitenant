from datetime import datetime

import pytest
from sqlalchemy.orm import Session, sessionmaker

from chatbot_core.agent.tools.base import ToolRegistry
from chatbot_core.agent.tools.scheduling import build_scheduling_tools
from chatbot_core.config import TenantConfig
from chatbot_core.scheduling.service import SchedulingService


@pytest.fixture
def registry(
    session_factory: sessionmaker[Session], tenant: TenantConfig, fixed_now: datetime
) -> ToolRegistry:
    service = SchedulingService(session_factory, tenant, now_fn=lambda: fixed_now)
    return ToolRegistry(build_scheduling_tools(service))


def test_get_services_lists_ids(registry: ToolRegistry) -> None:
    output = registry.execute("get_services", {})
    assert "corte" in output and "tinte" in output


def test_slots_and_booking_flow(registry: ToolRegistry) -> None:
    slots = registry.execute("get_available_slots", {"service_id": "corte", "days_ahead": 0})
    assert "2026-07-06" in slots and "09:00" in slots

    confirmation = registry.execute(
        "book_appointment",
        {
            "service_id": "corte",
            "date": "2026-07-06",
            "time": "09:00",
            "customer_name": "Ana Pérez",
            "customer_phone": "+53 5555 0001",
        },
    )
    assert "Cita confirmada" in confirmation

    # El slot reservado desaparece y el doble booking devuelve mensaje, no excepción.
    slots_after = registry.execute("get_available_slots", {"service_id": "corte", "days_ahead": 0})
    assert "09:00" not in slots_after
    retry = registry.execute(
        "book_appointment",
        {
            "service_id": "tinte",
            "date": "2026-07-06",
            "time": "09:00",
            "customer_name": "Luis",
            "customer_phone": "+53 5555 0002",
        },
    )
    assert "ocupado" in retry


def test_book_requires_all_parameters(registry: ToolRegistry) -> None:
    output = registry.execute("book_appointment", {"service_id": "corte"})
    assert "faltan parámetros" in output


def test_lookup_and_cancel(registry: ToolRegistry) -> None:
    registry.execute(
        "book_appointment",
        {
            "service_id": "corte",
            "date": "2026-07-06",
            "time": "10:00",
            "customer_name": "Ana",
            "customer_phone": "+53 5555 0001",
        },
    )
    mine = registry.execute("get_my_appointments", {"customer_phone": "+53 5555 0001"})
    assert "cita 1" in mine

    cancelled = registry.execute(
        "cancel_appointment", {"appointment_id": 1, "customer_phone": "+53 5555 0001"}
    )
    assert "cancelada" in cancelled
    assert "No hay citas" in registry.execute(
        "get_my_appointments", {"customer_phone": "+53 5555 0001"}
    )


def test_invalid_date_reports_error(registry: ToolRegistry) -> None:
    output = registry.execute(
        "book_appointment",
        {
            "service_id": "corte",
            "date": "6 de julio",
            "time": "10:00",
            "customer_name": "Ana",
            "customer_phone": "+53 5555 0001",
        },
    )
    assert "fecha u hora inválidas" in output
