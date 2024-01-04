"""Entity Time Zone Sensor."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TIME, CONF_TIME_ZONE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import homeassistant.util.dt as dt_util

from .const import (
    ADDRESS_ICON,
    ATTR_COUNTRY_CODE,
    ATTR_UTC_OFFSET,
    COUNTRY_ICON,
    LOCAL_TIME_ICON,
    TIME_ZONE_ICON,
)
from .helpers import ETZEntity, ETZSource


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    if CONF_TIME_ZONE in entry.data:
        async_add_entities([EntityLocalTimeSensor(entry)])
    else:
        async_add_entities([cls(entry) for cls in _SENSORS])


class EntityAddressSensor(ETZEntity, SensorEntity):
    """Entity address sensor entity."""

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the entity."""
        entity_description = SensorEntityDescription(key="address", icon=ADDRESS_ICON)
        super().__init__(entry, entity_description, (ETZSource.LOC,))

    async def async_update(self) -> None:
        """Update sensor."""
        if not self._sources_valid:
            return

        self._attr_native_value = self._entity_loc.address


class EntityCountrySensor(ETZEntity, SensorEntity):
    """Entity country sensor entity."""

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the entity."""
        entity_description = SensorEntityDescription(key="country", icon=COUNTRY_ICON)
        super().__init__(entry, entity_description, (ETZSource.LOC,))

    async def async_update(self) -> None:
        """Update sensor."""
        self._attr_extra_state_attributes = {ATTR_COUNTRY_CODE: None}
        if not self._sources_valid:
            return

        address = self._entity_loc.raw["address"]
        self._attr_native_value = address["country"]
        self._attr_extra_state_attributes[ATTR_COUNTRY_CODE] = address[
            "country_code"
        ].upper()


class EntityLocalTimeSensor(ETZEntity, SensorEntity):
    """Entity local time sensor entity."""

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the entity."""
        entity_description = SensorEntityDescription(
            key="local_time", icon=LOCAL_TIME_ICON
        )
        super().__init__(entry, entity_description, (ETZSource.TIME, ETZSource.TZ))

    async def async_update(self) -> None:
        """Update sensor."""
        self._attr_extra_state_attributes = {ATTR_TIME: None}
        if not self._sources_valid:
            return

        dt_now = dt_util.now(self._entity_tz)
        value = dt_now.time().isoformat("minutes")
        if value[0] == "0":
            value = value[1:]
        self._attr_native_value = value
        self._attr_extra_state_attributes[ATTR_TIME] = dt_now


class EntityTimeZoneSensor(ETZEntity, SensorEntity):
    """Entity time zone sensor entity."""

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the entity."""
        entity_description = SensorEntityDescription(
            key="time_zone", icon=TIME_ZONE_ICON
        )
        super().__init__(entry, entity_description, (ETZSource.TZ,))

    async def async_update(self) -> None:
        """Update sensor."""
        self._attr_extra_state_attributes = {ATTR_UTC_OFFSET: None}
        if not self._sources_valid:
            return

        self._attr_native_value = str(self._entity_tz)
        if (offset := dt_util.now().astimezone(self._entity_tz).utcoffset()) is None:
            return
        self._attr_extra_state_attributes[ATTR_UTC_OFFSET] = (
            offset.total_seconds() / 3600
        )


_SENSORS = (
    EntityAddressSensor,
    EntityCountrySensor,
    EntityLocalTimeSensor,
    EntityTimeZoneSensor,
)
