# <img src="https://brands.home-assistant.io/entity_tz/icon.png" alt="Entity Time Zone Sensor" width="50" height="50"/> Entity Time Zone Sensor

Creates several sensors that have information about the time zone in which another entity is located.

Type | Enabled by default | Description
-|-|-
address | no | The address where the entity is located
country | no | The country the entity is in. Includes an attribute with the country code.
different time | no | Is `on` when the local time where entity is locaed is different than Home Assistant's local time
local time | no | The local time where the entity is located. No time zone suffix is included so that the UI doesn't automatically change it back to Home Assistant's local time.
time zone | yes | The name of the time zone where the entity is located

## Installation
### With HACS
[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/)

You can use HACS to manage the installation and provide update notifications.

1. Add this repo as a [custom repository](https://hacs.xyz/docs/faq/custom_repositories/):

```text
https://github.com/pnbruckner/ha-entity-tz
```

2. Install the integration using the appropriate button on the HACS Integrations page. Search for "entity time zone".

### Manual

Place a copy of the files from [`custom_components/entity_tz`](custom_components/entity_tz)
in `<config>/custom_components/entity_tz`,
where `<config>` is your Home Assistant configuration directory.

>__NOTE__: When downloading, make sure to use the `Raw` button from each file's page.

### Versions

This custom integration supports HomeAssistant versions 2023.4.0 or newer.

## Sensor History

When enabled, the "local time" sensor will change its state every minute.
Also, when enabled, the "address" sensor can update quite often, especially when the input device is moving.
These will cause a lot of data to get recorded that really isn't useful.

It is suggested, therefore, to add the following to your YAML configuration:
```yaml
recorder:
  exclude:
    entity_globs:
      - sensor.*_address
      - sensor.*_local_time
```
