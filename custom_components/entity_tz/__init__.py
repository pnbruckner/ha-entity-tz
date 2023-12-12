"""Entity Time Zone Sensor."""
from __future__ import annotations

from typing import cast

from timezonefinder import TimezoneFinder

from homeassistant.components import zone
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    CONF_ENTITY_ID,
    EVENT_CORE_CONFIG_UPDATE,
    EVENT_STATE_CHANGED,
    Platform,
)
from homeassistant.core import Event, HomeAssistant, State, callback, split_entity_id
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, SIG_ENTITY_CHANGED

PLATFORMS = [Platform.SENSOR]


def signal(entry: ConfigEntry) -> str:
    """Return signal name derived from config entry."""
    return f"{SIG_ENTITY_CHANGED}-{entry.entry_id}"


def get_tz_name(hass: HomeAssistant, state: State | None) -> str | None:
    """Get time zone name from latitude & longitude from state."""
    if not state:
        return None
    lat = state.attributes.get(ATTR_LATITUDE)
    lng = state.attributes.get(ATTR_LONGITUDE)
    if lat is None or lng is None:
        return None
    return cast(str, hass.data[DOMAIN]["tzf"].timezone_at(lat=lat, lng=lng))


async def init_hass_data(hass: HomeAssistant) -> None:
    """Initialize integration's data."""
    if DOMAIN in hass.data:
        return
    hass.data[DOMAIN] = {}

    def create_timefinder() -> None:
        """Create timefinder object."""

        # This must be done in an executor since the timefinder constructor
        # does file I/O.

        hass.data[DOMAIN]["tzf"] = TimezoneFinder()

    await hass.async_add_executor_job(create_timefinder)

    @callback
    def update_zones(_: Event | None = None) -> None:
        """Update list of zones to use."""
        zones = []
        for state in hass.states.async_all(zone.DOMAIN):
            if get_tz_name(hass, state) != hass.config.time_zone:
                zones.append(state.entity_id)
        hass.data[DOMAIN]["zones"] = zones

    @callback
    def zones_filter(event: Event) -> bool:
        """Return if the state changed event is for a zone."""
        return split_entity_id(event.data["entity_id"])[0] == zone.DOMAIN

    update_zones()
    hass.bus.async_listen(EVENT_CORE_CONFIG_UPDATE, update_zones)
    hass.bus.async_listen(EVENT_STATE_CHANGED, update_zones, zones_filter)


async def async_setup(hass: HomeAssistant, _: ConfigType) -> bool:
    """Set up composite integration."""
    await init_hass_data(hass)
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
            async_dispatcher_send(hass, signal(entry), new_state)

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
