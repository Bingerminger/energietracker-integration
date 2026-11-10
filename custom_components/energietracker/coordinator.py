"""One coordinator per Energietracker installation: summary and "To do" together."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import AppTooOld, CannotConnect, EnergietrackerClient, EnergietrackerError, InvalidAuth
from .const import CONF_URL, DOMAIN, UPDATE_INTERVAL
from .logic import min_app_version

_LOGGER = logging.getLogger(__name__)


@dataclass
class EnergietrackerData:
    """What the sensors read."""

    summary: dict[str, Any]
    todo: dict[str, Any]


type EnergietrackerConfigEntry = ConfigEntry[EnergietrackerCoordinator]


def app_too_old_issue_id(entry: ConfigEntry) -> str:
    return f"app_too_old_{entry.entry_id}"


def instance_id(entry: EnergietrackerConfigEntry) -> str:
    """The installation's ``instance_id``: identifier of its devices and prefix of the unique ids."""
    return str(entry.runtime_data.data.summary.get("instance_id") or entry.unique_id or entry.entry_id)


class EnergietrackerCoordinator(DataUpdateCoordinator[EnergietrackerData]):
    """Fetches ``/api/summary`` and ``/api/todo`` every 15 minutes."""

    config_entry: EnergietrackerConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: EnergietrackerConfigEntry, client: EnergietrackerClient) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
            always_update=False,
        )
        self.client = client

    async def _async_update_data(self) -> EnergietrackerData:
        issue_id = app_too_old_issue_id(self.config_entry)
        try:
            summary, todo = await self.client.fetch()
        except InvalidAuth as err:
            raise ConfigEntryAuthFailed(translation_domain=DOMAIN, translation_key="invalid_auth") from err
        except AppTooOld as err:
            # A repair issue instead of empty sensors; it goes away with the update of the app.
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                issue_id,
                is_fixable=False,
                severity=ir.IssueSeverity.ERROR,
                translation_key="app_too_old",
                translation_placeholders={
                    "version": err.version,
                    "minimum": min_app_version(),
                    "url": str(self.config_entry.data.get(CONF_URL, "")),
                },
            )
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="app_too_old",
                translation_placeholders={"version": err.version, "minimum": min_app_version()},
            ) from err
        except CannotConnect as err:
            raise UpdateFailed(translation_domain=DOMAIN, translation_key="cannot_connect") from err
        except EnergietrackerError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="invalid_response",
                translation_placeholders={"detail": str(err) or err.__class__.__name__},
            ) from err
        ir.async_delete_issue(self.hass, DOMAIN, issue_id)
        return EnergietrackerData(summary=summary, todo=todo)
