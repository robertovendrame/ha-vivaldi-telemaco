"""Media player entities for Vivaldi Telemaco."""

from __future__ import annotations

from homeassistant.components.media_player import MediaPlayerEntity, MediaPlayerEntityFeature
from homeassistant.components.media_player.const import MediaPlayerState
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import TelemacoCoordinator
from .entity import TelemacoEntity

PLAYER_FEATURES = (
    MediaPlayerEntityFeature.PLAY
    | MediaPlayerEntityFeature.PAUSE
    | MediaPlayerEntityFeature.STOP
    | MediaPlayerEntityFeature.NEXT_TRACK
    | MediaPlayerEntityFeature.PREVIOUS_TRACK
    | MediaPlayerEntityFeature.SHUFFLE_SET
    | MediaPlayerEntityFeature.REPEAT_SET
)
ZONE_FEATURES = (
    MediaPlayerEntityFeature.VOLUME_SET
    | MediaPlayerEntityFeature.VOLUME_MUTE
    | MediaPlayerEntityFeature.SELECT_SOURCE
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator: TelemacoCoordinator = entry.runtime_data
    async_add_entities(
        [
            *(TelemacoZone(coordinator, index) for index in range(1, coordinator.zone_count + 1)),
            *(
                TelemacoPlayer(coordinator, index)
                for index in range(1, coordinator.player_count + 1)
            ),
        ]
    )


class TelemacoZone(TelemacoEntity, MediaPlayerEntity):
    """One amplified Telemaco output zone."""

    _attr_supported_features = ZONE_FEATURES

    def __init__(self, coordinator: TelemacoCoordinator, index: int) -> None:
        super().__init__(coordinator)
        self.index = index
        self._attr_unique_id = f"{coordinator.entry.unique_id}_zone_{index}"
        self._attr_translation_key = "zone"

    @property
    def name(self) -> str:
        return self.coordinator.data.zones[self.index].name

    @property
    def state(self) -> MediaPlayerState:
        return (
            MediaPlayerState.ON
            if self.coordinator.data.zones[self.index].active
            else MediaPlayerState.OFF
        )

    @property
    def available(self) -> bool:
        return super().available and self.coordinator.data.zones[self.index].available

    @property
    def volume_level(self) -> float:
        return self.coordinator.data.zones[self.index].volume

    @property
    def is_volume_muted(self) -> bool:
        return self.coordinator.data.zones[self.index].muted

    @property
    def source(self) -> str | None:
        return self.coordinator.data.zones[self.index].source

    @property
    def source_list(self) -> list[str]:
        return [f"Player {index}" for index in range(1, self.coordinator.player_count + 1)]

    async def async_set_volume_level(self, volume: float) -> None:
        await self.coordinator.async_command(
            "zone_volume", zone=self.index, volume=round(volume * 100)
        )

    async def async_mute_volume(self, mute: bool) -> None:
        await self.coordinator.async_command("zone_mute", zone=self.index, mute=mute)

    async def async_select_source(self, source: str) -> None:
        await self.coordinator.async_command("zone_source", zone=self.index, source=source)


class TelemacoPlayer(TelemacoEntity, MediaPlayerEntity):
    """One independent Telemaco multimedia player."""

    _attr_supported_features = PLAYER_FEATURES

    def __init__(self, coordinator: TelemacoCoordinator, index: int) -> None:
        super().__init__(coordinator)
        self.index = index
        self._attr_unique_id = f"{coordinator.entry.unique_id}_player_{index}"
        self._attr_translation_key = "player"

    @property
    def name(self) -> str:
        return self.coordinator.data.players[self.index].name

    @property
    def state(self) -> MediaPlayerState:
        value = self.coordinator.data.players[self.index].state
        return {
            "playing": MediaPlayerState.PLAYING,
            "play": MediaPlayerState.PLAYING,
            "paused": MediaPlayerState.PAUSED,
            "pause": MediaPlayerState.PAUSED,
            "off": MediaPlayerState.OFF,
        }.get(value, MediaPlayerState.IDLE)

    @property
    def media_title(self) -> str | None:
        return self.coordinator.data.players[self.index].title

    @property
    def media_artist(self) -> str | None:
        return self.coordinator.data.players[self.index].artist

    @property
    def media_album_name(self) -> str | None:
        return self.coordinator.data.players[self.index].album

    @property
    def media_image_url(self) -> str | None:
        return self.coordinator.data.players[self.index].image_url

    @property
    def volume_level(self) -> float:
        return self.coordinator.data.players[self.index].volume

    @property
    def is_volume_muted(self) -> bool:
        return self.coordinator.data.players[self.index].muted

    @property
    def source(self) -> str | None:
        return self.coordinator.data.players[self.index].source

    @property
    def shuffle(self) -> bool:
        return self.coordinator.data.players[self.index].shuffle

    @property
    def repeat(self) -> str:
        return "all" if self.coordinator.data.players[self.index].repeat else "off"

    async def async_media_play(self) -> None:
        await self.coordinator.async_command("player_play", player=self.index)

    async def async_media_pause(self) -> None:
        await self.coordinator.async_command("player_pause", player=self.index)

    async def async_media_stop(self) -> None:
        await self.coordinator.async_command("player_stop", player=self.index)

    async def async_media_next_track(self) -> None:
        await self.coordinator.async_command("player_next", player=self.index)

    async def async_media_previous_track(self) -> None:
        await self.coordinator.async_command("player_previous", player=self.index)

    async def async_set_shuffle(self, shuffle: bool) -> None:
        await self.coordinator.async_command("player_shuffle", player=self.index, shuffle=shuffle)

    async def async_set_repeat(self, repeat: str) -> None:
        await self.coordinator.async_command(
            "player_repeat", player=self.index, repeat=repeat != "off"
        )
