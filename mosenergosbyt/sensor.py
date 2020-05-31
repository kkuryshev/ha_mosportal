"""Platform for sensor integration."""
from homeassistant.helpers.entity import Entity
from .const import DOMAIN
import logging
from homeassistant.const import CONF_NAME
from datetime import datetime

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    if discovery_info is None:
        return

    client = hass.data[DOMAIN]

    meter_list = discovery_info.items()
    if not meter_list:
        return

    entities = []
    for meter in meter_list:
        sensor = MosenergoSensor(
            client,
            meter[0]
        )
        entities.append(sensor)
    _LOGGER.debug(f'Счетчики мосэнергосбыт добавлены {entities}')

    async_add_entities(entities, update_before_add=True)


class MosenergoSensor(Entity):
    """Representation of a Sensor."""

    def __init__(self, client, meter_id):
        """Initialize the sensor."""
        self.client = client
        self._device_class = 'power'
        self._unit = 'kw'
        self._icon = 'mdi:speedometer'
        self._available = True
        self._name = meter_id
        self._state = None
        self.meter_id = meter_id
        self.update_time = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        if self._state:
            return self._state.last_measure.nm_status

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return 'кв'

    @property
    def unique_id(self) -> str:
        """Return a unique identifier for this entity."""
        return f"mosenergosbyt_{self.name}"

    @property
    def device_state_attributes(self):
        if self._state:
            measure = self._state.last_measure
            attributes = {
                'nn_ls': self._state.nn_ls,
                'nm_provider': self._state.nm_provider,
                'nm_ls_group_full': self._state.nm_ls_group_full,
                'dt_pay': measure.dt_pay,
                'nm_status': measure.nm_status,
                'sm_pay': measure.sm_pay,
                'dt_meter_installation': measure.dt_meter_installation,
                'dt_indication': measure.dt_indication,
                'nm_description_take': measure.nm_description_take,
                'nm_take': measure.nm_take,
                'nm_t1': measure.nm_t1,
                'nm_t2': measure.nm_t2,
                'nm_t3': measure.nm_t3,
                'pr_zone_t1': measure.pr_zone_t1,
                'pr_zone_t2': measure.pr_zone_t2,
                'pr_zone_t3': measure.pr_zone_t3,
                'vl_t1': measure.vl_t1,
                'vl_t2': measure.vl_t2,
                'vl_t3': measure.vl_t3,
                'refresh_date': self.update_time,
                'nn_days': self._state.nn_days,
                'vl_debt': self._state.vl_debt,
                'vl_balance': self._state.vl_balance
            }
            return attributes

    async def async_update(self):
        self._state, self.update_time = await self.async_fetch_state()

    @property
    def should_poll(self):
        """No need to poll. Coordinator notifies entity of updates."""
        return False

    async def async_fetch_state(self):
        try:
            _LOGGER.debug('получение данных с портала по счетчикам')

            meter_list = await self.client.fetch_data()

            if not meter_list:
                return

            for item in meter_list.values():
                if item.nn_ls == self.meter_id:
                    return item, datetime.now()
        except BaseException:
            _LOGGER.exception('ошибка получения состояния счетчиков с портала')
