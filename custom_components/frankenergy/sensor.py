"""Frank Energy sensors."""

from datetime import datetime, timedelta
import logging
import pytz

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.recorder.models import StatisticData, StatisticMetaData
from homeassistant.components.recorder.util import get_instance
from homeassistant.components.recorder.statistics import (
    async_add_external_statistics,
    get_last_statistics,
)

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
        self._last_reset = None
        self._state_attributes = {}
        self._api = api
        self._icon = "mdi:meter-electric"
        self._consumption_sensor_id =  f"{DOMAIN}:energy_consumption_daily"
        self._consumption_sensor_name =  f"{DOMAIN} energy_consumption_daily"
        self._cost_sensor_id =  f"{DOMAIN}:energy_cost_daily"
        self._cost_sensor_name =  f"{DOMAIN} energy_cost_daily"

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
        return None

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
    def last_reset(self):
        """Return when the total accumulated energy usage was last reset to 0"""
        return self._last_reset

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
        if not response:
          _LOGGER.warning("No sensor data available, skipping processing")
          return    
        await self.process_data(response)

    async def process_data(self, data):
      """Process the hourly energy data."""
      usageData = data.get('usage', [])
      if not usageData:
        _LOGGER.warning("No usage data available, skipping processing")
        return    
      
      _LOGGER.debug(f"usage data: {usageData}")
      running_sum_kw = 0
      running_sum_costNZD = 0

      cost_statistics = []
      kw_statistics = []
      first_start_date = datetime.fromisoformat(usageData[0]['startDate']).astimezone(pytz.utc)

      # Since last_reset doesn't seem to work, fetch the previous sum total to continue from
      previous_consumption_sensor_data = await get_instance(self.hass).async_add_executor_job(
          get_last_statistics, self.hass, 200, self._consumption_sensor_id, True, {"sum"}
      )
      previous_consumption_stats = previous_consumption_sensor_data.get(self._consumption_sensor_id, [])
      
      previous_cost_stats_sensor_data = await get_instance(self.hass).async_add_executor_job(
          get_last_statistics, self.hass, 200, self._cost_sensor_id, True, {"sum"}
      )
      previous_cost_stats =previous_cost_stats_sensor_data.get(self._cost_sensor_id, [])
      
      for stat in previous_consumption_stats:
        statStartDate = datetime.fromtimestamp(stat['start']).astimezone(pytz.utc)
        if statStartDate < first_start_date and stat["sum"] is not None:
            running_sum_kw = stat["sum"]
            break
      for stat in previous_cost_stats:
        statStartDate = datetime.fromtimestamp(stat['start']).astimezone(pytz.utc)
        if statStartDate < first_start_date and stat["sum"] is not None: 
            running_sum_costNZD = stat["sum"]
            break

      _LOGGER.debug(f"previous running sum for consumption: {running_sum_kw}")
      _LOGGER.debug(f"previous running sum for cost: {running_sum_costNZD}")
                  
      for entry in usageData:
          running_sum_kw += entry['kw']
          running_sum_costNZD += entry['costNZD']

          cost_statistics.append(StatisticData({
              "start": datetime.strptime(entry['startDate'], "%Y-%m-%dT%H:%M:%S%z"),
              "state": entry['costNZD'],
              "sum": round(running_sum_costNZD, 2),
          }))

          kw_statistics.append(StatisticData({
              "start": datetime.strptime(entry['startDate'], "%Y-%m-%dT%H:%M:%S%z"),
              "state": entry['kw'],
              "sum": round(running_sum_kw, 2)
          }))

      if kw_statistics:
          kw_metadata = StatisticMetaData(
              has_mean= False,
              has_sum= True,
              name= self._consumption_sensor_name,
              source= DOMAIN,
              statistic_id= self._consumption_sensor_id,
              unit_of_measurement= self._unit_of_measurement,
          )
          _LOGGER.debug(f"kw statistics: {kw_statistics}")
          async_add_external_statistics(self.hass, kw_metadata, kw_statistics)
      else:
          _LOGGER.warning("No daily energy consumption statistics found, skipping update")

      if kw_statistics:
          cost_metadata = StatisticMetaData(
              has_mean= False,
              has_sum= True,
              name= self._cost_sensor_name,
              source= DOMAIN,
              statistic_id= self._cost_sensor_id,
              unit_of_measurement= self._unit_of_measurement,
          )

          _LOGGER.debug(f"Cost statistics: {cost_statistics}")
          async_add_external_statistics(self.hass, cost_metadata, cost_statistics)
      else:
          _LOGGER.warning("No daily energy cost statistics found, skipping update")

