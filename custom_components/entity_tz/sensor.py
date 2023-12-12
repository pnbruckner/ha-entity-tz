"""Entity Time Zone Sensor."""
from __future__ import annotations

import logging

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_LATITUDE, ATTR_LONGITUDE, CONF_ENTITY_ID
from homeassistant.core import HomeAssistant, State, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import homeassistant.util.dt as dt_util

from .const import ATTR_UTC_OFFSET, DOMAIN, SIG_ENTITY_CHANGED

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    async_add_entities([EntityTimeZoneSensor(entry)], True)


class EntityTimeZoneSensor(SensorEntity):
    """Entity Time Zone Sensor Entity."""

    _attr_icon = "mdi:map-clock"
    _attr_should_poll = False

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize entity time zone sensor entity."""
        self._attr_name = f"{entry.title} Time Zone"
        self._attr_unique_id = entry.entry_id
        self._entity_id = entry.data[CONF_ENTITY_ID]
        self.entity_id = f"{SENSOR_DOMAIN}.{self._entity_id.split('.', 1)[1]}_time_zone"
        self._dispatcher_connected = False

    async def async_update(self) -> None:
        """Update sensor."""
        self._update(self.hass.states.get(self._entity_id))
        if not self._dispatcher_connected:

            @callback
            def entity_changed(new_state: State | None) -> None:
                """Handle entity change."""
                self._update(new_state)
                self.async_write_ha_state()

            self.async_on_remove(
                async_dispatcher_connect(self.hass, SIG_ENTITY_CHANGED, entity_changed)
            )
            self._dispatcher_connected = True

    def _update(self, state: State | None) -> None:
        """Perform state update."""
        _LOGGER.debug("Updating from state of %s: %s", self._entity_id, state)
        self._attr_available = False

        if state is None:
            return
        latitude = state.attributes.get(ATTR_LATITUDE)
        longitude = state.attributes.get(ATTR_LONGITUDE)
        if latitude is None or longitude is None:
            return

        self._attr_available = True
        tz_name = self.hass.data[DOMAIN].timezone_at(lat=latitude, lng=longitude)
        self._attr_native_value = tz_name

        self._attr_extra_state_attributes = {}
        tz = dt_util.get_time_zone(tz_name)
        if not tz:
            return
        offset = dt_util.now().astimezone(tz).utcoffset()
        if offset is None:
            return
        self._attr_extra_state_attributes[ATTR_UTC_OFFSET] = (
            offset.total_seconds() / 3600
        )
