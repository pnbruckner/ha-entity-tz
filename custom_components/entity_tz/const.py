"""Constants for Entity Time Zone integration."""
DOMAIN = "entity_tz"

LOC_CACHE_PER_CONFIG = 8

ADDRESS_ICON = "mdi:map-marker"
COUNTRY_ICON = "mdi:web"
DIFF_COUNTRY_OFF_ICON = "mdi:home-city"
DIFF_COUNTRY_ON_ICON = "mdi:city"
DIFF_TIME_OFF_ICON = "mdi:home-clock"
DIFF_TIME_ON_ICON = "mdi:briefcase-clock"
LOCAL_TIME_ICON = "mdi:account-clock"
TIME_ZONE_ICON = "mdi:map-clock"

ATTR_COUNTRY_CODE = "country_code"
ATTR_UTC_OFFSET = "utc_offset"

SIG_ENTITY_CHANGED = f"{DOMAIN}_entity_changed"
