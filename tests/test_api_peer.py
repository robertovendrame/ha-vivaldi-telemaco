"""Tests for linked Telemaco REST resources."""

import asyncio
import importlib.util
import sys
import types
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parents[1]
PACKAGE = ROOT / "custom_components" / "vivaldi_telemaco"

try:
    import aiohttp  # noqa: F401
except ModuleNotFoundError:
    aiohttp_stub = types.ModuleType("aiohttp")
    aiohttp_stub.ClientError = type("ClientError", (Exception,), {})
    aiohttp_stub.ClientResponse = object
    aiohttp_stub.ClientSession = object

    class ClientTimeout:
        def __init__(self, total: int) -> None:
            self.total = total

    aiohttp_stub.ClientTimeout = ClientTimeout
    sys.modules["aiohttp"] = aiohttp_stub


def _load(name: str):
    spec = importlib.util.spec_from_file_location(
        f"vivaldi_telemaco.{name}", PACKAGE / f"{name}.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


pkg = sys.modules.setdefault("vivaldi_telemaco", types.ModuleType("vivaldi_telemaco"))
pkg.__path__ = [str(PACKAGE)]
_load("exceptions")
api_module = _load("api")


class FakePeer:
    """Minimal linked device client."""

    def __init__(self) -> None:
        self.host = "192.168.2.81"
        self.commands: list[tuple[str, dict[str, Any]]] = []

    async def request(self, method: str, endpoint: str):
        resources = {
            "/api/metadata/get": {"player1": {"title": "Slave track"}},
            "/api/presets/get": {
                "player1": {"presets": [{"id": 7, "name": "Slave preset"}]}
            },
            "/api/input/get": {"player1": {"volume": 45}},
            "/api/hostnames/get": {
                "inputs": {"player1": {"name": "Slave player 1"}}
            },
        }
        return resources[endpoint]

    async def async_send_command(self, command: str, payload: dict[str, Any]):
        self.commands.append((command, payload))
        return {"success": True}


def _main_with_peer() -> tuple[Any, FakePeer]:
    main = api_module.TelemacoApi.__new__(api_module.TelemacoApi)
    peer = FakePeer()
    main._peer_api = peer
    main._peer_player_offset = 3
    return main, peer


def test_merge_slave_players() -> None:
    main, _peer = _main_with_peer()
    combined = {
        "metadata": {},
        "presets": {},
        "inputs": {},
        "hostnames": {"inputs": {}},
    }
    asyncio.run(main._async_merge_peer_players(combined))
    assert combined["metadata"]["player4"]["title"] == "Slave track"
    assert combined["presets"]["player4"]["presets"][0]["id"] == 7
    assert combined["inputs"]["player4"]["volume"] == 45
    assert combined["hostnames"]["inputs"]["player4"]["name"] == "Slave player 1"
    assert combined["peer"]["host"] == "192.168.2.81"


def test_slave_player_command_is_remapped() -> None:
    main, peer = _main_with_peer()
    asyncio.run(
        main.async_send_command(
            "player_preset",
            {"player": 4, "preset": 7},
        )
    )
    assert peer.commands == [
        ("player_preset", {"player": 1, "preset": 7}),
    ]
