import requests
import logging
from datetime import datetime
logger = logging.getLogger(__name__)


class Session:
    def __init__(self,**kwargs):
        self.__session = None
        self.__last_update = None
        self.login = kwargs['login']
        self.password = kwargs['password']
    
    @property
    def session(self):
        if self.__session and self.__last_update:
            if (datetime.now() - self.__last_update).total_seconds() < 60:
                return self.__session

        logger.info('авторизуемся в портале москвы')
        try:
            session = requests.session()
            session.get('https://www.mos.ru/api/oauth20/v1/frontend/json/ru/process/enter?redirect=https://www.mos.ru/services/catalog/popular/')
            session.post(
                url="https://login.mos.ru/sps/login/methods/password",
                headers={
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                    "Accept-Encoding": "gzip, deflate, br",
                    "Connection": "keep-alive",
                    "Referer": "https://login.mos.ru/sps/login/methods/password",
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Host": "login.mos.ru",
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.14; rv:65.0) Gecko/20100101 Firefox/65.0",
                    "Content-Length": "75",
                    "Accept-Language": "ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3",
                    "Upgrade-Insecure-Requests": "1",
                },
                data={
                    "login": self.login,
                    "password": self.password,
                },
            )
            self.__last_update = datetime.now()
            self.__session = session
            return self.__session
        except requests.exceptions.RequestException:
            print('HTTP Request failed')