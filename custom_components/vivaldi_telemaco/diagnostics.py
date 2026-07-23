"""Diagnostics for Vivaldi Telemaco."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import TelemacoConfigEntry
from .const import CONF_API_TOKEN

TO_REDACT = {CONF_API_TOKEN, "token", "password", "authorization", "mac", "mac_address"}


def _json_safe(value: Any) -> Any:
    if isinstance(value, set):
        return sorted(value)
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: TelemacoConfigEntry
) -> dict[str, Any]:
    """Return safe diagnostic data including the raw protocol payload."""
    coordinator = entry.runtime_data
    state = coordinator.data
    return async_redact_data(
        {
            "entry": dict(entry.data),
            "options": dict(entry.options),
            "last_update_success": coordinator.last_update_success,
            "state": _json_safe(asdict(state)) if state else None,
        },
        TO_REDACT,
    )
