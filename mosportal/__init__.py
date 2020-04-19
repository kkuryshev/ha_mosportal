import logging
from .epd import get_epd
from .water import Water
from .auth import Session
from .error import Error
import asyncio

from homeassistant.core import callback

logger = logging.getLogger(__name__)

DOMAIN = "mosportal"


# TODO добавить описание схемы


@asyncio.coroutine
def async_setup(hass, config):
    broker = hass.components.mqtt
    hass.components.epd = False

    session = Session(**config[DOMAIN])

    hass.data[DOMAIN] = {
        'water': Water(hass=hass,session=session, **config[DOMAIN]),
        'auth': session
    }

    @callback
    def async_trigger_get_epd_service(call):
        topic_out = config[DOMAIN]['epd'].get('topic_out', None)
        if not topic_out:
            logger.error('Для получения ЕПД нужно указать канал mqtt для сохранения результата')
            return
        if hass.components.epd:
            logger.warning('может быть запущен только один инстанс получения epd.')
            return
        try:
            hass.components.epd = True
            hass.loop.create_task(
                get_epd(topic_out, broker=broker,
                        auth=hass.data[DOMAIN]['auth'],
                        **call.data, **config[DOMAIN]
                        )
            )
        except Error as e:
            logger.error('ошибка получения epd: %s' % e)
        except BaseException:
            logger.exception('ошибка получения epd')

        hass.components.epd = False

    @callback
    def publish_water_usage(call):
        """
        Загрузка данных воды на портал
        :param call:
        :return:
        """
        hass.loop.create_task(
            hass.data[DOMAIN]['water'].update(
                {
                    str(item['meter_id']):
                        {
                            'val': hass.states.get(item['name']).state,
                            'friendly_name': hass.states.get(item['name']).attributes['friendly_name']
                        }
                    for item in config[DOMAIN]['water']['meters']
                }
            )
        )

    hass.services.async_register(DOMAIN, 'get_epd', async_trigger_get_epd_service)
    hass.services.async_register(DOMAIN, 'publish_water_usage', publish_water_usage)

    return True
