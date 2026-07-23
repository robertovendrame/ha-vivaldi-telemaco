"""DND switches for Vivaldi Telemaco."""

from typing import Any

from homeassistant.components.switch import SwitchEntity
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
    if coordinator.api is None:
        return
    async_add_entities(
        [TelemacoDndSwitch(coordinator, zone) for zone in range(1, coordinator.zone_count + 1)]
    )


class TelemacoDndSwitch(TelemacoEntity, SwitchEntity):
    """Doorbell do-not-disturb for an output."""

    _attr_icon = "mdi:bell-off"

    def __init__(self, coordinator: TelemacoCoordinator, zone: int) -> None:
        super().__init__(coordinator)
        self.zone = zone
        self._attr_unique_id = f"{coordinator.entry.unique_id}_zone_{zone}_dnd"

    @property
    def name(self) -> str:
        return f"{self.coordinator.data.zones[self.zone].name} non disturbare"

    @property
    def is_on(self) -> bool:
        return self.coordinator.data.zones[self.zone].dnd

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_command("zone_dnd", zone=self.zone, dnd=True)
        self.coordinator.data.zones[self.zone].dnd = True
        self.coordinator.async_set_updated_data(self.coordinator.data)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_command("zone_dnd", zone=self.zone, dnd=False)
        self.coordinator.data.zones[self.zone].dnd = False
        self.coordinator.async_set_updated_data(self.coordinator.data)
