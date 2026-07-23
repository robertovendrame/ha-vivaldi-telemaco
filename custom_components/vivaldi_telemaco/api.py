"""Local REST client for Vivaldi Telemaco."""

from __future__ import annotations

import asyncio
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
    ) -> None:
        scheme = "https" if port == 443 else "http"
        self.base_url = f"{scheme}://{host}:{port}"
        self._session = session
        self._token = token
        self._username = username
        self._password = password
        self._token_expires_at = 0.0
        self._verify_ssl = verify_ssl
        self._timeout = ClientTimeout(total=timeout)

    @property
    def headers(self) -> dict[str, str]:
        """Return authentication headers used by known firmware variants."""
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
            headers["X-Auth-Token"] = self._token
        return headers

    async def _decode(self, response: ClientResponse) -> Mapping[str, Any]:
        if response.status in (401, 403):
            raise TelemacoAuthenticationError("Invalid Telemaco access token")
        if response.status >= 400:
            raise TelemacoProtocolError(f"Telemaco returned HTTP {response.status}")
        try:
            payload = await response.json(content_type=None)
        except (ValueError, TypeError) as err:
            raise TelemacoProtocolError("Telemaco returned a non-JSON response") from err
        if not isinstance(payload, Mapping):
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
    ) -> Mapping[str, Any]:
        """Perform an authenticated request."""
        if authenticated:
            await self.async_ensure_token()
        try:
            async with asyncio.timeout(self._timeout.total):
                response = await self._session.request(
                    method,
                    f"{self.base_url}{endpoint}",
                    headers=self.headers,
                    json=payload,
                    ssl=self._verify_ssl,
                    timeout=self._timeout,
                )
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
        combined: dict[str, Any] = {}
        last_error: Exception | None = None
        for key, endpoint in STATUS_ENDPOINTS.items():
            try:
                combined[key] = dict(await self.request("GET", endpoint))
            except TelemacoAuthenticationError:
                raise
            except (TelemacoConnectionError, TelemacoProtocolError) as err:
                last_error = err
                continue
        if not combined:
            raise TelemacoProtocolError(
                "No documented Telemaco REST endpoint was reachable"
            ) from last_error
        return combined

    async def async_send_command(
        self, command: str, payload: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        """Map Home Assistant actions to documented REST endpoints."""
        player = payload.get("player")
        zone = payload.get("zone")
        if command == "zone_source":
            selected = int(str(payload["source"]).split()[-1])
            matrix = dict(await self.request("GET", "/api/matrix/get"))
            for candidate in range(1, 7):
                route = matrix.get(f"player{candidate}")
                if isinstance(route, dict):
                    route[f"out{zone}"] = candidate == selected
            return await self.request(
                "POST",
                "/api/matrix/set",
                matrix,
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
