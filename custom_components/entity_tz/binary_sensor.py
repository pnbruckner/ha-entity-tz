"""Entity Time Zone Binary Sensor."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TIME_ZONE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DIFF_COUNTRY_OFF_ICON,
    DIFF_COUNTRY_ON_ICON,
    DIFF_TIME_OFF_ICON,
    DIFF_TIME_ON_ICON,
)
from .helpers import ETZEntity, ETZSource, not_ha_tz


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the binary sensor platform."""
    if CONF_TIME_ZONE in entry.data:
        return
    async_add_entities([cls(entry) for cls in _SENSORS])


class EntityDiffCountrySensor(ETZEntity, BinarySensorEntity):
    """Entity different country binary sensor entity."""

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the entity."""
        entity_description = BinarySensorEntityDescription(key="diff_country")
        super().__init__(entry, entity_description, (ETZSource.LOC, ETZSource.HA_CFG))

    async def async_update(self) -> None:
        """Update sensor."""
        self._attr_icon = DIFF_COUNTRY_OFF_ICON
        if not self._sources_valid:
            return

        self._attr_is_on = (
            self._entity_loc.raw["address"]["country_code"].upper()
            != self.hass.config.country
        )
        if self.is_on:
            self._attr_icon = DIFF_COUNTRY_ON_ICON


class EntityDiffTZSensor(ETZEntity, BinarySensorEntity):
    """Entity different time zone binary sensor entity."""

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the entity."""
        entity_description = BinarySensorEntityDescription(key="diff_time")
        super().__init__(entry, entity_description, (ETZSource.TZ, ETZSource.HA_CFG))

    async def async_update(self) -> None:
        """Update sensor."""
        self._attr_icon = DIFF_TIME_OFF_ICON
        if not self._sources_valid:
            return

        self._attr_is_on = not_ha_tz(self._entity_tz)
        if self.is_on:
            self._attr_icon = DIFF_TIME_ON_ICON


_SENSORS = (EntityDiffCountrySensor, EntityDiffTZSensor)
