"""Protocol normalization and command mapping.

Vivaldi distributes the exact REST/MQTT schema separately.  This module keeps
all firmware-specific knowledge in one place, so new payload captures can be
added without changing Home Assistant entities.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .const import SOURCE_NAMES
from .exceptions import TelemacoProtocolError
from .models import PlayerState, TelemacoState, ZoneState

READ_ENDPOINT_CANDIDATES = ("/api/device/status", "/api/status/get")


def _first(data: Mapping[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in data and data[key] is not None:
            return data[key]
    return default


def _bool(value: Any) -> bool:
    if isinstance(value, str):
        return value.lower() in {"1", "true", "on", "yes", "active", "playing"}
    return bool(value)


def _volume(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    if number > 1:
        number /= 100
    return max(0.0, min(1.0, number))


def _items(value: Any) -> list[Mapping[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, Mapping)]
    if isinstance(value, Mapping):
        result = []
        for key, item in value.items():
            if isinstance(item, Mapping):
                result.append({"id": key, **item})
        return result
    return []


def normalize_state(
    payload: Mapping[str, Any],
    *,
    fallback_id: str,
    zone_count: int,
    player_count: int,
) -> TelemacoState:
    """Normalize common Vivaldi payload shapes into a stable model."""
    root = payload.get("data", payload)
    if not isinstance(root, Mapping):
        raise TelemacoProtocolError("The status response is not a JSON object")

    if (
        "api" in root
        and "device" in root
        or "metadata" in root
        and "matrix" in root
        and "outputs" in root
    ):
        return _normalize_rest_aggregate(
            root,
            fallback_id=fallback_id,
            zone_count=zone_count,
            player_count=player_count,
        )

    device = root.get("device", root)
    if not isinstance(device, Mapping):
        device = root

    state = TelemacoState(
        serial=str(_first(device, "serial", "serial_number", "id", "uuid", default=fallback_id)),
        name=str(_first(device, "name", "device_name", "hostname", default="Vivaldi Telemaco")),
        model=str(_first(device, "model", "product", default="TELEMACO")),
        firmware=_first(device, "firmware", "fw_version", "version"),
        mac=_first(device, "mac", "mac_address"),
        online=True,
        paired=_bool(_first(device, "paired", "grouped", default=False)),
        raw=dict(payload),
    )
    state.sources = list(SOURCE_NAMES.values())

    raw_sources = _first(root, "sources", "inputs", default=[])
    if isinstance(raw_sources, list):
        state.sources = [
            str(item.get("name", item.get("id"))) if isinstance(item, Mapping) else str(item)
            for item in raw_sources
        ]

    raw_presets = _first(root, "presets", "scenarios", default={})
    if isinstance(raw_presets, Mapping):
        state.presets = {
            int(k): str(v.get("name", v) if isinstance(v, Mapping) else v)
            for k, v in raw_presets.items()
        }
    elif isinstance(raw_presets, list):
        state.presets = {
            int(_first(item, "id", "index", default=index)): str(
                _first(item, "name", "title", default=f"Preset {index}")
            )
            for index, item in enumerate(_items(raw_presets), 1)
        }

    zones = _items(_first(root, "zones", "outputs", "channels", default=[]))
    for index in range(1, zone_count + 1):
        item = next(
            (z for z in zones if str(_first(z, "id", "index", "channel")) == str(index)), {}
        )
        state.zones[index] = ZoneState(
            id=index,
            name=str(_first(item, "name", "zone_name", default=f"Zona {index}")),
            available=not _bool(_first(item, "disabled", default=False)),
            active=_bool(_first(item, "active", "power", "enabled", "on", default=False)),
            muted=_bool(_first(item, "muted", "mute", default=False)),
            volume=_volume(_first(item, "volume", "level", "vol", default=0)),
            source=_first(item, "source", "source_name", "input"),
            amplifier_error=_bool(_first(item, "error", "amplifier_error", "fault", default=False)),
            stereo=_bool(_first(item, "stereo", "stereo_link", default=False)),
        )

    players = _items(_first(root, "players", "users", default=[]))
    for index in range(1, player_count + 1):
        item = next(
            (p for p in players if str(_first(p, "id", "index", "player")) == str(index)), {}
        )
        playback = str(_first(item, "state", "playback_state", "status", default="idle")).lower()
        state.players[index] = PlayerState(
            id=index,
            name=str(_first(item, "name", "player_name", "user_name", default=f"Player {index}")),
            available=not _bool(_first(item, "disabled", default=False)),
            state=playback,
            muted=_bool(_first(item, "muted", "mute", default=False)),
            volume=_volume(_first(item, "volume", "level", "vol", default=0)),
            source=_first(item, "source", "source_name", "input"),
            title=_first(item, "title", "track", "track_title"),
            artist=_first(item, "artist", "track_artist"),
            album=_first(item, "album", "track_album"),
            preset=_first(item, "preset", "preset_id", "scenario"),
        )
    return state


def command_payload(command: str, **values: Any) -> dict[str, Any]:
    """Build the canonical command envelope used by both transports."""
    return {
        "command": command,
        **{key: value for key, value in values.items() if value is not None},
    }


def _normalize_rest_aggregate(
    root: Mapping[str, Any],
    *,
    fallback_id: str,
    zone_count: int,
    player_count: int,
) -> TelemacoState:
    """Normalize the resources defined by Telemaco RestAPI 1.2.0."""
    api_data = root.get("api", {})
    device = root.get("device", {})
    hostnames = root.get("hostnames", {})
    if not isinstance(api_data, Mapping):
        api_data = {}
    if not isinstance(device, Mapping):
        device = {}
    if not isinstance(hostnames, Mapping):
        hostnames = {}

    link_mode = str(device.get("link", root.get("multiroom", "SINGLE")))
    state = TelemacoState(
        serial=str(api_data.get("device_id", fallback_id)),
        name=str(hostnames.get("device", "Vivaldi Telemaco")),
        model=str(api_data.get("model", "TELEMACO")),
        firmware=str(device.get("device_actual_version") or api_data.get("version") or "") or None,
        online=bool(device.get("ping", True)),
        paired=link_mode != "SINGLE",
        link_mode_id=1 if link_mode == "SINGLE" else 2,
        link_mode=link_mode,
        update_available=bool(device.get("update_available", False)),
        sources=list(SOURCE_NAMES.values()),
        raw=dict(root),
    )

    inputs = root.get("inputs", {})
    metadata = root.get("metadata", {})
    presets = root.get("presets", {})
    matrix = root.get("matrix", {})
    outputs = root.get("outputs", {})
    hostname_inputs = hostnames.get("inputs", {})

    mono_outputs = outputs.get("mono", {}) if isinstance(outputs, Mapping) else {}
    for index in range(1, zone_count + 1):
        output = mono_outputs.get(f"ch{index}", {}) if isinstance(mono_outputs, Mapping) else {}
        if not isinstance(output, Mapping):
            output = {}
        state.zones[index] = ZoneState(
            id=index,
            name=str(output.get("name", f"Zona {index}")),
            available=bool(output.get("amplified", True)),
        )

    for index in range(1, player_count + 1):
        key = f"player{index}"
        input_data = inputs.get(key, {}) if isinstance(inputs, Mapping) else {}
        meta = metadata.get(key, {}) if isinstance(metadata, Mapping) else {}
        names = hostname_inputs.get(key, {}) if isinstance(hostname_inputs, Mapping) else {}
        preset_data = presets.get(key, {}) if isinstance(presets, Mapping) else {}
        if not isinstance(input_data, Mapping):
            input_data = {}
        if not isinstance(meta, Mapping):
            meta = {}
        if not isinstance(names, Mapping):
            names = {}
        if not isinstance(preset_data, Mapping):
            preset_data = {}
        player = PlayerState(
            id=index,
            name=str(names.get("name") or input_data.get("name") or f"Player {index}"),
            state=str(meta.get("status", "idle")),
            muted=bool(input_data.get("mute", False)),
            volume=_volume(input_data.get("volume", 0)),
            source=meta.get("source"),
            title=meta.get("title"),
            artist=meta.get("artist"),
            album=meta.get("album"),
            shuffle=bool(meta.get("shuffle", False)),
            repeat=bool(meta.get("loop", False)),
            image_url=meta.get("image"),
        )
        for item in preset_data.get("presets", []):
            if isinstance(item, Mapping) and item.get("id") is not None:
                player.presets[int(item["id"])] = str(item.get("name", f"Preset {item['id']}"))
                state.presets.setdefault(int(item["id"]), player.presets[int(item["id"])])
        route = matrix.get(key, {}) if isinstance(matrix, Mapping) else {}
        if isinstance(route, Mapping):
            for output_id in range(1, zone_count + 1):
                if bool(route.get(f"out{output_id}", False)):
                    player.routed_outputs.add(output_id)
                    state.zones[output_id].player = index
                    state.zones[output_id].source = f"Player {index}"
                    state.zones[output_id].active = True
        state.players[index] = player
    return state
