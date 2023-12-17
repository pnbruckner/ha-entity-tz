"""Entity Time Zone Sensor Helpers."""
from __future__ import annotations

import asyncio
from collections.abc import Container
from dataclasses import dataclass
from datetime import tzinfo
from enum import Enum, auto
import logging
from typing import Any, cast

from geopy.adapters import AioHTTPAdapter
from geopy.geocoders import Nominatim
from geopy.location import Location
from timezonefinder import TimezoneFinder

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.components.device_tracker import DOMAIN as DT_DOMAIN
from homeassistant.components.person import DOMAIN as PERSON_DOMAIN
from homeassistant.components.zone import DOMAIN as ZONE_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    EVENT_CORE_CONFIG_UPDATE,
    EVENT_STATE_CHANGED,
    STATE_HOME,
    STATE_UNAVAILABLE,
)
from homeassistant.core import Event, HomeAssistant, State, callback, split_entity_id
from homeassistant.helpers.aiohttp_client import (
    SERVER_SOFTWARE,
    async_get_clientsession,
)
from homeassistant.helpers.device_registry import DeviceEntryType

# Device Info moved to device_registry in 2023.9
try:
    from homeassistant.helpers.device_registry import DeviceInfo
except ImportError:
    from homeassistant.helpers.entity import DeviceInfo  # type: ignore[attr-defined]

from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.helpers.event import async_track_time_change
from homeassistant.util import dt as dt_util

from .const import DOMAIN, NOM_TIMEOUT, NOM_WAIT, SIG_ENTITY_CHANGED

_LOGGER = logging.getLogger(__name__)


@dataclass(init=False)
class ETZData:
    """Entity Time Zone integration data."""

    nominatim: Nominatim
    loc_users: dict[str, int]
    query_lock: asyncio.Lock
    tzf: TimezoneFinder
    tz_users: dict[str, int]
    zones: list[str]


def etz_data(hass: HomeAssistant) -> ETZData:
    """Return Entity Time Zone integration data."""
    return cast(ETZData, hass.data[DOMAIN])


async def init_etz_data(hass: HomeAssistant) -> None:
    """Initialize integration's data."""
    if DOMAIN in hass.data:
        return
    hass.data[DOMAIN] = ETZData()
    etz_data(hass).loc_users = {}
    etz_data(hass).tz_users = {}

    nominatim = Nominatim(
        user_agent=SERVER_SOFTWARE,
        timeout=NOM_TIMEOUT,
        adapter_factory=lambda proxies, ssl_context: AioHTTPAdapter(
            proxies=proxies, ssl_context=ssl_context
        ),
    )
    nominatim.adapter.__dict__["session"] = async_get_clientsession(hass)
    etz_data(hass).nominatim = nominatim
    etz_data(hass).query_lock = asyncio.Lock()

    def create_timefinder() -> None:
        """Create timefinder object."""

        # This must be done in an executor since the timefinder constructor
        # does file I/O.

        etz_data(hass).tzf = TimezoneFinder()

    await hass.async_add_executor_job(create_timefinder)

    @callback
    def update_zones(_: Event | None = None) -> None:
        """Update list of zones to use."""
        zones = []
        for state in hass.states.async_all(ZONE_DOMAIN):
            if get_tz(hass, state) != dt_util.DEFAULT_TIME_ZONE:
                zones.append(state.entity_id)
        etz_data(hass).zones = zones

    @callback
    def zones_filter(event: Event) -> bool:
        """Return if the state changed event is for a zone."""
        return split_entity_id(event.data["entity_id"])[0] == ZONE_DOMAIN

    update_zones()
    hass.bus.async_listen(EVENT_CORE_CONFIG_UPDATE, update_zones)
    hass.bus.async_listen(EVENT_STATE_CHANGED, update_zones, zones_filter)


def get_tz(hass: HomeAssistant, state: State | None) -> tzinfo | str | None:
    """Get time zone from latitude & longitude from state."""
    if not state:
        return STATE_UNAVAILABLE
    if state.domain in (PERSON_DOMAIN, DT_DOMAIN) and state.state == STATE_HOME:
        return dt_util.DEFAULT_TIME_ZONE
    lat = state.attributes.get(ATTR_LATITUDE)
    lng = state.attributes.get(ATTR_LONGITUDE)
    if lat is None or lng is None:
        return STATE_UNAVAILABLE
    tz_name = etz_data(hass).tzf.timezone_at(lat=lat, lng=lng)
    if tz_name is None:
        return None
    return dt_util.get_time_zone(tz_name)


async def get_location(
    hass: HomeAssistant, state: State | None
) -> Location | str | None:
    """Get address from latitude & longitude."""
    if state is None:
        return STATE_UNAVAILABLE
    lat = state.attributes.get(ATTR_LATITUDE)
    lng = state.attributes.get(ATTR_LONGITUDE)
    if lat is None or lng is None:
        return STATE_UNAVAILABLE

    lock = etz_data(hass).query_lock

    async def limit_rate() -> None:
        """Hold the lock to limit calls to server."""
        await asyncio.sleep(NOM_WAIT)
        lock.release()

    coordinates = f"{lat}, {lng}"
    await lock.acquire()
    try:
        return await etz_data(hass).nominatim.reverse(coordinates)
    except Exception as exc:  # pylint: disable=broad-exception-caught
        _LOGGER.error("While getting address & country code: %s", exc)
        return None
    finally:
        hass.async_create_task(limit_rate())


def signal(entry: ConfigEntry) -> str:
    """Return signal name derived from config entry."""
    return f"{SIG_ENTITY_CHANGED}-{entry.entry_id}"


class ETZSource(Enum):
    """Source of state."""

    HA_CFG = auto()
    TIME = auto()
    TZ = auto()
    LOC = auto()


class ETZEntity(Entity):
    """Base entity."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    _sources: Container[ETZSource]
    _ent_loc: Location | str | None = None
    _ent_tz: tzinfo | str | None = None

    def __init__(
        self,
        entry: ConfigEntry,
        entity_description: EntityDescription,
        sources: Container[ETZSource],
    ) -> None:
        """Initialize sensor entity."""
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
        )
        key = entity_description.key
        entity_description.translation_key = key
        self.entity_description = entity_description
        self._attr_unique_id = f"{entry.entry_id}-{key}"
        self._sources = sources

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        if ETZSource.LOC in self._sources and self._ent_loc == STATE_UNAVAILABLE:
            return False
        if ETZSource.TZ in self._sources and self._ent_tz == STATE_UNAVAILABLE:
            return False
        return True

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        config_entry = cast(ConfigEntry, self.platform.config_entry)

        @callback
        def entity_changed(
            entity_loc: Location | str | None, entity_tz: tzinfo | str | None
        ) -> None:
            """Handle entity change."""
            self._ent_loc = entity_loc
            self._ent_tz = entity_tz
            self.async_schedule_update_ha_state(True)

        loc_user = ETZSource.LOC in self._sources
        tz_user = ETZSource.TZ in self._sources
        if loc_user or tz_user:
            if loc_user:
                etz_data(self.hass).loc_users[config_entry.entry_id] += 1
            if tz_user:
                etz_data(self.hass).tz_users[config_entry.entry_id] += 1
            self.async_on_remove(
                async_dispatcher_connect(
                    self.hass, signal(config_entry), entity_changed
                )
            )

        @callback
        def update(_: Any) -> None:
            """Update sensor."""
            self.async_schedule_update_ha_state(True)

        if ETZSource.HA_CFG in self._sources:
            self.async_on_remove(
                self.hass.bus.async_listen(EVENT_CORE_CONFIG_UPDATE, update)
            )

        if ETZSource.TIME in self._sources:
            self.async_on_remove(async_track_time_change(self.hass, update, second=0))

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        config_entry = cast(ConfigEntry, self.platform.config_entry)
        if ETZSource.LOC in self._sources:
            etz_data(self.hass).loc_users[config_entry.entry_id] -= 1
        if ETZSource.TZ in self._sources:
            etz_data(self.hass).tz_users[config_entry.entry_id] -= 1

    @property
    def _sources_valid(self) -> bool:
        """Check if sources are available and valid."""
        if not self.available:
            return False

        if issubclass(type(self), BinarySensorEntity):
            setattr(self, "_attr_is_on", None)
        else:
            setattr(self, "_attr_native_value", None)

        if ETZSource.LOC in self._sources and not isinstance(self._ent_loc, Location):
            return False
        if ETZSource.TZ in self._sources and not isinstance(self._ent_tz, tzinfo):
            return False

        return True

    @property
    def _entity_loc(self) -> Location:
        """Return entity location."""
        return cast(Location, self._ent_loc)

    @property
    def _entity_tz(self) -> tzinfo:
        """Return entity location."""
        return cast(tzinfo, self._ent_tz)
