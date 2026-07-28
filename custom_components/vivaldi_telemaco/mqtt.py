"""MQTT 1.1 transport for Vivaldi Telemaco."""

from __future__ import annotations

import asyncio
import contextlib
import inspect
import logging
from collections.abc import Awaitable, Callable

import aiomqtt
from homeassistant.components import mqtt
from homeassistant.core import HomeAssistant, callback

from .exceptions import TelemacoConnectionError

TopicCallback = Callable[[str, str], Awaitable[None] | None]
_LOGGER = logging.getLogger(__name__)


class TelemacoMqtt:
    """Use Home Assistant's broker with the documented scalar topic API."""

    def __init__(self, hass: HomeAssistant, root_topic: str) -> None:
        self.hass = hass
        self.root_topic = root_topic.rstrip("/")
        self._unsubscribe: Callable[[], None] | None = None

    async def async_subscribe(self, on_message: TopicCallback) -> None:
        """Subscribe to state topics only, avoiding our own set messages."""

        @callback
        def message_received(message: mqtt.ReceiveMessage) -> None:
            relative = message.topic.removeprefix(f"{self.root_topic}/")
            result = on_message(relative, str(message.payload))
            if result is not None:
                self.hass.async_create_task(result)

        self._unsubscribe = await mqtt.async_subscribe(
            self.hass,
            f"{self.root_topic}/status/#",
            message_received,
            qos=0,
        )

    async def async_publish_topic(self, relative_topic: str, value: str | int) -> None:
        """Publish one exact Telemaco set topic."""
        await mqtt.async_publish(
            self.hass,
            f"{self.root_topic}/set/{relative_topic.lstrip('/')}",
            str(value),
            qos=0,
            retain=False,
        )

    async def async_close(self) -> None:
        if self._unsubscribe:
            self._unsubscribe()
            self._unsubscribe = None


class DirectTelemacoMqtt:
    """Connect directly to the MQTT broker embedded in Telemaco."""

    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
        port: int,
        root_topic: str,
    ) -> None:
        self.hass = hass
        self.host = host
        self.port = port
        self.root_topic = root_topic.rstrip("/")
        self._callback: TopicCallback | None = None
        self._client: aiomqtt.Client | None = None
        self._task: asyncio.Task[None] | None = None
        self._connected = asyncio.Event()
        self._closing = False

    async def async_subscribe(self, on_message: TopicCallback) -> None:
        """Start the reconnecting direct subscription."""
        self._callback = on_message
        if self._task is None:
            self._task = self.hass.async_create_background_task(
                self._async_run(),
                name=f"vivaldi_telemaco_mqtt_{self.host}",
            )

    async def _async_run(self) -> None:
        while not self._closing:
            try:
                async with aiomqtt.Client(self.host, port=self.port) as client:
                    self._client = client
                    self._connected.set()
                    await client.subscribe(f"{self.root_topic}/status/#", qos=0)
                    async for message in client.messages:
                        if self._callback is None:
                            continue
                        topic = str(message.topic)
                        relative = topic.removeprefix(f"{self.root_topic}/")
                        payload = message.payload
                        if isinstance(payload, bytes):
                            value = payload.decode(errors="replace")
                        else:
                            value = str(payload)
                        result = self._callback(relative, value)
                        if inspect.isawaitable(result):
                            await result
            except asyncio.CancelledError:
                raise
            except (aiomqtt.MqttError, OSError) as err:
                _LOGGER.debug(
                    "Direct Telemaco MQTT connection to %s:%s unavailable: %s",
                    self.host,
                    self.port,
                    err,
                )
            finally:
                self._client = None
                self._connected.clear()
            if not self._closing:
                await asyncio.sleep(5)

    async def async_publish_topic(self, relative_topic: str, value: str | int) -> None:
        """Publish one command through the embedded broker."""
        try:
            await asyncio.wait_for(self._connected.wait(), timeout=10)
        except TimeoutError as err:
            raise TelemacoConnectionError(
                f"MQTT broker {self.host}:{self.port} is not connected"
            ) from err
        if self._client is None:
            raise TelemacoConnectionError("Direct MQTT client is not connected")
        try:
            await self._client.publish(
                f"{self.root_topic}/set/{relative_topic.lstrip('/')}",
                str(value),
                qos=0,
                retain=False,
            )
        except aiomqtt.MqttError as err:
            raise TelemacoConnectionError(str(err)) from err

    async def async_close(self) -> None:
        """Stop the direct MQTT connection."""
        self._closing = True
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
