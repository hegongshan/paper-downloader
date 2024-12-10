import logging
import random
from typing import Dict

import requests

_user_agent = [
    # desktop
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/75.0.3770.142 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/70.0.3538.25 Safari/537.36 Core/1.70.3722.400 QQBrowser/10.5.3739.400',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',

    # mobile
    'Mozilla/5.0 (Linux; Android 7.1.1; OPPO R9sk) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/73.0.3683.90 Mobile Safari/537.36 EdgA/42.0.2.3819',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0.1 Mobile/22A3370 Safari/604.1'
]


def _get_headers() -> Dict[str, str]:
    return {
        'User-Agent': random.choice(_user_agent)
    }


def download_html(url: str, proxies: Dict[str, str] = None) -> str | None:
    try:
        if proxies is None:
            r = requests.get(url=url, headers=_get_headers())
        else:
            r = requests.get(url=url, headers=_get_headers(), proxies=proxies)
        r.raise_for_status()
        r.encoding = r.apparent_encoding
        return r.text
    except requests.HTTPError as e:
        logging.error(f'download html: {url}, error: {e}')


def download_file(url: str, filename: str, proxies: Dict[str, str] = None) -> None:
    try:
        if proxies is None:
            r = requests.get(url, headers=_get_headers())
        else:
            r = requests.get(url, headers=_get_headers(), proxies=proxies)
        r.raise_for_status()

        with open(filename, 'wb') as file:
            file.write(r.content)
    except requests.HTTPError as e:
        logging.error(f'download file: url = {url}, filename = {filename}, error: {e}')


def get_real_url(url: str) -> str:
    r = requests.head(url, headers=_get_headers(), allow_redirects=True)
    return r.url
