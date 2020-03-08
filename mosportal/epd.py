import logging
from lxml import html
import time
from .error import Error
from datetime import datetime
import json
import base64

logger = logging.getLogger(__name__)


def get_epd(**kwargs):
    try:
        logger.info('input params: %s' % kwargs)

        topic_out = kwargs['topic_out']
        broker = kwargs['broker']
        auth = kwargs['auth']
        user_id = kwargs.get('user_id', None)
        message_id = kwargs.get('message_id', None)
    except KeyError as e:
        raise Error('входные параметры не корректны', origin=e)

    result = dict(user_id=user_id, message_id=message_id)
    try:
        result = __get_epd_impl(session=auth.session, **kwargs)
        logger.debug('получили ответ %s...' % str(result)[:30])
    except BaseException as e:
        result.update({'message': str(e)})
        logger.error('ошибка получения ЕПД: %s' % e)
        return

    try:
        result.update({'user_id': user_id, 'message_id': message_id})
        st = json.dumps(result)
        logger.info('кладем сообщение с длиной %s в очередь %s' % (len(st), topic_out))
        broker.publish(topic_out, st)
    except BaseException as e:
        logger.error('ошибка отправки данных в mqtt: %s' % e)
        return


def __get_epd_impl(session, month=None, year=None, **kwargs):
    try:
        month = month if month and len(month) else datetime.now().month
        year = year if year and len(year) else datetime.now().year

        response = session.get('https://www.mos.ru/pgu/ru/application/guis/-47/#step_2')
        tree = html.fromstring(response.text)
        form_hash = tree.find('.//input[@name="uniqueFormHash"]').attrib['value']

        time.sleep(5)
        response = session.post(url='https://www.mos.ru/pgu/ru/application/guis/-47/',
                                data={
                                    'action': 'send',
                                    'field[new_epd_month][month]': month,
                                    'field[new_epd_month][year]': year,
                                    'field[new_epd_type]': '1',
                                    'field[new_flat]': kwargs['flat'],
                                    'field[new_payer_code]': kwargs['paycode'],
                                    'form_id': '-47',
                                    'org_id': 'guis',
                                    'send_from_step': '1',
                                    'step': '1',
                                    'uniqueFormHash': form_hash
                                })
        app_id = response.json()['app_id']
        time.sleep(5)
        response = session.post(url='https://www.mos.ru/pgu/ru/application/guis/-47/',
                                data={
                                    'ajaxAction': 'give_data',
                                    'ajaxModule': 'GuisEPD',
                                    'app_id': app_id
                                })
        data_json = response.json()
        data = data_json.get('data', None)
        if not data:
            return {'message': 'данные от мос. портала не получены'}
        requested_data = data.get('requested_data', None)
        if not requested_data:
            logger.info('ошибочный ответ %s' % data_json)
            status_info = data.get('status_info', None)
            if status_info:
                return {'message': '%s.%s' % (
                    (data.get('extra_info', {})).get('value', ''), status_info.get('status_title', ''))}
            else:
                return {'message': '%s' % (str(data))}

        need_to_pay = data_json['data']['requested_data']['total']
        pdf_guid = data_json['data']['files']['file_info']['file_url']

        logger.info('запрашиваем файл ЕПД')
        r = session.get(f'https://report.mos.ru/epd/epd.pdf?file_guid={pdf_guid}', stream=True)

        return {
            'message': '%s.%s необходимо оплатить %s' % (month, year, need_to_pay),
            'content': (base64.b64encode(r.content)).decode(),
            'filename': 'EPD_%04d_%02d.pdf' % (year, month),
            'result': {'code': '0'}
        }
    except BaseException as e:
        logger.exception("ошибка получения данных от мос.поратала")
        return {'result': {'code': '500', 'msg': 'ошибка получения данных %s' % str(e)}}
