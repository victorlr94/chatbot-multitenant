"""Modelos de persistencia del agendamiento.

Las citas viven en la DB propia (fuente de verdad); los servicios y horarios vienen
de la configuración del tenant (YAML). MVP asume un recurso por tenant: dos citas
confirmadas no pueden compartir `starts_at` (índice único parcial como backstop del
chequeo transaccional).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, String, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

STATUS_CONFIRMED = "confirmed"
STATUS_CANCELLED = "cancelled"


class Base(DeclarativeBase):
    pass


class Appointment(Base):
    __tablename__ = "appointments"
    __table_args__ = (
        Index(
            "uq_active_slot",
            "tenant_id",
            "starts_at",
            unique=True,
            sqlite_where=text("status = 'confirmed'"),
            postgresql_where=text("status = 'confirmed'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    service_id: Mapped[str] = mapped_column(String(64))
    service_name: Mapped[str] = mapped_column(String(200))
    starts_at: Mapped[datetime] = mapped_column(DateTime)
    duration_min: Mapped[int]
    customer_name: Mapped[str] = mapped_column(String(200))
    customer_phone: Mapped[str] = mapped_column(String(50), index=True)
    status: Mapped[str] = mapped_column(String(20), default=STATUS_CONFIRMED)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
