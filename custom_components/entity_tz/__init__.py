"""Entity Time Zone Sensor."""
from __future__ import annotations

import logging

from async_lru import alru_cache
from geopy.location import Location

from homeassistant.components.device_tracker import DOMAIN as DT_DOMAIN
from homeassistant.components.person import DOMAIN as PERSON_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    CONF_ENTITY_ID,
    CONF_TIME_ZONE,
    STATE_HOME,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import (
    Event,
    EventStateChangedData,
    HomeAssistant,
    State,
    callback,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util

from .const import DOMAIN, LOC_CACHE_PER_CONFIG
from .helpers import etz_data, get_tz, init_etz_data, signal
from .nominatim import get_location

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]
_LOGGER = logging.getLogger(__name__)

_get_location = alru_cache(0)(get_location)


async def async_setup(hass: HomeAssistant, _: ConfigType) -> bool:
    """Set up composite integration."""
    await init_etz_data(hass)
    return True


async def get_loc(hass: HomeAssistant, state: State | None) -> Location | str | None:
    """Get location data from entity state."""
    if state is None:
        return STATE_UNAVAILABLE
    lat = state.attributes.get(ATTR_LATITUDE)
    lng = state.attributes.get(ATTR_LONGITUDE)
    if lat is None or lng is None:
        return STATE_UNAVAILABLE

    location = await _get_location(hass, f"{lat:.4f}, {lng:.4f}")
    _LOGGER.debug("Location cache: %s", _get_location.cache_info())
    return location


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up config entry."""
    etzd = etz_data(hass)
    etzd.loc_users[entry.entry_id] = 0
    etzd.tz_users[entry.entry_id] = 0

    loc_cache_size = len(etzd.loc_users) * LOC_CACHE_PER_CONFIG
    _get_location._LRUCacheWrapper__maxsize = max(  # type: ignore[attr-defined] # noqa: SLF001 # pylint: disable=protected-access
        _get_location._LRUCacheWrapper__maxsize,  # type: ignore[attr-defined] # noqa: SLF001 # pylint: disable=protected-access
        loc_cache_size,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    if (tz_name := entry.data.get(CONF_TIME_ZONE)) is not None:
        tz = await dt_util.async_get_time_zone(tz_name)
        async_dispatcher_send(hass, signal(entry), None, tz)
        return True

    entity_id = entry.data[CONF_ENTITY_ID]

    async def update_from_entity(
        event: Event[EventStateChangedData] | None = None,
    ) -> None:
        """Process input entity state update."""
        if event:
            new_state: State | None = event.data["new_state"]
            old_state: State | None = event.data["old_state"]
        else:
            new_state = hass.states.get(entity_id)
            old_state = None
        if (
            new_state is None
            or old_state is None
            or new_state.domain in (PERSON_DOMAIN, DT_DOMAIN)
            and ((new_state.state == STATE_HOME) ^ (old_state.state == STATE_HOME))
            or new_state.attributes.get(ATTR_LATITUDE)
            != old_state.attributes.get(ATTR_LATITUDE)
            or new_state.attributes.get(ATTR_LONGITUDE)
            != old_state.attributes.get(ATTR_LONGITUDE)
        ):
            if etzd.loc_available and etzd.loc_users[entry.entry_id]:
                entity_loc = await get_loc(hass, new_state)
            else:
                entity_loc = None
            if etzd.tz_users[entry.entry_id]:
                entity_tz = await get_tz(hass, new_state)
            else:
                entity_tz = None
            async_dispatcher_send(hass, signal(entry), entity_loc, entity_tz)

    @callback
    def sensor_state_listener(event: Event[EventStateChangedData]) -> None:
        """Handle input entity state changed event."""
        entry.async_create_background_task(
            hass, update_from_entity(event), "Entity update"
        )

    entry.async_on_unload(
        async_track_state_change_event(hass, entity_id, sensor_state_listener)
    )
    entry.async_create_background_task(
        hass, update_from_entity(), "First entity update"
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    res = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    etzd = etz_data(hass)
    loc_users = etzd.loc_users.pop(entry.entry_id)
    tz_uers = etzd.tz_users.pop(entry.entry_id)
    assert not loc_users
    assert not tz_uers
    return res
