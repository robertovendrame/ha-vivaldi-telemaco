"""Equalizer controls for Vivaldi Telemaco."""

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfSoundPressure
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import TelemacoCoordinator
from .entity import TelemacoEntity

BANDS = {"low": "Bassi", "mid": "Medi", "high": "Alti"}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator: TelemacoCoordinator = entry.runtime_data
    if coordinator.mqtt is None:
        return
    async_add_entities(
        [
            TelemacoEqualizer(coordinator, zone, band)
            for zone in range(1, coordinator.zone_count + 1)
            for band in BANDS
        ]
    )


class TelemacoEqualizer(TelemacoEntity, NumberEntity):
    """One -10/+10 dB output EQ band."""

    _attr_native_min_value = -10
    _attr_native_max_value = 10
    _attr_native_step = 1
    _attr_native_unit_of_measurement = UnitOfSoundPressure.DECIBEL
    _attr_icon = "mdi:tune-vertical"

    def __init__(self, coordinator: TelemacoCoordinator, zone: int, band: str) -> None:
        super().__init__(coordinator)
        self.zone = zone
        self.band = band
        self._attr_unique_id = f"{coordinator.entry.unique_id}_zone_{zone}_eq_{band}"

    @property
    def name(self) -> str:
        return f"{self.coordinator.data.zones[self.zone].name} {BANDS[self.band]}"

    @property
    def native_value(self) -> int:
        attribute = {
            "low": "eq_low",
            "mid": "eq_mid",
            "high": "eq_high",
        }[self.band]
        return getattr(self.coordinator.data.zones[self.zone], attribute)

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_command(
            "zone_eq", zone=self.zone, band=self.band, value=round(value)
        )
