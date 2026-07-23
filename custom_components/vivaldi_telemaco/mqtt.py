"""MQTT 1.1 transport for Vivaldi Telemaco."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from homeassistant.components import mqtt
from homeassistant.core import HomeAssistant, callback

TopicCallback = Callable[[str, str], Awaitable[None] | None]


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
