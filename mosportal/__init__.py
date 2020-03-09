import logging
from .epd import get_epd
from .water import Water
from .auth import Session
from .error import Error
import asyncio

from homeassistant.core import callback

logger = logging.getLogger(__name__)

DOMAIN = "mosportal"


@asyncio.coroutine
def async_setup(hass, config):
    broker = hass.components.mqtt
    hass.components.epd = False

    hass.data[DOMAIN] = {'water': Water(**config[DOMAIN], session=Session(**config[DOMAIN]))}

    @callback
    def epd_wrap(call):
        topic_out = config[DOMAIN]['epd'].get('topic_out', None)
        if not topic_out:
            logger.error('Для получения ЕПД нужно указать канал mqtt для сохранения результата')
            return
        if hass.components.epd:
            logger.warning('может быть запущен только один инстанс получения epd.')
            return
        try:
            hass.components.epd = True

            get_epd(topic_out, broker=broker,
                    auth=Session(**config[DOMAIN]),
                    **call.data, **config[DOMAIN]
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
        try:
            res = hass.data[DOMAIN]['water'].update(
                {
                    str(item['meter_id']):
                        {
                            'val': hass.states.get(item['name']).state,
                            'friendly_name': hass.states.get(item['name']).attributes['friendly_name']
                        }
                    for item in config[DOMAIN]['water']['meters']
                }
            )
            topic_out = config[DOMAIN]['water'].get('topic_out', None)
            if res and topic_out:
                broker.publish(topic_out, 'Показания успешно переданы в моспортал!\n    %s' % ';\n   '.join(res))
        except Error as e:
            logger.error('ошибка передачи данных в моспортал: %s' % e)
        except BaseException:
            logger.exception('ошибка передачи данных в моспортал')

    hass.services.async_register(DOMAIN, 'get_epd', epd_wrap)
    hass.services.async_register(DOMAIN, 'publish_water_usage', publish_water_usage)

    return True
