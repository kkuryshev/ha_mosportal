import logging
import json
from mosportal import *
from .const import *
import async_timeout
from datetime import datetime
import voluptuous as vol
from homeassistant.core import callback, HomeAssistant
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import async_load_platform
import base64
from os.path import join, dirname, abspath
import pkg_resources

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Required(CONF_PAYCODE): cv.string,
                vol.Required(CONF_FLAT): cv.string
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, base_config: dict):
    _LOGGER.info(f'Используется версия модуля mosportal: {pkg_resources.get_distribution("mosportal").version}')
    config = base_config[DOMAIN]
    _LOGGER.debug("настройка компонента моспортал")
    client = PortalWrap(
        hass,
        Session(
            config[CONF_USERNAME],
            config[CONF_PASSWORD],
            cookie_save_path=join(dirname(abspath(__file__)), '..', '..','.storage')
        ),
        config[CONF_FLAT],
        config[CONF_PAYCODE]
    )

    hass.data[DOMAIN] = client

    meter_list = await hass.async_add_executor_job(
        client.get_meters_list
    )
    if meter_list:
        _LOGGER.debug("счетчики получены")
        hass.async_create_task(
            async_load_platform(
                hass,
                SENSOR_DOMAIN,
                DOMAIN,
                discovered=meter_list,
                hass_config=config,
            )
        )

    async def trigger_get_epd_service(call):
        try:
            month = call.data.get('month', datetime.now().month)
            year = call.data.get('year', datetime.now().year)
            data = call.data.get('data', {})

            await hass.async_add_executor_job(
                client.get_epd_service, month, year, data
            )

        except BaseException as e:
            _LOGGER.exception(f'ошибка постановки задачи {e}')

    async def publish_water_usage(call):
        try:
            if 'meter_list_to_update' not in call.data:
                _LOGGER.error('переданы не корректные данные на вход в сервис')
                return

            meter_list_to_update = {
                item['meter_id']: item for item in call.data['meter_list_to_update']
            }
            await hass.async_add_executor_job(
                client.publish_water_usage, meter_list_to_update
            )

        except BaseException as e:
            _LOGGER.exception(f'ошибка постановки задачи {e}')

    hass.services.async_register(DOMAIN, 'get_epd', trigger_get_epd_service)
    hass.services.async_register(DOMAIN, 'publish_water_usage', publish_water_usage)

    return True


class PortalWrap:
    def __init__(self, hass: HomeAssistant, auth: Session, flat: str, paycode: str):
        self.hass = hass
        self.flat = flat
        self.paycode = paycode
        self.epd = Epd(session=auth, flat=self.flat, paycode=self.paycode)
        self.water = Water(session=auth, flat=self.flat, paycode=self.paycode)

    def get_meters_list(self):
        try:
            _LOGGER.debug("получение списка счетчиков с портала")
            result = {item.meter_id: item for item in self.water.get_meter_list()}
            return result
        except BaseException as e:
            _LOGGER.error(f'данные не могут быть загружены {e}')

    async def fetch_data(self):
        async with async_timeout.timeout(20) as at:
            data = await self.hass.async_add_executor_job(
                self.get_meters_list
            )
        if at.expired:
            _LOGGER.error('таймаут получения данных с портала')
        return data

    def publish_water_usage(self, meter_list_to_update):
        _LOGGER.debug(f'входные данные для передачи на портал: {meter_list_to_update}')

        for item in self.water.get_meter_list():
            msg = {'meter_id': item.meter_id}
            try:
                if item.meter_id not in meter_list_to_update:
                    _LOGGER.warning(f'счетчик {item.meter_id} отсутствует в настройках hass')
                    continue
                meter = meter_list_to_update[item.meter_id]
                item.cur_val = round(float(meter['value']), 2)
                msg['friendly_name'] = item.friendly_name = meter['friendly_name']
                if item.upload_value():
                    msg['usage'] = round(float(item.cur_val) - float(item.value), 2)
                    self.hass.bus.fire(
                        'upload_water_success',
                        msg
                    )
            except BaseException as e:
                if not isinstance(e, WaterException):
                    _LOGGER.error(f'ошибка отправки данных на портал {e}')

                msg['error'] = str(e)
                self.hass.bus.fire(
                    'upload_water_fail',
                    msg
                )

        self.hass.bus.fire(
            'upload_water_finish',
            {}
        )

    def get_epd_service(self, *args):
        _LOGGER.debug(f'входные данные на получение ЕПД: {args}')
        month = int(args[0])
        year = int(args[1])
        data = json.loads(args[2])
        try:
            _LOGGER.debug('вызов сервиса получения epd')
            need_to_pay, content, filename = self.epd.get(year=year, month=month)
            data.update(
                {
                    'msg': '%04d_%02d необходимо оплатить %s' % (year, month, need_to_pay),
                    'content': base64.b64encode(content).decode(),
                    'filename': filename
                }
            )
            self.hass.bus.fire(
                'get_epd_success',
                data
            )
        except BaseException as e:
            data.update({'msg': str(e)})
            if not isinstance(e, EpdNotExist):
                _LOGGER.error(
                    f'ошибка получения данных с портала {e}'
                )
            else:
                _LOGGER.info(
                    f'ошибка получения данных с портала {e}'
                )

            self.hass.bus.fire(
                'get_epd_error',
                data
            )
