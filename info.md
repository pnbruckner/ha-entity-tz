# <img src="https://brands.home-assistant.io/entity_tz/icon.png" alt="Entity Time Zone Sensor" width="50" height="50"/> Entity Time Zone Sensor

Creates sensors that have information about the time zone in which another entity is located, or about a fixed time zone.

Type | Description
-|-
address | The address where the entity is located
country | The country the entity is in. Includes an attribute with the country code.
different country | Is `on` when the country where entity is located is different than Home Assistant's country configuration
different time | Is `on` when the local time where entity is located is different than Home Assistant's local time
local time | The local time where the entity is located. No time zone suffix is included so that the UI doesn't automatically change it back to Home Assistant's local time.
time zone | The name of the time zone where the entity is located

All entities are disabled by default,
exept for the "local time" sensor, which is enabled by default for static time zones and zone entities,
and the "time zone" sensor, which is enabled by default for all other entities.
