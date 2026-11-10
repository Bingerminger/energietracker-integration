"""Energietracker for Home Assistant: "To do", balance, consumption and forecast as sensors.

Reads ``/api/summary`` and ``/api/todo`` of a self-hosted Energietracker
(https://github.com/Bingerminger/energietracker). Nothing leaves the home
network unless the address you enter lies outside it.
"""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import EnergietrackerClient
from .const import CONF_TOKEN, CONF_URL, CONF_VERIFY_SSL, DOMAIN
from .coordinator import EnergietrackerConfigEntry, EnergietrackerCoordinator, app_too_old_issue_id, instance_id
from .logic import all_meters

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: EnergietrackerConfigEntry) -> bool:
    session = async_get_clientsession(hass, verify_ssl=bool(entry.data.get(CONF_VERIFY_SSL, True)))
    client = EnergietrackerClient(session, entry.data[CONF_URL], entry.data.get(CONF_TOKEN))
    coordinator = EnergietrackerCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: EnergietrackerConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: EnergietrackerConfigEntry, device_entry: dr.DeviceEntry
) -> bool:
    """A meter deleted in Energietracker can be deleted in Home Assistant, a current one cannot."""
    instance = instance_id(entry)
    current = {instance} | {f"{instance}_{m['key']}" for m in all_meters(entry.runtime_data.data.summary)}
    return not any(domain == DOMAIN and ident in current for domain, ident in device_entry.identifiers)


async def async_remove_entry(hass: HomeAssistant, entry: EnergietrackerConfigEntry) -> None:
    """The repair issue "Energietracker too old" goes with the entry."""
    ir.async_delete_issue(hass, DOMAIN, app_too_old_issue_id(entry))
