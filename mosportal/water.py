import logging
from datetime import datetime
from .error import Error

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class Water:
    def __init__(self, **kwargs):
        self.__session = kwargs['session']
        self.paycode = kwargs['paycode']
        self.flat = kwargs['flat']
        self.__meter_list = []

    def update(self, meter_list_to_update):
        '''
        Upload values of meters to mosportal
        :param meter_list_to_update:
        :type meter_list_to_update: dict
        :return:
        '''
        logger.debug('Meter list to update %s' % meter_list_to_update)
        result = []
        for item in self.meter_list:
            if item.meter_id not in meter_list_to_update:
                logger.warning('счетчик <%s> отсутствует в настройках hass' % item.meter_id)
                continue
            meter = meter_list_to_update[item.meter_id]
            item.cur_val = round(float(meter['val']), 2)
            item.friendly_name = meter['friendly_name']
            if item.upload_value():
                result.append('Счетчик <%s (%s)> потрачено %s м3'
                              % (item.friendly_name, item.meter_id,
                                 round(float(item.cur_val) - float(item.value), 2)))

        return result

    @property
    def session(self):
        return self.__session.session

    @property
    def meter_list(self):
        if self.__meter_list:
            return self.__meter_list

        try:
            response = self.session.post(
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
            logger.debug(f'Response HTTP Status Code: {response.status_code}, {response.content}')
            self.__meter_list = [Meter.parse(item, self) for item in response.json()['counter']]
            return self.__meter_list
        except BaseException as e:
            raise Error('Ошибка получения данных с моспортала %s' % e)


class Meter:
    def __init__(self, **kwargs):
        self.counterId = kwargs['counterId']
        self.meter_id = kwargs['meter_id']
        self.water = kwargs['water']
        self.value = kwargs['value']
        self.update_date = kwargs['update_date']
        self.friendly_name = kwargs.get('friendly_name', None)
        self.cur_val = kwargs.get('cur_val', None)
        self.period = datetime.now().strftime('%Y-%m-%d')

    @classmethod
    def parse(cls, rj, water):
        value, update_date = cls.__get_current_val(rj['indications'])
        return cls(
            counterId=rj['counterId'],
            meter_id=rj['num'][1:],
            value=value,
            update_date=update_date,
            water=water
        )

    @staticmethod
    def __get_current_val(indicator):
        if type(indicator) is list:
            obj = max(indicator, key=lambda x: float(x['indication']))
            return float(obj['indication']),datetime.strptime(obj['period'][:-6], '%Y-%m-%d')
        else:
            return float(indicator['indication']), datetime.strptime(indicator['period'][:-6], '%Y-%m-%d')

    @property
    def session(self):
        return self.water.session

    def upload_value(self):
        """
        Обновление значения счетчика в Моспортале
        :return:
        """
        try:
            logger.debug('пытаемся передать данные: счетчик=<%s>; значние=<%s>' % (self.meter_id, self.cur_val))

            response = self.session.post(
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
            rj = response.json()
        except BaseException as e:
            raise Error('ошибка вызова обновления %s' % e)

        if response.status_code == 200 and 'code' in rj and rj['code'] == 0:
            logger.debug('запрос успешно выполнен %s set value: %s' % (self.meter_id, self.cur_val))
            return True
        else:
            logger.error('Счетчик <%s (%s)>: %s' % (self.friendly_name, self.meter_id, rj.get('error', rj)))
            return False
