"""Entity Time Zone Sensor."""
from __future__ import annotations

import asyncio
from datetime import datetime, tzinfo
import logging
from typing import cast

from homeassistant.components.sensor import (
    DOMAIN as SENSOR_DOMAIN,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ENTITY_ID
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback, EntityPlatform
from homeassistant.helpers.event import async_track_time_change
from homeassistant.util import slugify
import homeassistant.util.dt as dt_util

from . import get_tz, signal
from .const import ATTR_UTC_OFFSET

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


class ETZSensor(SensorEntity):
    """Base sensor entity."""

    _tz: tzinfo | None

    def __init__(
        self, entry: ConfigEntry, entity_description: SensorEntityDescription
    ) -> None:
        """Initialize sensor entity."""
        self.entity_description = entity_description
        self.entity_description.name = f"{entry.title} {entity_description.key}"
        slug = slugify(entity_description.key)
        self._attr_unique_id = f"{entry.entry_id}-{slug}"
        self._entity_id = entry.data[CONF_ENTITY_ID]
        self.entity_id = f"{SENSOR_DOMAIN}.{self._entity_id.split('.', 1)[1]}_{slug}"

    @callback
    def add_to_platform_start(
        self,
        hass: HomeAssistant,
        platform: EntityPlatform,
        parallel_updates: asyncio.Semaphore | None,
    ) -> None:
        """Start adding an entity to a platform."""
        super().add_to_platform_start(hass, platform, parallel_updates)
        self._tz = get_tz(self.hass, self.hass.states.get(self._entity_id))

        @callback
        def entity_changed(tz: tzinfo | None) -> None:
            """Handle entity change."""
            self._tz = tz
            self.async_schedule_update_ha_state(True)

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                signal(cast(ConfigEntry, self.platform.config_entry)),
                entity_changed,
            )
        )


class EntityTimeZoneSensor(ETZSensor):
    """Entity time zone sensor entity."""

    _attr_should_poll = False

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize entity time zone sensor entity."""
        entity_description = SensorEntityDescription(
            key="Time zone",
            icon="mdi:map-clock",
        )
        super().__init__(entry, entity_description)

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


class EntityLocalTimeSensor(ETZSensor):
    """Entity local time sensor entity."""

    _attr_should_poll = False

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize entity local time sensor entity."""
        entity_description = SensorEntityDescription(
            key="Local Time",
            entity_registry_enabled_default=False,
            icon="mdi:map-clock",
        )
        super().__init__(entry, entity_description)

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
