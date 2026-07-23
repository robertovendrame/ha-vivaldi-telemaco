"""Base entities for Vivaldi Telemaco."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TelemacoCoordinator


class TelemacoEntity(CoordinatorEntity[TelemacoCoordinator]):
    """Base coordinator entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: TelemacoCoordinator) -> None:
        super().__init__(coordinator)
        state = coordinator.data
        serial = state.serial if state else coordinator.entry.unique_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(serial))},
            manufacturer="Vivaldi",
            model=state.model if state else "TELEMACO",
            name=state.name if state else coordinator.entry.title,
            sw_version=state.firmware if state else None,
            configuration_url=(
                f"http://{coordinator.entry.data['host']}"
                if coordinator.entry.data.get("host")
                else None
            ),
        )
