"""Entity Time Zone Binary Sensor."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DIFF_TIME_OFF_ICON, DIFF_TIME_ON_ICON
from .helpers import ETZEntity, ETZSource


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the binary sensor platform."""
    async_add_entities([EntityDiffTZSensor(entry)])


class EntityDiffTZSensor(ETZEntity, BinarySensorEntity):
    """Entity time zone sensor entity."""

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize entity time zone sensor entity."""
        entity_description = BinarySensorEntityDescription(
            key="diff_time",
            entity_registry_enabled_default=False,
        )
        super().__init__(entry, entity_description, (ETZSource.TZ, ETZSource.HA_CFG))

    async def async_update(self) -> None:
        """Update sensor."""
        self._attr_icon = DIFF_TIME_OFF_ICON
        if not self._sources_valid:
            return

        n = dt_util.now()
        self._attr_is_on = n.astimezone(self._entity_tz).replace(
            tzinfo=None
        ) != n.replace(tzinfo=None)
        if self.is_on:
            self._attr_icon = DIFF_TIME_ON_ICON
