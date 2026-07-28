"""Tests for C4IO configuration and event decoding."""

import importlib.util
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

aiohttp = types.ModuleType("aiohttp")
aiohttp.ClientError = type("ClientError", (Exception,), {})
aiohttp.ClientSession = type("ClientSession", (), {})
aiohttp.WSMsgType = type(
    "WSMsgType",
    (),
    {"TEXT": "text", "CLOSE": "close", "CLOSED": "closed", "ERROR": "error"},
)
sys.modules["aiohttp"] = aiohttp

homeassistant = types.ModuleType("homeassistant")
helpers = types.ModuleType("homeassistant.helpers")
device_registry = types.ModuleType("homeassistant.helpers.device_registry")
entity = types.ModuleType("homeassistant.helpers.entity")
device_registry.CONNECTION_NETWORK_MAC = "mac"
device_registry.DeviceInfo = type("DeviceInfo", (dict,), {})
entity.Entity = type("Entity", (), {})
sys.modules["homeassistant"] = homeassistant
sys.modules["homeassistant.helpers"] = helpers
sys.modules["homeassistant.helpers.device_registry"] = device_registry
sys.modules["homeassistant.helpers.entity"] = entity

c4io = _load("c4io")


def test_parse_c4io_devices() -> None:
    devices = c4io.parse_c4io_devices(
        "# studio\nSTUDIO 1=192.168.2.83\nUFFICIO = 192.168.2.90"
    )
    assert [(item.name, item.host) for item in devices] == [
        ("STUDIO 1", "192.168.2.83"),
        ("UFFICIO", "192.168.2.90"),
    ]


def test_parse_c4io_devices_rejects_invalid_and_duplicates() -> None:
    for value in ("STUDIO 1", "STUDIO 1=", "A=192.168.2.83\nB=192.168.2.83"):
        try:
            c4io.parse_c4io_devices(value)
        except ValueError:
            pass
        else:
            raise AssertionError(f"Accepted invalid C4IO definitions: {value}")


def test_decode_short_and_long_press_events() -> None:
    client = c4io.C4IOClient(
        object(),
        c4io.C4IODeviceSpec(name="STUDIO 2", host="192.168.2.84"),
    )
    events = []
    client.add_event_listener(
        lambda input_number, event_type: events.append((input_number, event_type))
    )
    client._process_message(
        '{"action":"&&","key":"input_event",'
        '"data":{"input":"2","event":"short_press"}}'
    )
    client._process_message(
        '{"action":"&&","key":"input_event",'
        '"data":{"input":"2","event":"release"}}'
    )
    client._process_message(
        '{"action":"&&","key":"input_event",'
        '"data":{"input":"4","event":"long_press"}}'
    )
    assert events == [(2, "short_press"), (4, "long_press")]
