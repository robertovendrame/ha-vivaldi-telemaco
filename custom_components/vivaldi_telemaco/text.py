"""Editable Telemaco names."""

from __future__ import annotations

from homeassistant.components.text import TextEntity
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
        [
            TelemacoNameText(coordinator, "device", 0),
            *(
                TelemacoNameText(coordinator, "player", index)
                for index in range(1, coordinator.player_count + 1)
            ),
            *(
                TelemacoNameText(coordinator, "input", index)
                for index in range(1, 7)
            ),
            *(
                TelemacoNameText(coordinator, "zone", index)
                for index in range(1, coordinator.zone_count + 1)
            ),
        ]
    )


class TelemacoNameText(TelemacoEntity, TextEntity):
    """Edit a device, player, input or zone name."""

    _attr_icon = "mdi:rename"
    _attr_native_min = 1
    _attr_native_max = 64

    def __init__(
        self,
        coordinator: TelemacoCoordinator,
        kind: str,
        index: int,
    ) -> None:
        super().__init__(coordinator)
        self.kind = kind
        self.index = index
        self._attr_unique_id = (
            f"{coordinator.entry.unique_id}_{kind}_{index}_configured_name"
        )

    @property
    def name(self) -> str:
        if self.kind == "device":
            return "Nome dispositivo"
        return f"Nome {self.kind} {self.index}"

    @property
    def native_value(self) -> str:
        if self.kind == "device":
            return self.coordinator.data.name
        if self.kind == "player":
            return self.coordinator.data.players[self.index].name
        if self.kind == "input":
            return self.coordinator.data.input_names.get(
                f"aux{self.index}",
                f"Ingresso {self.index}",
            )
        return self.coordinator.data.zones[self.index].name

    async def async_set_value(self, value: str) -> None:
        value = value.strip()
        if not value:
            raise ValueError("The Telemaco name cannot be empty")
        if self.kind == "device":
            await self.coordinator.async_command("rename_device", name=value)
        elif self.kind == "player":
            await self.coordinator.async_command(
                "rename_player",
                player=self.index,
                name=value,
            )
        elif self.kind == "input":
            await self.coordinator.async_command(
                "rename_input",
                input=f"aux{self.index}",
                name=value,
            )
        else:
            await self.coordinator.async_command(
                "rename_zone",
                zone=self.index,
                name=value,
            )
