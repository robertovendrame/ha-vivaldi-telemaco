"""Local REST client for Vivaldi Telemaco."""

from __future__ import annotations

import asyncio
import ipaddress
import time
from collections.abc import Mapping
from typing import Any

from aiohttp import ClientError, ClientResponse, ClientSession, ClientTimeout

from .exceptions import (
    TelemacoAuthenticationError,
    TelemacoConnectionError,
    TelemacoProtocolError,
)

STATUS_ENDPOINTS = {
    "device": "/api/device/status",
    "metadata": "/api/metadata/get",
    "presets": "/api/presets/get",
    "inputs": "/api/input/get",
    "matrix": "/api/matrix/get",
    "outputs": "/api/output/get",
    "hostnames": "/api/hostnames/get",
    "multiroom": "/api/status/get",
    "api": "/api/api/status",
}


class TelemacoApi:
    """Async REST API client."""

    def __init__(
        self,
        session: ClientSession,
        host: str,
        *,
        token: str | None = None,
        username: str | None = None,
        password: str | None = None,
        port: int = 80,
        verify_ssl: bool = True,
        timeout: int = 10,
        peer_player_offset: int = 3,
    ) -> None:
        scheme = "https" if port == 443 else "http"
        self.base_url = f"{scheme}://{host}:{port}"
        self.host = host
        self.port = port
        self._session = session
        self._token = token
        self._username = username
        self._password = password
        self._token_expires_at = 0.0
        self._verify_ssl = verify_ssl
        self._timeout = ClientTimeout(total=timeout)
        self._peer_player_offset = peer_player_offset
        self._peer_api: TelemacoApi | None = None

    @property
    def headers(self) -> dict[str, str]:
        """Return authentication headers used by known firmware variants."""
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
            headers["X-Auth-Token"] = self._token
        return headers

    async def _decode(self, response: ClientResponse) -> Any:
        if response.status in (401, 403):
            raise TelemacoAuthenticationError("Invalid Telemaco access token")
        if response.status >= 400:
            raise TelemacoProtocolError(f"Telemaco returned HTTP {response.status}")
        try:
            payload = await response.json(content_type=None)
        except (ValueError, TypeError) as err:
            raise TelemacoProtocolError("Telemaco returned a non-JSON response") from err
        if not isinstance(payload, (Mapping, str, int, float, bool)) and payload is not None:
            raise TelemacoProtocolError("Telemaco returned an unsupported JSON payload")
        return payload

    async def request(
        self,
        method: str,
        endpoint: str,
        payload: Mapping[str, Any] | None = None,
        *,
        authenticated: bool = False,
        retry_auth: bool = True,
    ) -> Any:
        """Perform an authenticated request."""
        if authenticated:
            await self.async_ensure_token()
        try:
            async with asyncio.timeout(self._timeout.total):
                async with self._session.request(
                    method,
                    f"{self.base_url}{endpoint}",
                    headers=self.headers,
                    json=payload,
                    ssl=self._verify_ssl,
                    timeout=self._timeout,
                ) as response:
                    return await self._decode(response)
        except TelemacoAuthenticationError:
            if authenticated and retry_auth and self._username and self._password:
                await self.async_login()
                return await self.request(
                    method,
                    endpoint,
                    payload,
                    authenticated=True,
                    retry_auth=False,
                )
            raise
        except (ClientError, TimeoutError, OSError) as err:
            raise TelemacoConnectionError(str(err)) from err

    async def async_login(self) -> None:
        """Retrieve a JWT using the documented webpage user credentials."""
        if not self._username or not self._password:
            raise TelemacoAuthenticationError("Username and password are required")
        result = await self.request(
            "POST",
            "/api/session/login",
            {"username": self._username, "password": self._password},
        )
        token = result.get("token")
        if not token:
            raise TelemacoAuthenticationError("Login response did not contain a token")
        self._token = str(token)
        expiration_ms = float(result.get("expiration", 7_200_000))
        self._token_expires_at = time.monotonic() + max(60, expiration_ms / 1000 - 60)

    async def async_refresh_token(self) -> None:
        """Refresh the current JWT."""
        result = await self.request(
            "GET",
            "/api/session/refresh",
            authenticated=False,
            retry_auth=False,
        )
        token = result.get("token")
        if not token:
            raise TelemacoAuthenticationError("Refresh response did not contain a token")
        self._token = str(token)
        expiration_ms = float(result.get("expiration", 7_200_000))
        self._token_expires_at = time.monotonic() + max(60, expiration_ms / 1000 - 60)

    async def async_ensure_token(self) -> None:
        """Log in or refresh shortly before token expiry."""
        if self._token and (
            self._token_expires_at == 0 or time.monotonic() < self._token_expires_at
        ):
            return
        if self._token and self._token_expires_at:
            try:
                await self.async_refresh_token()
                return
            except TelemacoAuthenticationError:
                pass
        await self.async_login()

    async def async_validate_auth(self) -> None:
        """Validate credentials against an authenticated read-only endpoint."""
        await self.request("GET", "/api/user/get", authenticated=True)

    async def async_get_status(self) -> Mapping[str, Any]:
        """Read and combine the documented Telemaco REST resources."""
        async def read_resource(key: str, endpoint: str) -> tuple[str, Any, Exception | None]:
            try:
                return key, await self.request("GET", endpoint), None
            except TelemacoAuthenticationError:
                raise
            except (TelemacoConnectionError, TelemacoProtocolError) as err:
                return key, None, err

        results = await asyncio.gather(
            *(read_resource(key, endpoint) for key, endpoint in STATUS_ENDPOINTS.items())
        )
        combined: dict[str, Any] = {}
        last_error: Exception | None = None
        for key, value, error in results:
            if error is not None:
                last_error = error
                continue
            if isinstance(value, Mapping):
                combined[key] = dict(value)
            elif key == "multiroom" and isinstance(value, str):
                combined[key] = value
        if not combined:
            raise TelemacoProtocolError(
                "No documented Telemaco REST endpoint was reachable"
            ) from last_error
        await self._async_merge_peer_players(combined)
        return combined

    def _new_peer_api(self, host: str) -> TelemacoApi:
        """Create a client for the linked Telemaco peer."""
        return TelemacoApi(
            self._session,
            host,
            token=None,
            username=self._username,
            password=self._password,
            port=self.port,
            verify_ssl=self._verify_ssl,
            timeout=int(self._timeout.total or 10),
            peer_player_offset=self._peer_player_offset,
        )

    @staticmethod
    def _valid_peer_ip(value: Any) -> str | None:
        """Return a usable peer address from a device status field."""
        if not isinstance(value, str):
            return None
        candidate = value.strip()
        try:
            ipaddress.ip_address(candidate)
        except ValueError:
            return None
        return candidate

    async def _async_find_peer(self, combined: Mapping[str, Any]) -> TelemacoApi | None:
        """Find the only linked or nearby Telemaco device."""
        if self._peer_api is not None:
            return self._peer_api

        device = combined.get("device", {})
        candidate: str | None = None
        if isinstance(device, Mapping):
            link = str(device.get("link", "")).upper()
            field = "slave" if link == "MULTI" else "master" if link == "SLAVE" else ""
            if field:
                candidate = self._valid_peer_ip(device.get(field))

        if candidate is None:
            try:
                devices = await self.request("GET", "/api/devices/get")
            except (TelemacoConnectionError, TelemacoProtocolError):
                return None
            items = devices.get("devices", [])
            candidates = [
                ip
                for item in items
                if isinstance(item, Mapping)
                and (ip := self._valid_peer_ip(item.get("ip"))) is not None
                and ip != self.host
            ]
            if len(candidates) == 1:
                candidate = candidates[0]

        if candidate is None or candidate == self.host:
            return None
        self._peer_api = self._new_peer_api(candidate)
        if isinstance(combined, dict):
            combined["peer"] = {"host": candidate}
        return self._peer_api

    async def _async_merge_peer_players(self, combined: dict[str, Any]) -> None:
        """Merge the slave's local player1..n resources after the master players."""
        peer = await self._async_find_peer(combined)
        if peer is None:
            return
        combined["peer"] = {"host": peer.host}

        resources = {
            "metadata": "/api/metadata/get",
            "presets": "/api/presets/get",
            "inputs": "/api/input/get",
            "hostnames": "/api/hostnames/get",
        }

        async def read_peer(key: str, endpoint: str) -> tuple[str, Mapping[str, Any] | None]:
            try:
                value = await peer.request("GET", endpoint)
                return key, value if isinstance(value, Mapping) else None
            except (TelemacoConnectionError, TelemacoProtocolError):
                return key, None

        peer_resources = {
            key: value
            for key, value in await asyncio.gather(
                *(read_peer(key, endpoint) for key, endpoint in resources.items())
            )
            if value is not None
        }

        offset = self._peer_player_offset
        for resource in ("metadata", "presets", "inputs"):
            target = combined.setdefault(resource, {})
            source = peer_resources.get(resource, {})
            if not isinstance(target, dict) or not isinstance(source, Mapping):
                continue
            for key, value in source.items():
                if key.startswith("player") and key.removeprefix("player").isdigit():
                    local_id = int(key.removeprefix("player"))
                    target[f"player{offset + local_id}"] = value

        target_hostnames = combined.setdefault("hostnames", {})
        peer_hostnames = peer_resources.get("hostnames", {})
        if isinstance(target_hostnames, dict) and isinstance(peer_hostnames, Mapping):
            target_inputs = target_hostnames.setdefault("inputs", {})
            peer_inputs = peer_hostnames.get("inputs", {})
            if isinstance(target_inputs, dict) and isinstance(peer_inputs, Mapping):
                for key, value in peer_inputs.items():
                    if key.startswith("player") and key.removeprefix("player").isdigit():
                        local_id = int(key.removeprefix("player"))
                        target_inputs[f"player{offset + local_id}"] = value

    async def _async_player_command_target(
        self,
        player: Any,
    ) -> tuple[TelemacoApi, int]:
        """Return the correct device and local player number."""
        player_id = int(player)
        if player_id <= self._peer_player_offset or self._peer_api is None:
            return self, player_id
        return self._peer_api, player_id - self._peer_player_offset

    async def async_send_command(
        self, command: str, payload: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        """Map Home Assistant actions to documented REST endpoints."""
        player = payload.get("player")
        zone = payload.get("zone")
        if command in {
            "player_play",
            "player_pause",
            "player_stop",
            "player_next",
            "player_previous",
            "player_shuffle",
            "player_repeat",
            "player_preset",
            "player_volume",
            "player_mute",
        }:
            target, local_player = await self._async_player_command_target(player)
            if target is not self:
                forwarded = dict(payload)
                forwarded["player"] = local_player
                return await target.async_send_command(command, forwarded)
        if command == "matrix_route":
            source = str(payload["source"])
            matrix = dict(await self.request("GET", "/api/matrix/get"))
            routes = matrix.get(source)
            if not isinstance(routes, dict):
                raise TelemacoProtocolError(f"Matrix source {source} is missing")
            routes[f"out{zone}"] = bool(payload.get("active"))
            return await self.request(
                "POST",
                "/api/matrix/set",
                matrix,
                authenticated=True,
            )
        if command == "rename_player":
            target, local_player = await self._async_player_command_target(player)
            if target is not self:
                forwarded = dict(payload)
                forwarded["player"] = local_player
                return await target.async_send_command(command, forwarded)
        if command in ("rename_device", "rename_player"):
            hostnames = dict(await self.request("GET", "/api/hostnames/get"))
            if command == "rename_device":
                hostnames["device"] = str(payload["name"])
            else:
                inputs = hostnames.setdefault("inputs", {})
                key = f"player{player}"
                player_data = inputs.setdefault(key, {})
                player_data["name"] = str(payload["name"])
            return await self.request(
                "POST",
                "/api/hostnames/set",
                hostnames,
            )
        if command == "rename_input":
            inputs = dict(await self.request("GET", "/api/input/get"))
            key = str(payload["input"])
            input_data = inputs.get(key)
            if not isinstance(input_data, dict):
                raise TelemacoProtocolError(f"Input {key} is missing")
            input_data["name"] = str(payload["name"])
            return await self.request(
                "POST",
                "/api/input/set",
                inputs,
                authenticated=True,
            )
        if command == "rename_zone":
            outputs = dict(await self.request("GET", "/api/output/get"))
            mono = outputs.get("mono")
            key = f"ch{zone}"
            if not isinstance(mono, dict) or not isinstance(mono.get(key), dict):
                raise TelemacoProtocolError(f"Output {key} is missing")
            mono[key]["name"] = str(payload["name"])
            return await self.request(
                "POST",
                "/api/output/set",
                outputs,
                authenticated=True,
            )
        if command == "zone_source":
            selected = int(player) if player is not None else None
            matrix = dict(await self.request("GET", "/api/matrix/get"))
            for candidate in range(1, 7):
                route = matrix.get(f"player{candidate}")
                if isinstance(route, dict):
                    route[f"out{zone}"] = selected is not None and candidate == selected
            return await self.request(
                "POST",
                "/api/matrix/set",
                matrix,
                authenticated=True,
            )
        if command in ("player_volume", "player_mute"):
            inputs = dict(await self.request("GET", "/api/input/get"))
            player_data = inputs.get(f"player{player}")
            if not isinstance(player_data, dict):
                raise TelemacoProtocolError(f"Player {player} is missing from input data")
            if command == "player_volume":
                player_data["volume"] = max(
                    0,
                    min(100, int(payload.get("volume", 0))),
                )
            else:
                player_data["mute"] = bool(payload.get("mute"))
            return await self.request(
                "POST",
                "/api/input/set",
                inputs,
                authenticated=True,
            )
        routes: dict[str, tuple[str, str]] = {
            "player_play": ("PUT", f"/api/player{player}/play"),
            "player_pause": ("PUT", f"/api/player{player}/pause"),
            "player_stop": ("PUT", f"/api/player{player}/stop"),
            "player_next": ("PUT", f"/api/player{player}/next"),
            "player_previous": ("PUT", f"/api/player{player}/previous"),
            "player_shuffle": ("PUT", f"/api/player{player}/shuffle/toggle"),
            "player_repeat": ("PUT", f"/api/player{player}/loop/toggle"),
            "player_preset": (
                "PUT",
                f"/api/player{player}/presets/play/{payload.get('preset')}",
            ),
            "zone_volume": (
                "POST",
                f"/api/output/mono/ch{zone}/volume/{payload.get('volume')}",
            ),
            "zone_mute": (
                "POST",
                f"/api/output/mono/ch{zone}/mute/{str(bool(payload.get('mute'))).lower()}",
            ),
            "zone_dnd": (
                "POST",
                f"/api/output/mono/ch{zone}/dnd/{str(bool(payload.get('dnd'))).lower()}",
            ),
            "doorbell": (
                "POST",
                f"/api/device/doorbell/play/{payload.get('sound', 0)}",
            ),
        }
        if command not in routes:
            raise TelemacoProtocolError(f"Command {command} needs a documented REST request body")
        method, endpoint = routes[command]
        return await self.request(method, endpoint, authenticated=True)
