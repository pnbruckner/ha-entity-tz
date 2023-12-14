"""Entity Time Zone Sensor Helpers."""
from __future__ import annotations

import asyncio
from datetime import tzinfo
from typing import cast

from timezonefinder import TimezoneFinder

from homeassistant.components.device_tracker import DOMAIN as DT_DOMAIN
from homeassistant.components.person import DOMAIN as PERSON_DOMAIN
from homeassistant.components.zone import DOMAIN as ZONE_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    CONF_ENTITY_ID,
    EVENT_CORE_CONFIG_UPDATE,
    EVENT_STATE_CHANGED,
    STATE_HOME,
)
from homeassistant.core import Event, HomeAssistant, State, callback, split_entity_id
from homeassistant.helpers.device_registry import DeviceEntryType

# Device Info moved to device_registry in 2023.9
try:
    from homeassistant.helpers.device_registry import DeviceInfo
except ImportError:
    from homeassistant.helpers.entity import DeviceInfo  # type: ignore[attr-defined]

from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.helpers.entity_platform import EntityPlatform
from homeassistant.util import dt as dt_util, slugify

from .const import DOMAIN, SIG_ENTITY_CHANGED


def signal(entry: ConfigEntry) -> str:
    """Return signal name derived from config entry."""
    return f"{SIG_ENTITY_CHANGED}-{entry.entry_id}"


def get_tz(hass: HomeAssistant, state: State | None) -> tzinfo | None:
    """Get time zone from latitude & longitude from state."""
    if not state:
        return None
    if state.domain in (PERSON_DOMAIN, DT_DOMAIN) and state.state == STATE_HOME:
        return dt_util.DEFAULT_TIME_ZONE
    lat = state.attributes.get(ATTR_LATITUDE)
    lng = state.attributes.get(ATTR_LONGITUDE)
    if lat is None or lng is None:
        return None
    tz_name = hass.data[DOMAIN]["tzf"].timezone_at(lat=lat, lng=lng)
    if tz_name is None:
        return None
    return dt_util.get_time_zone(tz_name)


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
        for state in hass.states.async_all(ZONE_DOMAIN):
            if get_tz(hass, state) != dt_util.DEFAULT_TIME_ZONE:
                zones.append(state.entity_id)
        hass.data[DOMAIN]["zones"] = zones

    @callback
    def zones_filter(event: Event) -> bool:
        """Return if the state changed event is for a zone."""
        return split_entity_id(event.data["entity_id"])[0] == ZONE_DOMAIN

    update_zones()
    hass.bus.async_listen(EVENT_CORE_CONFIG_UPDATE, update_zones)
    hass.bus.async_listen(EVENT_STATE_CHANGED, update_zones, zones_filter)


class ETZSensor(Entity):
    """Base entity."""

    _attr_should_poll = False
    _tz: tzinfo | None

    def __init__(
        self,
        entry: ConfigEntry,
        entity_description: EntityDescription,
        domain: str,
    ) -> None:
        """Initialize sensor entity."""
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
        )
        self.entity_description = entity_description
        self.entity_description.name = f"{entry.title} {entity_description.key}"
        slug = slugify(entity_description.key)
        self._attr_unique_id = f"{entry.entry_id}-{slug}"
        self._entity_id = entry.data[CONF_ENTITY_ID]
        self.entity_id = f"{domain}.{self._entity_id.split('.', 1)[1]}_{slug}"

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
