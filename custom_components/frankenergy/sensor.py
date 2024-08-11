"""Frank Energy sensors."""

from datetime import datetime, timedelta
import logging

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.recorder.models import StatisticData, StatisticMetaData
from homeassistant.components.recorder.statistics import async_add_external_statistics

from .const import DOMAIN, SENSOR_NAME

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(hours=1)

async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback, discovery_info=None
):
    """Set up the Frank Energy sensor platform."""

    if "api" not in hass.data[DOMAIN]:
        _LOGGER.error("API instance not found in config entry data.")
        return False

    api = hass.data[DOMAIN]["api"]
    async_add_entities([FrankEnergyUsageSensor(SENSOR_NAME, api)], True)

class FrankEnergyUsageSensor(SensorEntity):
    """Define Frank Energy Usage sensor."""

    def __init__(self, name, api):
        """Initialize Frank Energy Usage sensor."""
        self._name = name
        self._icon = "mdi:meter-electric"
        self._state = None
        self._unit_of_measurement = "kWh"
        self._unique_id = DOMAIN
        self._device_class = "energy"
        self._state_class = "total"
        self._state_attributes = {}
        self._api = api
        self._icon = "mdi:meter-electric"

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._icon

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the sensor."""
        return self._state_attributes

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    @property
    def state_class(self):
        """Return the state class."""
        return self._state_class

    @property
    def device_class(self):
        """Return the device class."""
        return self._device_class

    @property
    def unique_id(self):
        """Return the unique id."""
        return self._unique_id

    async def async_update(self):
        """Update the sensor data."""
        _LOGGER.debug("Beginning sensor update")
        response = await self._api.get_data()
        await self.process_data(response)

    async def process_data(self, data):
      """Process the hourly energy data."""
      parsed_data = data
      _LOGGER.debug(f"Parsed data: {parsed_data}")
      running_sum_kw = 0
      running_sum_costNZD = 0

      cost_statistics = []
      kw_statistics = []

      for entry in data['usage']:
          running_sum_kw += entry['kw']
          running_sum_costNZD += entry['costNZD']

          cost_statistics.append(StatisticData({
              "start": datetime.strptime(entry['startDate'], "%Y-%m-%dT%H:%M:%S%z"),
              "sum": round(running_sum_costNZD, 2),
          }))

          kw_statistics.append(StatisticData({
              "start": datetime.strptime(entry['startDate'], "%Y-%m-%dT%H:%M:%S%z"),
              "sum": round(running_sum_kw, 2)
          }))

      sensor_type = "energy_consumption_daily"
      if kw_statistics:
          kw_metadata = StatisticMetaData(
              has_mean= False,
              has_sum= True,
              name= f"{DOMAIN} {sensor_type}",
                source= DOMAIN,
                statistic_id= f"{DOMAIN}:{sensor_type}",
                unit_of_measurement= self._unit_of_measurement,
          )
          _LOGGER.debug(f"kw statistics: {kw_statistics}")
          async_add_external_statistics(self.hass, kw_metadata, kw_statistics)
      else:
          _LOGGER.warning("No daily energy consumption statistics found, skipping update")

      sensor_type = "energy_cost_daily"
      if kw_statistics:
          cost_metadata = StatisticMetaData(
              has_mean= False,
              has_sum= True,
              name= f"{DOMAIN} {sensor_type}",
                source= DOMAIN,
                statistic_id= f"{DOMAIN}:{sensor_type}",
                unit_of_measurement= self._unit_of_measurement,
          )

          _LOGGER.debug(f"Cost statistics: {cost_statistics}")
          async_add_external_statistics(self.hass, cost_metadata, cost_statistics)
      else:
          _LOGGER.warning("No daily energy cost statistics found, skipping update")

