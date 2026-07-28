"""Local WebSocket support for Vivaldi C4IO button interfaces."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from aiohttp import ClientError, ClientSession, WSMsgType
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

C4IO_EVENT_TYPES = ("short_press", "long_press")
RECONNECT_DELAY = 5


@dataclass(frozen=True, slots=True)
class C4IODeviceSpec:
    """Configured C4IO endpoint."""

    name: str
    host: str


def parse_c4io_devices(value: str | None) -> list[C4IODeviceSpec]:
    """Parse one ``name=host`` C4IO definition per line."""
    devices: list[C4IODeviceSpec] = []
    seen_hosts: set[str] = set()
    for number, raw_line in enumerate((value or "").splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ValueError(f"Riga C4IO {number}: usa Nome=IP")
        name, host = (part.strip() for part in line.split("=", 1))
        if not name or not host:
            raise ValueError(f"Riga C4IO {number}: nome e indirizzo sono obbligatori")
        if host in seen_hosts:
            raise ValueError(f"Riga C4IO {number}: indirizzo duplicato {host}")
        seen_hosts.add(host)
        devices.append(C4IODeviceSpec(name=name, host=host))
    return devices


@dataclass(slots=True)
class C4IOState:
    """Runtime information returned by a C4IO."""

    connected: bool = False
    mac: str | None = None
    firmware: str | None = None
    rssi: int | None = None
    mqtt_connected: bool | None = None
    restart_count: int | None = None
    input_config: dict[str, Any] = field(default_factory=dict)


class C4IOClient:
    """Maintain one reconnecting C4IO WebSocket."""

    def __init__(self, session: ClientSession, spec: C4IODeviceSpec) -> None:
        self.session = session
        self.spec = spec
        self.state = C4IOState()
        self._closing = False
        self._task: asyncio.Task[None] | None = None
        self._listeners: set[Callable[[], None]] = set()
        self._event_listeners: set[Callable[[int, str], None]] = set()

    def start(self) -> None:
        """Start the reconnect loop."""
        if self._task is None:
            self._task = asyncio.create_task(
                self._async_run(), name=f"vivaldi_c4io_{self.spec.host}"
            )

    async def async_close(self) -> None:
        """Stop the reconnect loop."""
        self._closing = True
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None

    def add_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        """Register a state listener."""
        self._listeners.add(listener)
        return lambda: self._listeners.discard(listener)

    def add_event_listener(
        self, listener: Callable[[int, str], None]
    ) -> Callable[[], None]:
        """Register a physical input-event listener."""
        self._event_listeners.add(listener)
        return lambda: self._event_listeners.discard(listener)

    def _notify(self) -> None:
        for listener in tuple(self._listeners):
            listener()

    async def _async_run(self) -> None:
        while not self._closing:
            try:
                async with self.session.ws_connect(
                    f"ws://{self.spec.host}/ws",
                    protocols=("websocket",),
                    timeout=10,
                ) as websocket:
                    self.state.connected = True
                    self._notify()
                    for key in ("info", "config", "network"):
                        await websocket.send_json({"action": "?", "key": key, "data": {}})

                    async for message in websocket:
                        if message.type == WSMsgType.TEXT:
                            self._process_message(message.data)
                        elif message.type in (
                            WSMsgType.CLOSE,
                            WSMsgType.CLOSED,
                            WSMsgType.ERROR,
                        ):
                            break
            except asyncio.CancelledError:
                raise
            except (ClientError, OSError, TimeoutError, ValueError) as err:
                _LOGGER.debug("C4IO %s WebSocket unavailable: %s", self.spec.host, err)
            except Exception:
                _LOGGER.exception("Unexpected C4IO %s WebSocket error", self.spec.host)
            finally:
                if self.state.connected:
                    self.state.connected = False
                    self._notify()

            if not self._closing:
                await asyncio.sleep(RECONNECT_DELAY)

    def _process_message(self, raw_message: str) -> None:
        try:
            message = json.loads(raw_message)
        except (TypeError, ValueError):
            _LOGGER.debug("Invalid C4IO message from %s", self.spec.host)
            return
        if not isinstance(message, dict):
            return

        action = message.get("action")
        key = message.get("key")
        data = message.get("data")
        if not isinstance(data, dict):
            return

        if action == "&&" and key == "input_event":
            input_id = data.get("input")
            event_type = data.get("event")
            try:
                input_number = int(input_id)
            except (TypeError, ValueError):
                return
            if input_number in range(1, 5) and event_type in C4IO_EVENT_TYPES:
                for listener in tuple(self._event_listeners):
                    listener(input_number, str(event_type))
            return

        if action != "@":
            return
        if key == "info":
            self.state.mac = str(data.get("mac") or "") or None
            app = data.get("app")
            if isinstance(app, dict):
                self.state.firmware = str(app.get("version") or "") or None
            restart_count = data.get("restart_count")
            if isinstance(restart_count, int):
                self.state.restart_count = restart_count
        elif key == "network":
            rssi = data.get("rssi")
            if isinstance(rssi, (int, float)):
                self.state.rssi = int(rssi)
        elif key == "wifi":
            rssi = data.get("rssi")
            if isinstance(rssi, (int, float)):
                self.state.rssi = int(rssi)
        elif key == "config":
            inputs = data.get("inputs")
            if isinstance(inputs, dict):
                self.state.input_config = inputs
            settings = data.get("settings")
            if isinstance(settings, dict):
                mqtt = settings.get("mqtt")
                if isinstance(mqtt, dict):
                    connected = mqtt.get("connected", mqtt.get("conn_state"))
                    if isinstance(connected, bool):
                        self.state.mqtt_connected = connected
        self._notify()


class C4IOManager:
    """Collection of configured C4IO WebSocket clients."""

    def __init__(self, session: ClientSession, specs: list[C4IODeviceSpec]) -> None:
        self.clients = [C4IOClient(session, spec) for spec in specs]

    def start(self) -> None:
        """Start every configured client."""
        for client in self.clients:
            client.start()

    async def async_close(self) -> None:
        """Close every configured client."""
        await asyncio.gather(
            *(client.async_close() for client in self.clients),
            return_exceptions=True,
        )


class C4IOEntity(Entity):
    """Base entity belonging to one C4IO device."""

    _attr_has_entity_name = True

    def __init__(self, client: C4IOClient) -> None:
        self.client = client

    @property
    def available(self) -> bool:
        return self.client.state.connected

    @property
    def device_info(self) -> DeviceInfo:
        connections = (
            {(CONNECTION_NETWORK_MAC, self.client.state.mac)}
            if self.client.state.mac
            else set()
        )
        return DeviceInfo(
            identifiers={(DOMAIN, f"c4io_{self.client.spec.host}")},
            connections=connections,
            manufacturer="Vivaldi",
            model="C4IO",
            name=self.client.spec.name,
            sw_version=self.client.state.firmware,
            configuration_url=f"http://{self.client.spec.host}",
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(self.client.add_listener(self.async_write_ha_state))
