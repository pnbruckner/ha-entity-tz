"""Config flow for Illuminance integration."""
from __future__ import annotations

from collections.abc import Iterable
from functools import partial
from typing import Any

import voluptuous as vol

from homeassistant.components.device_tracker import DOMAIN as DT_DOMAIN
from homeassistant.components.geo_location import DOMAIN as GL_DOMAIN
from homeassistant.components.person import DOMAIN as PERSON_DOMAIN
from homeassistant.components.zone import DOMAIN as ZONE_DOMAIN
from homeassistant.config_entries import ConfigFlow
from homeassistant.const import ATTR_LATITUDE, ATTR_LONGITUDE, CONF_ENTITY_ID
from homeassistant.core import HomeAssistant, State, split_entity_id
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.selector import EntitySelector, EntitySelectorConfig

from .const import DOMAIN
from .helpers import init_hass_data


def _wrapped_entity_config_entry_title(
    hass: HomeAssistant, entity_id_or_uuid: str
) -> str:
    """Generate title for a config entry wrapping a single entity."""
    registry = er.async_get(hass)
    entity_id = er.async_validate_entity_id(registry, entity_id_or_uuid)
    entry = registry.async_get(entity_id)
    if entry_name := (entry and (entry.name or entry.original_name)):
        return entry_name
    state = hass.states.get(entity_id)
    if state_name := (state and state.name):
        return state_name
    object_id = split_entity_id(entity_id)[1]
    return object_id


def _use_state(
    hass: HomeAssistant, used_entity_ids: Iterable[str], state: State
) -> bool:
    """Determine if state represents an entity that should be listed as an option."""
    if not state:
        return False
    if (entity_id := state.entity_id) in used_entity_ids:
        return False
    if (domain := state.domain) in (PERSON_DOMAIN, DT_DOMAIN):
        return True
    if domain in (ZONE_DOMAIN,):
        return entity_id in hass.data[DOMAIN]["zones"]
    if domain in (GL_DOMAIN,):
        return False
    lat = state.attributes.get(ATTR_LATITUDE)
    lng = state.attributes.get(ATTR_LONGITUDE)
    if lat is None or lng is None:
        return False
    return True


class EntityTimeZoneConfigFlow(ConfigFlow, domain=DOMAIN):
    """Entity Time Zone config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Start user config flow."""
        if user_input is not None:
            title = _wrapped_entity_config_entry_title(
                self.hass, user_input[CONF_ENTITY_ID]
            )
            return self.async_create_entry(title=title, data=user_input)

        await init_hass_data(self.hass)
        used_entity_ids = [
            entry.data[CONF_ENTITY_ID]
            for entry in self.hass.config_entries.async_entries(DOMAIN)
        ]
        entity_ids = [
            state.entity_id
            for state in filter(
                partial(_use_state, self.hass, used_entity_ids),
                self.hass.states.async_all(),
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
