"""Config flow for Illuminance integration."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.const import ATTR_LATITUDE, ATTR_LONGITUDE, CONF_ENTITY_ID
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.schema_config_entry_flow import (
    wrapped_entity_config_entry_title,
)
from homeassistant.helpers.selector import EntitySelector, EntitySelectorConfig

from .const import DOMAIN


class EntityTimeZoneConfigFlow(ConfigFlow, domain=DOMAIN):
    """Entity Time Zone config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Start user config flow."""
        if user_input is not None:
            title = wrapped_entity_config_entry_title(
                self.hass, user_input[CONF_ENTITY_ID]
            )
            return self.async_create_entry(title=title, data=user_input)

        entity_ids = [
            state.entity_id
            for state in self.hass.states.async_all()
            if state.domain != "zone"
            and all(
                attr in state.attributes for attr in (ATTR_LATITUDE, ATTR_LONGITUDE)
            )
        ]
        data_schema = vol.Schema(
            {
                vol.Required(CONF_ENTITY_ID): EntitySelector(
                    EntitySelectorConfig(include_entities=entity_ids)
                ),
            }
        )
        return self.async_show_form(step_id="user", data_schema=data_schema)
