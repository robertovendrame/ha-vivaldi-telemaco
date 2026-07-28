"""Preset selectors for Vivaldi Telemaco."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
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
    async_add_entities(
        TelemacoPresetSelect(coordinator, player)
        for player in range(1, coordinator.player_count + 1)
    )


class TelemacoPresetSelect(TelemacoEntity, SelectEntity):
    """Select and immediately play one player preset."""

    _attr_icon = "mdi:playlist-music"

    def __init__(self, coordinator: TelemacoCoordinator, player: int) -> None:
        super().__init__(coordinator)
        self.player = player
        self._attr_unique_id = f"{coordinator.entry.unique_id}_player_{player}_preset"

    @property
    def name(self) -> str:
        return f"{self.coordinator.data.players[self.player].name} preset"

    @property
    def options(self) -> list[str]:
        return [
            f"{preset} · {name}"
            for preset, name in self.coordinator.data.players[self.player].presets.items()
        ]

    @property
    def current_option(self) -> str | None:
        player = self.coordinator.data.players[self.player]
        if player.preset is None or player.preset not in player.presets:
            return None
        return f"{player.preset} · {player.presets[player.preset]}"

    async def async_select_option(self, option: str) -> None:
        presets = self.coordinator.data.players[self.player].presets
        preset_text, separator, _name = option.partition(" · ")
        preset = int(preset_text) if separator and preset_text.isdigit() else None
        if preset is None:
            raise ValueError(f"Unknown Telemaco preset: {option}")
        if preset not in presets:
            raise ValueError(f"Unknown Telemaco preset: {option}")
        await self.coordinator.async_command(
            "player_preset",
            player=self.player,
            preset=preset,
        )
        self.coordinator.data.players[self.player].preset = preset
        self.coordinator.async_set_updated_data(self.coordinator.data)
