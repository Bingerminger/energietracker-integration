"""Config flow: address of the app, optionally a read key."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import AppTooOld, CannotConnect, EnergietrackerClient, InvalidAuth, InvalidResponse
from .const import CONF_TOKEN, CONF_URL, CONF_VERIFY_SSL, DOMAIN
from .logic import clean_token, min_app_version, normalize_url, url_label

EXAMPLE_URL = "http://nas.local:8080"


class EnergietrackerConfigFlow(ConfigFlow, domain=DOMAIN):
    """One entry per Energietracker installation (its ``instance_id``)."""

    VERSION = 1

    async def _check(self, url: str, token: str, verify_ssl: bool) -> tuple[dict[str, Any], dict[str, Any]]:
        session = async_get_clientsession(self.hass, verify_ssl=verify_ssl)
        return await EnergietrackerClient(session, url, token).fetch()

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        # hassfest wants no addresses in translations: the example comes as a placeholder
        placeholders = {"example": EXAMPLE_URL, "version": "", "minimum": min_app_version()}
        if user_input is not None:
            token = clean_token(user_input.get(CONF_TOKEN))
            verify_ssl = bool(user_input.get(CONF_VERIFY_SSL, True))
            try:
                url = normalize_url(user_input[CONF_URL])
                summary, todo = await self._check(url, token, verify_ssl)
            except ValueError:
                errors[CONF_URL] = "invalid_url"
            except InvalidAuth:
                errors[CONF_TOKEN] = "invalid_auth"
            except AppTooOld as err:
                errors["base"] = "app_too_old"
                placeholders["version"] = err.version
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidResponse:
                errors["base"] = "invalid_response"
            else:
                instance = str(todo.get("instance_id") or summary.get("instance_id") or url)
                await self.async_set_unique_id(instance)
                self._abort_if_unique_id_configured(updates={CONF_URL: url})
                return self.async_create_entry(
                    title=f"Energietracker ({url_label(url)})",
                    data={CONF_URL: url, CONF_TOKEN: token, CONF_VERIFY_SSL: verify_ssl},
                )
        defaults = user_input or {}
        schema = vol.Schema({
            vol.Required(CONF_URL, default=defaults.get(CONF_URL, "")): str,
            vol.Optional(CONF_TOKEN, default=""): str,
            vol.Optional(CONF_VERIFY_SSL, default=defaults.get(CONF_VERIFY_SSL, True)): bool,
        })
        return self.async_show_form(
            step_id="user", data_schema=schema, errors=errors, description_placeholders=placeholders
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        """Sign-in was switched on, or the read key was revoked."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        placeholders = {"version": "", "minimum": min_app_version()}
        entry = self._get_reauth_entry()
        if user_input is not None:
            token = clean_token(user_input.get(CONF_TOKEN))
            try:
                await self._check(entry.data[CONF_URL], token, bool(entry.data.get(CONF_VERIFY_SSL, True)))
            except InvalidAuth:
                errors[CONF_TOKEN] = "invalid_auth"
            except AppTooOld as err:
                errors["base"] = "app_too_old"
                placeholders["version"] = err.version
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidResponse:
                errors["base"] = "invalid_response"
            else:
                return self.async_update_reload_and_abort(entry, data_updates={CONF_TOKEN: token})
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_TOKEN): str}),
            errors=errors,
            description_placeholders=placeholders,
        )
