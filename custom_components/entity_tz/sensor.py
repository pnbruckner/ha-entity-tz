"""Entity Time Zone Sensor."""
from __future__ import annotations

import asyncio
from datetime import datetime
import logging

from homeassistant.components.sensor import (
    DOMAIN as SENSOR_DOMAIN,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback, EntityPlatform
from homeassistant.helpers.event import async_track_time_change
import homeassistant.util.dt as dt_util

from .const import ATTR_UTC_OFFSET, LOCAL_TIME_ICON, TIME_ZONE_ICON
from .helpers import ETZSensor

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    async_add_entities(
        [EntityTimeZoneSensor(entry), EntityLocalTimeSensor(entry)], True
    )


class EntityTimeZoneSensor(ETZSensor, SensorEntity):
    """Entity time zone sensor entity."""

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize entity time zone sensor entity."""
        entity_description = SensorEntityDescription(
            key="time zone",
            icon=TIME_ZONE_ICON,
        )
        super().__init__(entry, entity_description, SENSOR_DOMAIN)

    async def async_update(self) -> None:
        """Update sensor."""
        self._attr_available = False

        if self._tz is None:
            return

        self._attr_available = True
        self._attr_native_value = str(self._tz)

        self._attr_extra_state_attributes = {}
        if (offset := dt_util.now().astimezone(self._tz).utcoffset()) is None:
            return
        self._attr_extra_state_attributes[ATTR_UTC_OFFSET] = (
            offset.total_seconds() / 3600
        )


class EntityLocalTimeSensor(ETZSensor, SensorEntity):
    """Entity local time sensor entity."""

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize entity local time sensor entity."""
        entity_description = SensorEntityDescription(
            key="local time",
            entity_registry_enabled_default=False,
            icon=LOCAL_TIME_ICON,
        )
        super().__init__(entry, entity_description, SENSOR_DOMAIN)

    @callback
    def add_to_platform_start(
        self,
        hass: HomeAssistant,
        platform: EntityPlatform,
        parallel_updates: asyncio.Semaphore | None,
    ) -> None:
        """Start adding an entity to a platform."""
        super().add_to_platform_start(hass, platform, parallel_updates)

        @callback
        def time_changed(_: datetime) -> None:
            """Handle entity change."""
            self.async_schedule_update_ha_state(True)

        self.async_on_remove(async_track_time_change(self.hass, time_changed, second=0))

    async def async_update(self) -> None:
        """Update sensor."""
        self._attr_available = False

        if self._tz is None:
            return

        self._attr_available = True
        state = dt_util.now(self._tz).time().isoformat("minutes")
        if state[0] == "0":
            state = state[1:]
        self._attr_native_value = state
