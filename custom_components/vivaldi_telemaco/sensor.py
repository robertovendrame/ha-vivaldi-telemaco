"""Sensors for Vivaldi Telemaco."""

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import SIGNAL_STRENGTH_DECIBELS_MILLIWATT, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .c4io import C4IOClient, C4IOEntity
from .coordinator import TelemacoCoordinator
from .entity import TelemacoEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator: TelemacoCoordinator = entry.runtime_data
    async_add_entities(
        [
            TelemacoFirmwareSensor(coordinator),
            *(C4IOFirmwareSensor(client) for client in coordinator.c4io_manager.clients),
            *(C4IORssiSensor(client) for client in coordinator.c4io_manager.clients),
        ]
    )


class C4IOFirmwareSensor(C4IOEntity, SensorEntity):
    """Firmware reported by one C4IO."""

    _attr_name = "Firmware"
    _attr_icon = "mdi:chip"
    _attr_entity_registry_enabled_default = False
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, client: C4IOClient) -> None:
        super().__init__(client)
        self._attr_unique_id = f"c4io_{client.spec.host.replace('.', '_')}_firmware"

    @property
    def native_value(self) -> str | None:
        return self.client.state.firmware


class C4IORssiSensor(C4IOEntity, SensorEntity):
    """Wi-Fi RSSI reported by one C4IO."""

    _attr_name = "Segnale Wi-Fi"
    _attr_device_class = SensorDeviceClass.SIGNAL_STRENGTH
    _attr_native_unit_of_measurement = SIGNAL_STRENGTH_DECIBELS_MILLIWATT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_registry_enabled_default = False
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, client: C4IOClient) -> None:
        super().__init__(client)
        self._attr_unique_id = f"c4io_{client.spec.host.replace('.', '_')}_rssi"

    @property
    def native_value(self) -> int | None:
        return self.client.state.rssi


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
