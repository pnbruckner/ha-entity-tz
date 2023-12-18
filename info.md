# <img src="https://brands.home-assistant.io/entity_tz/icon.png" alt="Entity Time Zone Sensor" width="50" height="50"/> Entity Time Zone Sensor

Creates several sensors that have information about the time zone in which another entity is located.

Type | Enabled by default | Description
-|-|-
address | no | The address where the entity is located
country | no | The country the entity is in. Includes an attribute with the country code.
different time | no | Is `on` when the local time where entity is locaed is different than Home Assistant's local time
local time | no | The local time where the entity is located. No time zone suffix is included so that the UI doesn't automatically change it back to Home Assistant's local time.
time zone | yes | The name of the time zone where the entity is located
