"""Data models for Vivaldi Telemaco."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ZoneState:
    """Normalized Telemaco zone state."""

    id: int
    name: str
    available: bool = True
    active: bool = False
    muted: bool = False
    volume: float = 0.0
    source: str | None = None
    amplifier_error: bool = False
    stereo: bool = False
    dnd: bool = False
    eq_low: int = 0
    eq_mid: int = 0
    eq_high: int = 0
    player: int | None = None


@dataclass(slots=True)
class PlayerState:
    """Normalized Telemaco player state."""

    id: int
    name: str
    available: bool = True
    state: str = "idle"
    muted: bool = False
    volume: float = 0.0
    source: str | None = None
    title: str | None = None
    artist: str | None = None
    album: str | None = None
    preset: int | None = None
    shuffle: bool = False
    repeat: bool = False
    image_url: str | None = None
    routed_outputs: set[int] = field(default_factory=set)
    presets: dict[int, str] = field(default_factory=dict)


@dataclass(slots=True)
class TelemacoState:
    """Complete normalized state."""

    serial: str
    name: str
    model: str = "TELEMACO"
    firmware: str | None = None
    mac: str | None = None
    online: bool = True
    paired: bool = False
    link_mode_id: int = 1
    link_mode: str = "SINGLE"
    update_available: bool = False
    zones: dict[int, ZoneState] = field(default_factory=dict)
    players: dict[int, PlayerState] = field(default_factory=dict)
    sources: list[str] = field(default_factory=list)
    presets: dict[int, str] = field(default_factory=dict)
    signals: dict[int, bool] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict, repr=False)
