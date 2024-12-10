import re


def get_file_extension_name_or_default(url: str, default_value: str = None) -> str | None:
    dot_idx = url.rfind('.')
    if dot_idx == -1:
        return default_value

    ext_name = url[dot_idx:].lower()

    if re.match(r'^\.[a-zA-Z]+$', ext_name):
        return ext_name

    return default_value


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
    print(message)
    exit()
