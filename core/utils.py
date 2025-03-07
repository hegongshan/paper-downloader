import os
import re
import sys

from enum import Enum


class _CLIColor(Enum):
    RESET = '\033[0m'
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'


def get_root_url(url: str) -> str:
    protocols = ['https://', 'http://']
    end = 0
    for protocol in protocols:
        idx = len(protocol)
        if url[:idx] == protocol:
            end = idx + url[idx:].find('/')
            break
    return url[:end]


def get_prefix_url(url: str) -> str:
    protocols = ['https://', 'http://']
    end = 0
    for protocol in protocols:
        idx = len(protocol)
        if url[:idx] == protocol:
            end = idx + url[idx:].rfind('/')
            break
    return url[:end]


def get_absolute_url(url: str, relative_url: str) -> str:
    if not relative_url:
        return ''

    if relative_url.startswith('https://') or relative_url.startswith('http://'):
        return relative_url

    if relative_url[0] == '/':
        return get_root_url(url) + relative_url

    return get_prefix_url(url) + '/' + relative_url


def print_and_exit(message: str) -> None:
    print_error(message)
    exit()


def print_error(message: str) -> None:
    error = _CLIColor.RED.value + message + _CLIColor.RESET.value
    print(error)


def print_warning(message: str) -> None:
    warning = _CLIColor.YELLOW.value + message + _CLIColor.RESET.value
    print(warning)


def print_success(message: str) -> None:
    success = _CLIColor.GREEN.value + message + _CLIColor.RESET.value
    print(success)


def get_abs_path(default_dirname, relative_path):
    if hasattr(sys, '_MEIPASS'):
        dirname = sys._MEIPASS
    else:
        dirname = os.path.abspath(default_dirname)
    return os.path.join(dirname, relative_path)
