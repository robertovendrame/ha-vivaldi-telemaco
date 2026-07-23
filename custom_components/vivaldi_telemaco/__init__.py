"""Vivaldi Telemaco integration."""

from __future__ import annotations

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import TelemacoApi
from .const import (
    ATTR_COMMAND,
    ATTR_PAYLOAD,
    ATTR_PLAYER,
    ATTR_PRESET,
    ATTR_SOUND,
    CONF_API_TOKEN,
    CONF_MQTT_PREFIX,
    CONF_PASSWORD,
    CONF_TRANSPORT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    DOMAIN,
    PLATFORMS,
    SERVICE_DOORBELL,
    SERVICE_PLAY_PRESET,
    SERVICE_SEND_COMMAND,
    TRANSPORT_API,
    TRANSPORT_HYBRID,
    TRANSPORT_MQTT,
)
from .coordinator import TelemacoCoordinator
from .mqtt import TelemacoMqtt

type TelemacoConfigEntry = ConfigEntry[TelemacoCoordinator]

SEND_COMMAND_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_COMMAND): cv.string,
        vol.Optional(ATTR_PAYLOAD, default={}): dict,
    }
)
PLAY_PRESET_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_PLAYER): vol.All(vol.Coerce(int), vol.Range(min=1, max=6)),
        vol.Required(ATTR_PRESET): vol.All(vol.Coerce(int), vol.Range(min=1)),
    }
)
DOORBELL_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_SOUND, default=0): vol.All(vol.Coerce(int), vol.Range(min=0)),
    }
)


async def async_setup_entry(hass: HomeAssistant, entry: TelemacoConfigEntry) -> bool:
    """Set up one Telemaco."""
    transport = entry.data[CONF_TRANSPORT]
    api = None
    mqtt_client = None

    if transport in (TRANSPORT_API, TRANSPORT_HYBRID):
        api = TelemacoApi(
            async_get_clientsession(hass),
            entry.data[CONF_HOST],
            token=entry.data.get(CONF_API_TOKEN) or None,
            username=entry.data.get(CONF_USERNAME) or None,
            password=entry.data.get(CONF_PASSWORD) or None,
            port=entry.data[CONF_PORT],
            verify_ssl=entry.data[CONF_VERIFY_SSL],
        )
    if transport in (TRANSPORT_MQTT, TRANSPORT_HYBRID):
        mqtt_client = TelemacoMqtt(hass, entry.data[CONF_MQTT_PREFIX])

    coordinator = TelemacoCoordinator(hass, entry, api, mqtt_client)
    entry.runtime_data = coordinator

    if mqtt_client:
        if api is None:
            coordinator.async_set_updated_data(coordinator._normalize({}))
        await mqtt_client.async_subscribe(coordinator.async_process_mqtt)
    if api:
        await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    _register_services(hass)
    return True


def _register_services(hass: HomeAssistant) -> None:
    if hass.services.has_service(DOMAIN, SERVICE_SEND_COMMAND):
        return

    def coordinators() -> list[TelemacoCoordinator]:
        return [
            item.runtime_data
            for item in hass.config_entries.async_entries(DOMAIN)
            if item.state is ConfigEntryState.LOADED and item.runtime_data
        ]

    async def send_command(call: ServiceCall) -> None:
        active = coordinators()
        if not active:
            raise HomeAssistantError("No loaded Telemaco device")
        for coordinator in active:
            await coordinator.async_command(call.data[ATTR_COMMAND], **call.data[ATTR_PAYLOAD])

    async def play_preset(call: ServiceCall) -> None:
        for coordinator in coordinators():
            await coordinator.async_command(
                "player_preset",
                player=call.data[ATTR_PLAYER],
                preset=call.data[ATTR_PRESET],
            )

    async def doorbell(call: ServiceCall) -> None:
        for coordinator in coordinators():
            await coordinator.async_command("doorbell", sound=call.data[ATTR_SOUND])

    hass.services.async_register(
        DOMAIN, SERVICE_SEND_COMMAND, send_command, schema=SEND_COMMAND_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_PLAY_PRESET, play_preset, schema=PLAY_PRESET_SCHEMA
    )
    hass.services.async_register(DOMAIN, SERVICE_DOORBELL, doorbell, schema=DOORBELL_SCHEMA)


async def _async_reload_entry(hass: HomeAssistant, entry: TelemacoConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: TelemacoConfigEntry) -> bool:
    """Unload Telemaco and MQTT subscriptions."""
    coordinator = entry.runtime_data
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded and coordinator.mqtt:
        await coordinator.mqtt.async_close()
    return unloaded
