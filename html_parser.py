from typing import List

from bs4 import BeautifulSoup, element


def get_parser(html: str, parser='lxml') -> BeautifulSoup:
    return BeautifulSoup(html, parser)


def get_href(tag: element.Tag) -> str | None:
    if not tag or tag.name != 'a' or 'href' not in tag.attrs:
        return None
    return tag['href'].strip()


def get_href_first(tags: List[element.Tag]) -> str | None:
    if not tags:
        return None
    return get_href(tags[0])


def get_text(tag: element.Tag) -> str | None:
    if not tag or not tag.text:
        return None
    return tag.text.strip()


def get_text_first(tags: List[element.Tag]) -> str | None:
    if not tags:
        return None
    return get_text(tags[0])


def parse_href(html: str, a_selector: str) -> str | None:
    parser = get_parser(html)
    return get_href_first(parser.select(a_selector))
