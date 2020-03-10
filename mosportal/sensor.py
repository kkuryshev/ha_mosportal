"""Platform for sensor integration."""
from homeassistant.helpers.entity import Entity
import voluptuous as vol
from datetime import datetime
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME
# from .water import Meter
import homeassistant.helpers.config_validation as cv
import logging

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'mosportal'
DEFAULT_NAME = 'Счетчик воды  (Моспортал)'
CONF_METER_ID = 'meter_id'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Required(CONF_METER_ID): cv.string,
})


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    async_add_entities([WaterSensor(hass, config)], True)


class WaterSensor(Entity):
    """Representation of a Sensor."""

    def __init__(self, hass, config):
        """Initialize the sensor."""
        self._state = None
        self._hass = hass
        self.meter_id = config.get(CONF_METER_ID)
        self._name = config.get(CONF_NAME)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        if self._state:
            return self._state.value

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return 'м³'

    @property
    def device_state_attributes(self):
        if self._state:
            attributes = {
                'update_date': self._state.update_date,
                'counterId': self._state.counterId,
                'meter_id': self._state.meter_id,
                'checkup': self._state.checkup,
                'consumption': self._state.consumption,
                'refresh_date': datetime.now(),
                'history_list': self._state.history_list
            }
            return attributes

    async def async_update(self):
        self._state = await self.async_fetch_state()

    async def async_fetch_state(self):
        for item in self._hass.data[DOMAIN]['water'].meter_list:
            if item.meter_id == self.meter_id:
                return item
