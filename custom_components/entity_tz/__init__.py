"""Entity Time Zone Sensor."""
from __future__ import annotations

from homeassistant.components.device_tracker import DOMAIN as DT_DOMAIN
from homeassistant.components.person import DOMAIN as PERSON_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    CONF_ENTITY_ID,
    STATE_HOME,
    Platform,
)
from homeassistant.core import Event, HomeAssistant, State, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.typing import ConfigType

from .helpers import get_location, get_tz, init_etz_data, signal

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]


async def async_setup(hass: HomeAssistant, _: ConfigType) -> bool:
    """Set up composite integration."""
    await init_etz_data(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up config entry."""
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entity_id = entry.data[CONF_ENTITY_ID]

    async def update_from_entity(event: Event | None = None) -> None:
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
            async_dispatcher_send(
                hass,
                signal(entry),
                await get_location(hass, new_state),
                get_tz(hass, new_state),
            )

    @callback
    def sensor_state_listener(event: Event) -> None:
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
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
