import logging
from .epd import get_epd
from .water import Water
from .auth import Session
from .error import Error

logger = logging.getLogger(__name__)

DOMAIN = "mosportal"


def setup(hass, config):
    """Setup the MQTT example component."""
    topic_out, water_topic_out = None, None
    if 'epd' in config[DOMAIN]:
        topic_out = config[DOMAIN]['epd']['topic_out']

    if 'water_topic_out' in config[DOMAIN]:
        water_topic_out = config[DOMAIN]['water_topic_out']

    broker = hass.components.mqtt
    hass.components.epd = False

    def epd_wrap(call):
        if hass.components.epd:
            logger.warning('может быть запущен только один инстанс получения epd.')
            return
        try:
            hass.components.epd = True
            get_epd(topic_out=topic_out, broker=broker,
                    auth=Session(**config[DOMAIN]),
                    **call.data, **config[DOMAIN]
                    )
        except Error as e:
            logger.error('ошибка получения epd: %s' % e)
        except BaseException:
            logger.exception('ошибка получения epd')

        hass.components.epd = False

    hass.services.register(DOMAIN, 'get_epd', epd_wrap)

    def publish_water_usage(call):
        """
        Загрузка данных воды на портал
        :param call:
        :return:
        """
        try:
            res = Water(**config[DOMAIN], session=Session(**config[DOMAIN])).update(
                {str(item['meter_id']):
                    {
                        'val': hass.states.get(item['name']).state,
                        'friendly_name': hass.states.get(item['name']).attributes['friendly_name']
                    }
                    for item in config[DOMAIN]['meters']
                }
            )
            if res and water_topic_out:
                broker.publish(water_topic_out, 'Показания успешно переданы в моспортал!\n    %s' % ';\n   '.join(res))
        except Error as e:
            logger.error('ошибка передачи данных в моспортал: %s' % e)
        except BaseException:
            logger.exception('ошибка передачи данных в моспортал')

    # Register our service with Home Assistant.
    hass.services.register(DOMAIN, 'publish_water_usage', publish_water_usage)

    # Return boolean to indicate that initialization was successfully.
    return True
