"""Coordinator for Vivaldi Telemaco."""

from __future__ import annotations

import logging
import re
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import TelemacoApi
from .const import (
    CONF_PLAYER_COUNT,
    CONF_SCAN_INTERVAL,
    CONF_TRANSPORT,
    CONF_ZONE_COUNT,
    DEFAULT_PLAYER_COUNT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_ZONE_COUNT,
    DOMAIN,
    SOURCE_NAMES,
    TRANSPORT_API,
    TRANSPORT_HYBRID,
)
from .exceptions import TelemacoError
from .models import TelemacoState
from .mqtt import TelemacoMqtt
from .protocol import normalize_state

_LOGGER = logging.getLogger(__name__)


class TelemacoCoordinator(DataUpdateCoordinator[TelemacoState]):
    """Combine REST polling and MQTT scalar push topics."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        api: TelemacoApi | None,
        mqtt_client: TelemacoMqtt | None,
    ) -> None:
        self.entry = entry
        self.api = api
        self.mqtt = mqtt_client
        self.zone_count = entry.options.get(
            CONF_ZONE_COUNT, entry.data.get(CONF_ZONE_COUNT, DEFAULT_ZONE_COUNT)
        )
        self.player_count = entry.options.get(
            CONF_PLAYER_COUNT, entry.data.get(CONF_PLAYER_COUNT, DEFAULT_PLAYER_COUNT)
        )
        transport = entry.data[CONF_TRANSPORT]
        interval = (
            timedelta(seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))
            if transport in (TRANSPORT_API, TRANSPORT_HYBRID)
            else None
        )
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=interval,
            always_update=False,
        )

    def _normalize(self, payload: dict[str, Any]) -> TelemacoState:
        return normalize_state(
            payload,
            fallback_id=self.entry.unique_id or self.entry.data["host"],
            zone_count=self.zone_count,
            player_count=self.player_count,
        )

    async def _async_update_data(self) -> TelemacoState:
        if self.api is None:
            if self.data is not None:
                return self.data
            raise UpdateFailed("Waiting for the first MQTT state payload")
        try:
            payload = await self.api.async_get_status()
            refreshed = self._normalize(dict(payload))
            if self.mqtt and self.data:
                for index, zone in refreshed.zones.items():
                    previous = self.data.zones.get(index)
                    if previous:
                        zone.volume = previous.volume
                        zone.muted = previous.muted
                        zone.eq_low = previous.eq_low
                        zone.eq_mid = previous.eq_mid
                        zone.eq_high = previous.eq_high
                        zone.dnd = previous.dnd
                refreshed.signals.update(self.data.signals)
                for index, player in refreshed.players.items():
                    previous = self.data.players.get(index)
                    if previous and player.preset is None:
                        player.preset = previous.preset
            return refreshed
        except TelemacoError as err:
            raise UpdateFailed(str(err)) from err

    @callback
    def async_process_mqtt(self, topic: str, payload: str) -> None:
        """Apply one MQTT API 1.1 scalar state topic."""
        state = self.data or self._normalize({})
        value = payload.strip()

        if topic == "status/system/link_mode_id":
            state.link_mode_id = _as_int(value, 1)
            state.paired = state.link_mode_id == 2
        elif topic == "status/system/link_mode":
            state.link_mode = value
        elif topic == "status/system/update_available":
            state.update_available = _as_bool(value)
        elif match := re.fullmatch(r"status/inputs/player(\d+)/(volume|mute|name)", topic):
            player = state.players.get(int(match[1]))
            if player:
                if match[2] == "volume":
                    player.volume = _as_int(value) / 100
                elif match[2] == "mute":
                    player.muted = _as_bool(value)
                else:
                    player.name = value
        elif match := re.fullmatch(r"status/metadata/player(\d+)/(.+)", topic):
            self._apply_player_metadata(state, int(match[1]), match[2], value)
        elif match := re.fullmatch(r"status/signals/ch(\d+)", topic):
            state.signals[int(match[1])] = _as_bool(value)
        elif match := re.fullmatch(
            r"status/outputs/(mono|stereo)/ch(\d+)/(mute|volume|equ1|equ2|equ3|name)",
            topic,
        ):
            self._apply_output(state, int(match[2]), match[3], value)
        elif match := re.fullmatch(r"status/zones/(?:mono|stereo)/player(\d+)/output(\d+)", topic):
            player_id, output_id = int(match[1]), int(match[2])
            player = state.players.get(player_id)
            zone = state.zones.get(output_id)
            if player and zone:
                if _as_bool(value):
                    player.routed_outputs.add(output_id)
                    zone.player = player_id
                    zone.active = True
                    zone.source = f"Player {player_id}"
                else:
                    player.routed_outputs.discard(output_id)
                    if zone.player == player_id:
                        zone.player = None
                        zone.active = False
                        zone.source = None
        else:
            _LOGGER.debug("Unhandled Telemaco MQTT topic: %s", topic)
            return
        self.async_set_updated_data(state)

    def _apply_player_metadata(
        self, state: TelemacoState, player_id: int, key: str, value: str
    ) -> None:
        player = state.players.get(player_id)
        if not player:
            return
        if key in {"title", "album", "artist", "image_url", "source_name"}:
            attribute = "source" if key == "source_name" else key
            setattr(player, attribute, value or None)
        elif key == "source_id":
            player.source = SOURCE_NAMES.get(_as_int(value), value)
        elif key == "stop" and _as_bool(value):
            player.state = "idle"
        elif key == "play_pause":
            player.state = "playing" if _as_bool(value) else "paused"
        elif key == "shuffle":
            player.shuffle = _as_bool(value)
        elif key == "repeat_all":
            player.repeat = _as_bool(value)
        elif key == "active_preset":
            player.preset = _as_int(value)

    def _apply_output(self, state: TelemacoState, channel: int, key: str, value: str) -> None:
        zone = state.zones.get(channel)
        if not zone:
            return
        if key == "mute":
            zone.muted = _as_bool(value)
        elif key == "volume":
            zone.volume = _as_int(value) / 100
        elif key == "name":
            zone.name = value
        else:
            attribute = {
                "equ1": "eq_low",
                "equ2": "eq_mid",
                "equ3": "eq_high",
            }[key]
            setattr(zone, attribute, _as_int(value))

    async def async_command(self, command: str, **payload: Any) -> None:
        """Send via MQTT when available, otherwise REST."""
        if self.mqtt:
            await self._async_mqtt_command(command, payload)
            return
        if self.api:
            await self.api.async_send_command(command, payload)
            await self.async_request_refresh()
            return
        raise UpdateFailed("No command transport is available")

    async def _async_mqtt_command(self, command: str, data: dict[str, Any]) -> None:
        player = data.get("player")
        zone = data.get("zone")
        mappings = {
            "player_play": (f"inputs/player{player}/play_pause", 1),
            "player_pause": (f"inputs/player{player}/play_pause", 0),
            "player_stop": (f"inputs/player{player}/stop", 1),
            "player_next": (f"inputs/player{player}/next", 1),
            "player_previous": (f"inputs/player{player}/previous", 1),
            "player_shuffle": (
                f"inputs/player{player}/shuffle",
                int(data["shuffle"]),
            ),
            "player_repeat": (
                f"inputs/player{player}/repeat_all",
                int(data["repeat"]),
            ),
            "player_preset": (
                f"inputs/player{player}/play_preset",
                data["preset"],
            ),
            "zone_volume": (f"outputs/mono/ch{zone}/volume", data["volume"]),
            "zone_mute": (f"outputs/mono/ch{zone}/mute", int(data["mute"])),
            "doorbell": ("doorbell/play", data.get("sound", 0)),
        }
        if command == "zone_source":
            selected = int(str(data["source"]).split()[-1])
            for candidate in range(1, self.player_count + 1):
                await self.mqtt.async_publish_topic(
                    f"zones/mono/player{candidate}/output{zone}",
                    int(candidate == selected),
                )
            return
        if command == "zone_eq":
            band = {"low": "equ1", "mid": "equ2", "high": "equ3"}[data["band"]]
            await self.mqtt.async_publish_topic(f"outputs/mono/ch{zone}/{band}", data["value"])
            return
        if command not in mappings:
            raise UpdateFailed(f"Command {command} is not supported by MQTT API 1.1")
        topic, value = mappings[command]
        await self.mqtt.async_publish_topic(topic, value)


def _as_bool(value: str) -> bool:
    return value.lower() in {"1", "true", "on", "yes"}


def _as_int(value: str, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default
