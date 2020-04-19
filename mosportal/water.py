import logging
import asyncio
import json
from datetime import datetime
from .error import Error

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class Water:
    lock = asyncio.Lock()

    def __init__(self, **kwargs):
        self.hass = kwargs['hass']
        self.__session = kwargs['session']
        self.paycode = kwargs['paycode']
        self.flat = kwargs['flat']
        self.__meter_list = []
        self.__last_update = None

    async def update(self, meter_list_to_update):
        '''
        Upload values of meters to mosportal
        :param meter_list_to_update:
        :type meter_list_to_update: dict
        :return:
        '''
        logger.debug('Meter list to update %s' % meter_list_to_update)

        for item in self.meter_list:
            msg = {'meter_id': item.meter_id}
            try:
                if item.meter_id not in meter_list_to_update:
                    logger.warning(f'счетчик {item.meter_id} отсутствует в настройках hass')
                    continue
                meter = meter_list_to_update[item.meter_id]
                item.cur_val = round(float(meter['val']), 2)
                msg['friendly_name'] = item.friendly_name = meter['friendly_name']
                if await item.upload_value():
                    msg['usage'] = round(float(item.cur_val) - float(item.value), 2)
                    self.hass.bus.fire("upload_water_success", msg)
            except BaseException as e:
                msg['error'] = str(e)
                self.hass.bus.fire("upload_water_fail", msg)

        self.hass.bus.fire("upload_water_finish", {})

    async def get_session(self):
        return await self.__session.get_session()

    async def skip_update(self):
        return self.__last_update and (datetime.now() - self.__last_update).total_seconds() < 30

    async def update_data(self):
        async with Water.lock:
            if self.__meter_list and await self.skip_update():
                return self.__meter_list

            try:
                session = await self.get_session()
                response = await session.post(
                    url="https://www.mos.ru/pgu/common/ajax/index.php",
                    headers={
                        "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
                    },
                    data={
                        "items[paycode]": str(self.paycode),
                        "ajaxModule": "Guis",
                        "ajaxAction": "getCountersInfo",
                        "items[flat]": str(self.flat),
                    },
                )
                logger.debug(f'Response HTTP Status Code: {response.status}')
                body = await response.json()
                self.__meter_list = [Meter.parse(item, self) for item in body['counter']]
                self.__last_update = datetime.now()

                return self.__meter_list
            except BaseException as e:
                raise Error('Ошибка получения данных с моспортала %s' % e)

    @property
    def meter_list(self):
        if self.__meter_list:
            return self.__meter_list

        return self.update_data()


class Meter:
    def __init__(self, **kwargs):
        self.counterId = kwargs['counterId']
        self.meter_id = kwargs['meter_id']
        self.water = kwargs['water']
        self.value = kwargs['value']
        self.checkup = kwargs.get('checkup', None)
        self.update_date = kwargs['update_date']
        self.friendly_name = kwargs.get('friendly_name', None)
        self.cur_val = kwargs.get('cur_val', None)
        self.period = datetime.now().strftime('%Y-%m-%d')
        self.consumption = kwargs.get('consumption', None)
        self.history_list = kwargs.get('history_list', [])

    @classmethod
    def parse(cls, rj, water):
        value, update_date, consumption, history_list = cls.__get_current_val(rj['indications'])
        return cls(
            counterId=rj['counterId'],
            meter_id=rj['num'][1:],
            value=value,
            update_date=update_date,
            checkup=datetime.strptime(rj['checkup'][:-6], '%Y-%m-%d'),
            consumption=consumption,
            history_list=history_list,
            water=water
        )

    @staticmethod
    def __get_current_val(indicator):
        value_list = []
        if type(indicator) is list:
            value_list = indicator
        else:
            value_list.append(indicator)

        consumption = None
        if len(value_list) > 1:
            value_list.sort(key=lambda x: float(x['indication']), reverse=True)
            consumption = round(float(value_list[0]['indication']) - float(value_list[1]['indication']), 2)

        obj = value_list[0]
        return float(obj['indication']), datetime.strptime(obj['period'][:-6], '%Y-%m-%d'), consumption, value_list

    async def upload_value(self):
        """
        Обновление значения счетчика в Моспортале
        :return:
        """
        logger.debug('пытаемся передать данные: счетчик=<%s>; значние=<%s>' % (self.meter_id, self.cur_val))
        session = await self.water.get_session()
        response = await session.post(
            url="https://www.mos.ru/pgu/common/ajax/index.php",
            data={
                "ajaxAction": "addCounterInfo",
                "ajaxModule": "Guis",
                "items[flat]": str(self.water.flat),
                "items[indications][0][period]": self.period,
                "items[indications][0][counterNum]": str(self.counterId),
                "items[paycode]": str(self.water.paycode),
                "items[indications][0][num]": "",
                "items[indications][0][counterVal]": self.cur_val,
            },
        )
        data = await response.text()
        rj = json.loads(data)

        if response.status == 200 and 'code' in rj and rj['code'] == 0:
            logger.debug('запрос успешно выполнен %s set value: %s' % (self.meter_id, self.cur_val))
            return True
        else:
            raise Error('%s'%rj.get('error', rj))
