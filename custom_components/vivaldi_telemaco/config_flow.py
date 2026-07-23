"""Config flow for Vivaldi Telemaco."""

from __future__ import annotations

import hashlib
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .api import TelemacoApi
from .const import (
    CONF_API_TOKEN,
    CONF_MQTT_PREFIX,
    CONF_PASSWORD,
    CONF_PLAYER_COUNT,
    CONF_SCAN_INTERVAL,
    CONF_TRANSPORT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    CONF_ZONE_COUNT,
    DEFAULT_MQTT_PREFIX,
    DEFAULT_NAME,
    DEFAULT_PLAYER_COUNT,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_ZONE_COUNT,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
    TRANSPORT_API,
    TRANSPORT_HYBRID,
    TRANSPORT_MQTT,
)
from .exceptions import (
    TelemacoAuthenticationError,
    TelemacoConnectionError,
    TelemacoProtocolError,
)
from .protocol import normalize_state


def _schema(defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_NAME, default=defaults.get(CONF_NAME, DEFAULT_NAME)): str,
            vol.Required(CONF_HOST, default=defaults.get(CONF_HOST, "")): str,
            vol.Required(CONF_PORT, default=defaults.get(CONF_PORT, DEFAULT_PORT)): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=65535)
            ),
            vol.Required(
                CONF_TRANSPORT, default=defaults.get(CONF_TRANSPORT, TRANSPORT_HYBRID)
            ): vol.In([TRANSPORT_HYBRID, TRANSPORT_API, TRANSPORT_MQTT]),
            vol.Optional(CONF_API_TOKEN, default=defaults.get(CONF_API_TOKEN, "")): str,
            vol.Optional(CONF_USERNAME, default=defaults.get(CONF_USERNAME, "admin")): str,
            vol.Optional(CONF_PASSWORD, default=defaults.get(CONF_PASSWORD, "")): str,
            vol.Optional(
                CONF_MQTT_PREFIX,
                default=defaults.get(CONF_MQTT_PREFIX, DEFAULT_MQTT_PREFIX),
            ): str,
            vol.Required(
                CONF_ZONE_COUNT, default=defaults.get(CONF_ZONE_COUNT, DEFAULT_ZONE_COUNT)
            ): vol.All(vol.Coerce(int), vol.In([6, 12])),
            vol.Required(
                CONF_PLAYER_COUNT,
                default=defaults.get(CONF_PLAYER_COUNT, DEFAULT_PLAYER_COUNT),
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=6)),
            vol.Required(CONF_VERIFY_SSL, default=defaults.get(CONF_VERIFY_SSL, True)): bool,
        }
    )


class TelemacoConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Set up Vivaldi Telemaco."""

    VERSION = 1

    def __init__(self) -> None:
        self._discovered: dict[str, Any] = {}

    async def async_step_zeroconf(self, discovery_info: ZeroconfServiceInfo) -> FlowResult:
        host = discovery_info.host
        self._discovered = {
            CONF_HOST: host,
            CONF_NAME: discovery_info.name.split(".")[0] or DEFAULT_NAME,
        }
        await self.async_set_unique_id(
            discovery_info.properties.get("serial")
            or discovery_info.properties.get("id")
            or hashlib.sha256(host.encode()).hexdigest()[:16]
        )
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})
        return await self.async_step_user()

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            user_input[CONF_HOST] = host
            transport = user_input[CONF_TRANSPORT]
            unique_id = hashlib.sha256(host.encode()).hexdigest()[:16]

            if transport in (TRANSPORT_API, TRANSPORT_HYBRID):
                api = TelemacoApi(
                    async_get_clientsession(self.hass),
                    host,
                    token=user_input.get(CONF_API_TOKEN) or None,
                    username=user_input.get(CONF_USERNAME) or None,
                    password=user_input.get(CONF_PASSWORD) or None,
                    port=user_input[CONF_PORT],
                    verify_ssl=user_input[CONF_VERIFY_SSL],
                )
                try:
                    await api.async_validate_auth()
                    payload = await api.async_get_status()
                    api_data = payload.get("api", {})
                    if (
                        transport == TRANSPORT_HYBRID
                        and user_input.get(CONF_MQTT_PREFIX) == DEFAULT_MQTT_PREFIX
                        and isinstance(api_data, dict)
                    ):
                        mqtt_data = api_data.get("mqtt_client", {})
                        if isinstance(mqtt_data, dict) and mqtt_data.get("root_topic"):
                            user_input[CONF_MQTT_PREFIX] = mqtt_data["root_topic"]
                    state = normalize_state(
                        payload,
                        fallback_id=unique_id,
                        zone_count=user_input[CONF_ZONE_COUNT],
                        player_count=user_input[CONF_PLAYER_COUNT],
                    )
                    unique_id = state.serial
                    user_input[CONF_NAME] = state.name or user_input[CONF_NAME]
                except TelemacoAuthenticationError:
                    errors["base"] = "invalid_auth"
                except TelemacoConnectionError:
                    errors["base"] = "cannot_connect"
                except TelemacoProtocolError:
                    errors["base"] = "unsupported_firmware"

            if not errors:
                await self.async_set_unique_id(str(unique_id))
                self._abort_if_unique_id_configured(updates={CONF_HOST: host})
                return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)

        defaults = {**self._discovered, **(user_input or {})}
        return self.async_show_form(step_id="user", data_schema=_schema(defaults), errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> TelemacoOptionsFlow:
        return TelemacoOptionsFlow(config_entry)


class TelemacoOptionsFlow(config_entries.OptionsFlow):
    """Runtime-tunable options."""

    def __init__(self, entry: config_entries.ConfigEntry) -> None:
        self.entry = entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        current = {**self.entry.data, **self.entry.options}
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_SCAN_INTERVAL,
                    default=current.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                ): vol.All(
                    vol.Coerce(int),
                    vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL),
                ),
                vol.Required(
                    CONF_ZONE_COUNT,
                    default=current.get(CONF_ZONE_COUNT, DEFAULT_ZONE_COUNT),
                ): vol.In([6, 12]),
                vol.Required(
                    CONF_PLAYER_COUNT,
                    default=current.get(CONF_PLAYER_COUNT, DEFAULT_PLAYER_COUNT),
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=6)),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
