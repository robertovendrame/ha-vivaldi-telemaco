"""Physical button events for Vivaldi C4IO."""

from __future__ import annotations

from homeassistant.components.event import EventEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .c4io import C4IO_EVENT_TYPES, C4IOClient, C4IOEntity
from .coordinator import TelemacoCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator: TelemacoCoordinator = entry.runtime_data
    manager = coordinator.c4io_manager
    async_add_entities(
        C4IOInputEvent(client, input_number)
        for client in manager.clients
        for input_number in range(1, 5)
    )


class C4IOInputEvent(C4IOEntity, EventEntity):
    """Short and long presses from one physical C4IO input."""

    _attr_event_types = list(C4IO_EVENT_TYPES)
    _attr_icon = "mdi:gesture-tap-button"

    def __init__(self, client: C4IOClient, input_number: int) -> None:
        super().__init__(client)
        self.input_number = input_number
        self._attr_name = f"Ingresso {input_number}"
        self._attr_unique_id = (
            f"c4io_{client.spec.host.replace('.', '_')}_input_{input_number}"
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(self.client.add_event_listener(self._handle_event))

    @callback
    def _handle_event(self, input_number: int, event_type: str) -> None:
        if input_number != self.input_number:
            return
        self._trigger_event(
            event_type,
            {
                "input": input_number,
                "device_name": self.client.spec.name,
                "host": self.client.spec.host,
            },
        )
        self.async_write_ha_state()
