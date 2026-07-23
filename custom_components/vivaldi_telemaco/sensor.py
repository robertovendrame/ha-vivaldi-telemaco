"""Sensors for Vivaldi Telemaco."""

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import TelemacoCoordinator
from .entity import TelemacoEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator: TelemacoCoordinator = entry.runtime_data
    async_add_entities([TelemacoFirmwareSensor(coordinator)])


class TelemacoFirmwareSensor(TelemacoEntity, SensorEntity):
    """Firmware version sensor."""

    _attr_translation_key = "firmware"
    _attr_icon = "mdi:chip"

    def __init__(self, coordinator: TelemacoCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.unique_id}_firmware"

    @property
    def native_value(self) -> str | None:
        return self.coordinator.data.firmware
