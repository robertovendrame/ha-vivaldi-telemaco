"""Tests for protocol normalization."""

import importlib.util
import json
import sys
import types
from pathlib import Path

ROOT = Path(__file__).parents[1]
PACKAGE = ROOT / "custom_components" / "vivaldi_telemaco"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(
        f"vivaldi_telemaco.{name}", PACKAGE / f"{name}.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


pkg = types.ModuleType("vivaldi_telemaco")
pkg.__path__ = [str(PACKAGE)]
sys.modules["vivaldi_telemaco"] = pkg
_load("exceptions")
models = _load("models")
protocol = _load("protocol")


def test_normalize_full_state() -> None:
    payload = json.loads((ROOT / "tests" / "fixtures" / "status.json").read_text())
    state = protocol.normalize_state(payload, fallback_id="fallback", zone_count=6, player_count=4)
    assert state.serial == "TM-DEMO-001"
    assert state.zones[1].name == "Soggiorno"
    assert state.zones[1].volume == 0.35
    assert state.zones[2].active is False
    assert len(state.zones) == 6
    assert state.players[1].title == "Demo track"
    assert state.players[1].state == "playing"
    assert len(state.players) == 4


def test_normalize_dictionary_shapes() -> None:
    state = protocol.normalize_state(
        {
            "id": "abc",
            "outputs": {"1": {"name": "Bagno", "mute": "true", "level": 75}},
            "users": {"1": {"name": "Utente", "status": "pause"}},
        },
        fallback_id="fallback",
        zone_count=1,
        player_count=1,
    )
    assert state.zones[1].muted is True
    assert state.zones[1].volume == 0.75
    assert state.players[1].state == "pause"


def test_normalize_rest_aggregate() -> None:
    payload = json.loads((ROOT / "tests" / "fixtures" / "rest_aggregate.json").read_text())
    state = protocol.normalize_state(
        payload,
        fallback_id="fallback",
        zone_count=6,
        player_count=4,
    )
    assert state.serial == "DEMO00000001"
    assert state.name == "Telemaco Demo"
    assert state.firmware == "2033.05.5"
    assert state.zones[1].name == "Soggiorno"
    assert state.zones[1].source == "Player 1"
    assert state.players[1].name == "Utente Demo"
    assert state.players[1].volume == 0.42
    assert state.players[1].title == "Brano"
    assert state.players[1].repeat is True
    assert state.players[1].presets[1] == "Metal"
