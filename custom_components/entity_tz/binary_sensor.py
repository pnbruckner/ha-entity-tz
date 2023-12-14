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

from .const import DIFF_TZ_OFF_ICON, DIFF_TZ_ON_ICON
from .helpers import ETZSensor


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the binary sensor platform."""
    async_add_entities([EntityDiffTZSensor(entry)], True)


class EntityDiffTZSensor(ETZSensor, BinarySensorEntity):
    """Entity time zone sensor entity."""

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize entity time zone sensor entity."""
        entity_description = BinarySensorEntityDescription(
            key="diff_tz",
            entity_registry_enabled_default=False,
        )
        super().__init__(entry, entity_description)

    async def async_update(self) -> None:
        """Update sensor."""
        self._attr_available = False
        self._attr_icon = DIFF_TZ_OFF_ICON

        if self._tz is None:
            return

        self._attr_available = True
        self._attr_is_on = self._tz != dt_util.DEFAULT_TIME_ZONE
        if self.is_on:
            self._attr_icon = DIFF_TZ_ON_ICON
