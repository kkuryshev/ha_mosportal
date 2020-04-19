"""Platform for sensor integration."""
from homeassistant.helpers.entity import Entity
import voluptuous as vol
from datetime import datetime, timedelta
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv
import logging

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'mosportal'
DEFAULT_NAME = 'Счетчик воды  (Моспортал)'
CONF_METER_ID = 'meter_id'
SCAN_INTERVAL = timedelta(seconds=24*60*60)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Required(CONF_METER_ID): cv.string,
})


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    name = config[CONF_NAME]
    _LOGGER.debug(f'Инициализация сенсора для портала москвы {name}...')
    try:
        async_add_entities([WaterSensor(hass, config)], update_before_add=True)
    except Exception as e:
        _LOGGER.info(f'Сенсор не может быть инициализирован {e}')


class WaterSensor(Entity):
    """Representation of a Sensor."""

    def __init__(self, hass, config):
        """Initialize the sensor."""
        self._state = None
        self._hass = hass
        self.meter_id = config.get(CONF_METER_ID)
        self._name = config.get(CONF_NAME)
        self.update_time = None


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
                'counterId': self._state.counterId,
                'meter_id': self._state.meter_id,
                'checkup': self._state.checkup,
                'consumption': self._state.consumption,
                'refresh_date': self.update_time,
                'history_list': self._state.history_list
            }
            return attributes

    async def async_update(self):
        self._state, self.update_time = await self.async_fetch_state()

    async def async_fetch_state(self):
        try:
            _LOGGER.debug('получение данных с портала по счетчикам')

            await self._hass.data[DOMAIN]['water'].update_data()
            for item in self._hass.data[DOMAIN]['water'].meter_list:
                if item.meter_id == self.meter_id:
                    return item, datetime.now()
        except BaseException:
            _LOGGER.exception('ошибка получения состояния счетчиков с портала')
