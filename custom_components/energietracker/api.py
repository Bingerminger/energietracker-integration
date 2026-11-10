"""Small client for the Energietracker API (no SDK, aiohttp of Home Assistant)."""

from __future__ import annotations

import asyncio
from typing import Any

import aiohttp

from .const import REQUEST_TIMEOUT
from .logic import app_too_old, auth_headers, endpoint, unwrap


class EnergietrackerError(Exception):
    """Base class."""


class CannotConnect(EnergietrackerError):
    """The app is not reachable."""


class InvalidAuth(EnergietrackerError):
    """Sign-in is on and the read key is missing or wrong (401/403)."""


class InvalidResponse(EnergietrackerError):
    """The answer is not what Energietracker sends (another service at that address?)."""


class AppTooOld(EnergietrackerError):
    """Energietracker is older than 3.9.0 (no ``/api/todo`` yet)."""

    def __init__(self, version: str) -> None:
        super().__init__(version)
        self.version = version


class EnergietrackerClient:
    """Reads ``/api/summary`` and ``/api/todo``."""

    def __init__(self, session: aiohttp.ClientSession, base: str, token: str | None) -> None:
        self._session = session
        self._base = base
        self._headers = {"Accept": "application/json", **auth_headers(token)}

    async def _get(self, name: str) -> dict[str, Any]:
        try:
            async with self._session.get(
                endpoint(self._base, name),
                headers=self._headers,
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
                allow_redirects=False,
            ) as resp:
                if resp.status in (401, 403):
                    raise InvalidAuth
                if resp.status != 200:
                    raise InvalidResponse(f"HTTP {resp.status}")
                payload = await resp.json(content_type=None)
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise CannotConnect(str(err)) from err
        except ValueError as err:
            raise InvalidResponse("no JSON") from err
        try:
            return unwrap(payload)
        except ValueError as err:
            raise InvalidResponse("no data") from err

    async def todo(self) -> dict[str, Any]:
        return await self._get("todo")

    async def summary(self) -> dict[str, Any]:
        return await self._get("summary")

    async def fetch(self) -> tuple[dict[str, Any], dict[str, Any]]:
        """Summary and "To do"; the summary first, it tells the app version.

        ``/api/summary`` exists since Energietracker 3.1.0, ``/api/todo`` since
        3.9.0: an older app raises :class:`AppTooOld` instead of a 404.
        """
        summary = await self.summary()
        if (version := app_too_old(summary)) is not None:
            raise AppTooOld(version)
        return summary, await self.todo()
