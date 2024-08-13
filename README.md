# Frank Energy integration for Home Assistant

View your energy usage from Frank Energy (NZ) in homeassistant.

## Data

Imports the last week of hourly energy data & costs from Frank Energy.

## Getting started

You will need to have an existing Frank Energy account.

## Installation

Once installed, simply set-up from the `Devices and services` area.
The first field is the username and the next field is the password for your Frank Energy account.

Add "energy_consumption_daily" into Energy Dashboard for energy reporting.
Then choose "Use an entity tracking the total costs" and select "frankenergy energy_cost_daily" to add the cost statistic.


### HACS (recommended)

1. [Install HACS](https://hacs.xyz/docs/setup/download), if you did not already
2. [![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=brunsy&repository=ha-frankenergy&category=integration)
3. Install the Frank Energy integration
4. Restart Home Assistant

### Manually

Copy all files in the custom*components/frankenergy folder to your Home Assistant folder \_config/custom_components/frankenergy*.

## Known issues

## Future enhancements

Your support is welcomed.

- fix/add labels for user integration config flow

## Acknowledgements

This integration is not supported / endorsed by, nor affiliated with, Frank Energy.
