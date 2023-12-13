# <img src="https://brands.home-assistant.io/entity_tz/icon.png" alt="Entity Time Zone Sensor" width="50" height="50"/> Entity Time Zone Sensor

Creates several sensors that have information about the time zone in which another entity is located.

Type | Enabled by default | Description
-|-|-
Diff tz | no | Is `on` when the entity is in a different time zone than Home Assistant's configured time zone
Local time | no | The local time where the entity is located. No time zone suffix is included so that the UI doesn't automatically change it back to Home Assistant's local time.
Time zone | yes | The name of the time zone where the entity is located
