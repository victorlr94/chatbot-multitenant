"""Excepciones de dominio del agendamiento."""

from __future__ import annotations


class SchedulingError(Exception):
    """Error base del motor de citas."""


class UnknownServiceError(SchedulingError):
    """El servicio solicitado no existe en la configuración del tenant."""


class SlotUnavailableError(SchedulingError):
    """El horario solicitado no está disponible (ocupado, pasado o fuera de horario)."""
