"""Entity Time Zone Sensor Helpers."""
from __future__ import annotations

from collections.abc import Container, Mapping
from dataclasses import dataclass
from datetime import tzinfo
from enum import Enum, auto
from functools import lru_cache
import logging
import traceback
from typing import Any, cast
from zoneinfo import available_timezones

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
    CONF_ENTITY_ID,
    CONF_TIME_ZONE,
    EVENT_CORE_CONFIG_UPDATE,
    EVENT_STATE_CHANGED,
    STATE_HOME,
    STATE_UNAVAILABLE,
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
from homeassistant.helpers.event import async_track_time_change
from homeassistant.util import dt as dt_util

from .const import DOMAIN, SIG_ENTITY_CHANGED
from .nominatim import init_nominatim

_ALWAYS_DISABLED_ENTITIES = ("address", "country", "diff_country", "diff_time")
_LOGGER = logging.getLogger(__name__)


@dataclass(init=False)
class ETZData:
    """Entity Time Zone integration data."""

    loc_available: bool
    loc_users: dict[str, int]
    tzf: TimezoneFinder
    tzs: set[str]
    tz_users: dict[str, int]
    zones: list[str]


def not_ha_tz(tz: tzinfo | str | None) -> bool:
    """Return if time zone is effectively different than HA's time zone."""
    if not isinstance(tz, tzinfo):
        return False
    n = dt_util.now()
    return n.astimezone(tz).replace(tzinfo=None) != n.replace(tzinfo=None)


def etz_data(hass: HomeAssistant) -> ETZData:
    """Return Entity Time Zone integration data."""
    return cast(ETZData, hass.data[DOMAIN])


def format_exc(exc: Exception) -> str:
    """Format an exception."""
    return "; ".join(s.strip() for s in traceback.format_exception_only(exc))


@lru_cache
def _get_tz_from_loc(tzf: TimezoneFinder, lat: float, lng: float) -> tzinfo | None:
    """Get time zone from a location.

    This must be run in an executor since timezone_at or get_time_zone may do file I/O.
    """
    try:
        if (tz_name := tzf.timezone_at(lat=lat, lng=lng)) is None:
            return None
    except Exception as exc:  # pylint: disable=broad-exception-caught
        _LOGGER.debug(
            "Getting time zone at (%f, %f) resulted in error: %s",
            lat,
            lng,
            format_exc(exc),
        )
        return None
    return dt_util.get_time_zone(tz_name)


async def get_tz(hass: HomeAssistant, state: State | None) -> tzinfo | str | None:
    """Get time zone from entity state."""
    if not state:
        return STATE_UNAVAILABLE
    if state.domain in (PERSON_DOMAIN, DT_DOMAIN) and state.state == STATE_HOME:
        # get_default_time_zone is new in HA 2024.6.
        if hasattr(dt_util, "get_default_time_zone"):
            return dt_util.get_default_time_zone()
        return dt_util.DEFAULT_TIME_ZONE
    lat = state.attributes.get(ATTR_LATITUDE)
    lng = state.attributes.get(ATTR_LONGITUDE)
    if lat is None or lng is None:
        return STATE_UNAVAILABLE
    tz = await hass.async_add_executor_job(
        _get_tz_from_loc, etz_data(hass).tzf, round(lat, 4), round(lng, 4)
    )
    _LOGGER.debug("Time zone cache: %s", _get_tz_from_loc.cache_info())
    return tz


async def init_etz_data(hass: HomeAssistant) -> None:
    """Initialize integration's data."""
    if DOMAIN in hass.data:
        return
    hass.data[DOMAIN] = etzd = ETZData()
    etzd.loc_available = init_nominatim(hass)
    etzd.loc_users = {}
    etzd.tz_users = {}

    def init_tz_data() -> None:
        """Initialize time zone data.

        This must be done in an executor since TimezoneFinder constructor and
        zoneinfo.available_timezones both do file I/O.
        """
        etzd.tzf = TimezoneFinder()
        etzd.tzs = available_timezones()

    await hass.async_add_executor_job(init_tz_data)

    async def update_zones(event: Event | None = None) -> None:
        """Update list of zones to use."""
        # Ignore events that do not contain any data.
        # For some reason, there are two EVENT_CORE_CONFIG_UPDATE events issued at
        # startup, even though the core config has not changed.
        if event and not event.data:
            return

        etzd.zones = [
            state.entity_id
            for state in hass.states.async_all(ZONE_DOMAIN)
            if not_ha_tz(await get_tz(hass, state))
        ]

    @callback
    def zones_filter(event_or_data: Event | Mapping[str, Any]) -> bool:
        """Return if the state changed event is for a zone."""
        # Event filter signature changed after 2024.3.
        try:
            entity_id = event_or_data["entity_id"]  # type: ignore[index]
        except TypeError:
            entity_id = event_or_data.data["entity_id"]  # type: ignore[union-attr]
        return split_entity_id(entity_id)[0] == ZONE_DOMAIN

    await update_zones()
    hass.bus.async_listen(EVENT_CORE_CONFIG_UPDATE, update_zones)
    hass.bus.async_listen(EVENT_STATE_CHANGED, update_zones, zones_filter)


def signal(entry: ConfigEntry) -> str:
    """Return signal name derived from config entry."""
    return f"{SIG_ENTITY_CHANGED}-{entry.entry_id}"


def _enable_entity(key: str, entry_data: Mapping[str, Any]) -> bool:
    """Determine if entity should be enabled by default."""
    if key in _ALWAYS_DISABLED_ENTITIES:
        return False
    static_tz_or_zone = (
        CONF_TIME_ZONE in entry_data
        or split_entity_id(entry_data[CONF_ENTITY_ID])[0] == ZONE_DOMAIN
    )
    if key == "local_time":
        return static_tz_or_zone
    assert key == "time_zone"
    return not static_tz_or_zone


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
        self.entity_description = entity_description
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
        )
        key = entity_description.key
        self._attr_entity_registry_enabled_default = _enable_entity(key, entry.data)
        self._attr_translation_key = key
        self._attr_unique_id = f"{entry.entry_id}-{key}"
        self._sources = sources
        if ETZSource.LOC in sources:
            self._attr_attribution = "Map data from OpenStreetMap"

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
            etzd = etz_data(self.hass)
            if loc_user:
                etzd.loc_users[config_entry.entry_id] += 1
            if tz_user:
                etzd.tz_users[config_entry.entry_id] += 1
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
        etzd = etz_data(self.hass)
        if ETZSource.LOC in self._sources:
            etzd.loc_users[config_entry.entry_id] -= 1
        if ETZSource.TZ in self._sources:
            etzd.tz_users[config_entry.entry_id] -= 1

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
