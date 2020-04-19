import aiohttp
import asyncio
import logging
from os.path import join, dirname, abspath
import re
from os import path
logger = logging.getLogger(__name__)


#TODO передаелать на сохранение через hass.helpers.storage.Store(STORAGE_VERSION, STORAGE_KEY)
STORAGE_FOLDER = join(dirname(abspath(__file__)), '..','..','.storage')

REDIRECT = 'https://www.mos.ru/api/oauth20/v1/frontend/json/ru/process/enter?redirect=https://www.mos.ru/services/catalog/popular/'


class Session:
    def __init__(self, **kwargs):
        total =  aiohttp.ClientTimeout(total=20)
        self.__session = aiohttp.ClientSession(timeout=total)
        self.login = kwargs['login']
        self.password = kwargs['password']

    @asyncio.coroutine
    async def get_session(self):
        logger.debug('авторизуемся в портале Москвы...')
        try:
            if not await self.authenticated():
                logger.debug('попытка чистой авторизации (без сохраненных куки)...')
                resp = await self.__session.get('https://www.mos.ru/api/acs/v1/login?back_url=https%3A%2F%2Fwww.mos.ru%2F')
                js = re.search(r'<script charset=\"utf-8\" src=\"(.+?)\"><\/script>',str(await resp.text())).group(1)
                resp = await self.__session.get(f'https://login.mos.ru{js}')
                js = re.search(r'COORDS:\"/(.+?)\"',str(await resp.text())).group(1)
                resp = await self.__session.post(f'https://login.mos.ru/{js}')
                resp = await self.__session.post(
                    url="https://login.mos.ru/sps/login/methods/password",
                    headers={
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                        "Accept-Encoding": "gzip, deflate, br",
                        "Connection": "keep-alive",
                        "Referer": "https://login.mos.ru/sps/login/methods/password",
                        "Content-Type": "application/x-www-form-urlencoded",
                        "Host": "login.mos.ru",
                        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.14; rv:65.0) Gecko/20100101 Firefox/65.0",
                        "Accept-Language": "ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3",
                        "Upgrade-Insecure-Requests": "1",
                    },
                    data={
                        "login": self.login,
                        "password": self.password,
                    },
                    allow_redirects = False
                )
                print('a')
                resp = await self.__session.get(
                    resp.headers.get('location'),
                    headers={
                        "sec-fetch-dest": "document",
                        "sec-fetch-mode": "navigate",
                        "sec-fetch-site": "same-site",
                        "sec-fetch-user": "?1",
                        "Upgrade-Insecure-Requests": "1"
                    }
                )
                print('a')
                await self.__save_cookies()
            return self.__session
        except aiohttp.ClientConnectionError as e:
            logger.error(f'ошибка получения сессии {e}')
            raise e

    @asyncio.coroutine
    async def authenticated(self):
        if not await self.__restore_cookies():
            return
        response = await self.__session.get(REDIRECT)
        if response.status != 200:
            return
        if not response.headers.get('x-session-fingerprint',None):
            return

        return True

    async def __save_cookies(self):
        try:
            file = join(STORAGE_FOLDER, '.mosportal_cookie')
            self.__session.cookie_jar.save(file)
        except Exception as e:
            logger.warning(f'не удалось сохранить сессию для портала Москвы {e}')

    async def __restore_cookies(self):
        file = join(STORAGE_FOLDER, '.mosportal_cookie')
        if path.exists(file):
            self.__session.cookie_jar.load(file)
            return True
        logger.debug('куки не сохранены')
