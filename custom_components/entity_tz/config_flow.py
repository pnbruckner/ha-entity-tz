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
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    CONF_ENTITY_ID,
    CONF_TIME_ZONE,
)
from homeassistant.core import HomeAssistant, State, split_entity_id
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    TextSelector,
)

from .const import DOMAIN
from .helpers import etz_data, init_etz_data


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
    return split_entity_id(entity_id)[1]


def _list_entity(
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
        return entity_id in etz_data(hass).zones
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
    ) -> ConfigFlowResult:
        """Start user config flow."""
        errors = {}

        if user_input is not None:
            if len(user_input) != 1:
                errors["base"] = "specify_one"
            else:
                if (tz := user_input.get(CONF_TIME_ZONE)) is not None:
                    try:
                        cv.time_zone(tz)
                        title = tz
                    except vol.Invalid:
                        title = tz.title()
                        tz_suffix = title.replace(" ", "_")
                        for tz_name in etz_data(self.hass).tzs:
                            if tz_name.endswith(tz_suffix):
                                user_input[CONF_TIME_ZONE] = tz_name
                                break
                        else:
                            cv.time_zone(tz)
                else:
                    title = _wrapped_entity_config_entry_title(
                        self.hass, user_input[CONF_ENTITY_ID]
                    )
                return self.async_create_entry(title=title, data=user_input)

        await init_etz_data(self.hass)
        used_entity_ids = [
            entry.data[CONF_ENTITY_ID]
            for entry in self.hass.config_entries.async_entries(DOMAIN)
            if CONF_ENTITY_ID in entry.data
        ]
        entity_ids = [
            state.entity_id
            for state in filter(
                partial(_list_entity, self.hass, used_entity_ids),
                self.hass.states.async_all(),
            )
        ]
        data_schema = vol.Schema(
            {
                vol.Optional(CONF_ENTITY_ID): EntitySelector(
                    EntitySelectorConfig(include_entities=entity_ids)
                ),
                vol.Optional(CONF_TIME_ZONE): TextSelector(),
            }
        )
        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )
