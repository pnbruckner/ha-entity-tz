"""Entity Time Zone Sensor."""
from __future__ import annotations

import re

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_LATITUDE, ATTR_LONGITUDE, CONF_ENTITY_ID, Platform
from homeassistant.core import Event, HomeAssistant, State, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .helpers import get_tz, init_hass_data, signal

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]
_OLD_UNIQUE_ID = re.compile(r"[0-9a-f]{32}")


async def async_setup(hass: HomeAssistant, _: ConfigType) -> bool:
    """Set up composite integration."""
    await init_hass_data(hass)

    # From 1.0.0b2 or older: Convert unique_id from entry.entry_id -> entry.entry_id-time_zone
    ent_reg = er.async_get(hass)
    for entity in ent_reg.entities.values():
        if entity.platform != DOMAIN:
            continue
        if _OLD_UNIQUE_ID.fullmatch(entity.unique_id):
            new_unique_id = f"{entity.unique_id}-time_zone"
            ent_reg.async_update_entity(entity.entity_id, new_unique_id=new_unique_id)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up config entry."""

    @callback
    def sensor_state_listener(event: Event) -> None:
        """Process input entity state update."""
        new_state: State | None = event.data["new_state"]
        old_state: State | None = event.data["old_state"]
        if (
            not old_state
            or not new_state
            or new_state.attributes.get(ATTR_LATITUDE)
            != old_state.attributes.get(ATTR_LATITUDE)
            or new_state.attributes.get(ATTR_LONGITUDE)
            != old_state.attributes.get(ATTR_LONGITUDE)
        ):
            async_dispatcher_send(hass, signal(entry), get_tz(hass, new_state))

    entry.async_on_unload(
        async_track_state_change_event(
            hass, entry.data[CONF_ENTITY_ID], sensor_state_listener
        )
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
