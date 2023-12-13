# <img src="https://brands.home-assistant.io/entity_tz/icon.png" alt="Entity Time Zone Sensor" width="50" height="50"/> Entity Time Zone Sensor

Creates several sensors that have information about the time zone in which another entity is located.

Type | Enabled by default | Description
-|-|-
Diff tz | no | Is `on` when the entity is in a different time zone than Home Assistant's configured time zone
Local time | no | The local time where the entity is located. No time zone suffix is included so that the UI doesn't automatically change it back to Home Assistant's local time.
Time zone | yes | The name of the time zone where the entity is located

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

## Local Time Sensor History

When enabled, the "Local time" sensor will change its state every minute.
This will cause a lot of data to get recorded that really isn't necessary.
It is suggested, therefore, to add the following to your YAML configuration:
```yaml
recorder:
  exclude:
    entity_globs:
      - sensor.*_local_time
```
