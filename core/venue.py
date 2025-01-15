import logging
import os
import re
import threading
import time
from abc import ABC, ABCMeta, abstractmethod
from collections import OrderedDict
from enum import Enum
from typing import Dict, List, Tuple

from . import downloader, html_parser, utils

_Tag = html_parser.Tag


class _DBLPVenueType(Enum):
    CONFERENCE = 'conf'
    JOURNAL = 'journals'


##################################################################
#                       Abstract Class                           #
##################################################################
class _Base(ABC):
    def __init__(self,
                 save_dir: str,
                 sleep_time_per_paper: float = 2,
                 keyword: str = None,
                 proxies: Dict[str, str] = None,
                 **kwargs):
        self.save_dir = save_dir
        if not os.path.exists(self.save_dir):
            os.makedirs(self.save_dir)
        self.sleep_time_per_paper = sleep_time_per_paper
        self.keyword = keyword
        self.proxies = proxies
        self.url = self._get_url()
        self.dblp_url_prefix = 'https://dblp.org/db/'

    def get_paper_list(self) -> List[Tuple[str, str]]:
        if not self.url:
            logging.error('URL is empty!')
            return []

        logging.info(f'downloading {self.url}')
        paper_list_html = downloader.download_html(self.url, proxies=self.proxies)
        if not paper_list_html or not paper_list_html.strip():
            return []

        if self.url.startswith(self.dblp_url_prefix):
            return self._get_paper_list_by_dblp(paper_list_html)

        return self._get_paper_list_by_diy(paper_list_html)

    def process_one(self, paper_info: Tuple[str, str]) -> None:
        paper_title, paper_url = paper_info
        tid = threading.get_native_id()

        # 匹配关键词
        if self.keyword:
            match_result = re.search(self.keyword, paper_title, re.IGNORECASE)
            if not match_result:
                logging.info(f'(tid {tid}) The paper "{paper_title}" does not contain the required keywords!')
                return

        logging.info(f'(tid {tid}) process paper: {paper_title}')

        # 判断URL是否直接是PDF
        if self._paper_url_is_file_url(paper_url):
            logging.info(f'(tid {tid}) downloading paper: {paper_url}')
            self._download_paper(paper_url, paper_title)
        else:
            logging.info(f'(tid {tid}) downloading html: {paper_url}')
            paper_html = downloader.download_html(paper_url, proxies=self.proxies)
            if paper_html is None:
                return

            paper_file_url = self._get_paper_file_url(paper_html)
            if paper_file_url is None:
                return
            logging.info(f'(tid {tid}) downloading paper: {paper_file_url}')
            self._download_paper(utils.get_absolute_url(paper_url, paper_file_url), paper_title)

            paper_slides_url = self._get_slides_file_url(paper_html)
            if paper_slides_url:
                logging.info(f'(tid {tid}) downloading slides: {paper_slides_url}')
                self._download_slides(utils.get_absolute_url(paper_url, paper_slides_url), paper_title)

        # 如果sleep_time_per_paper不为0，下载完成后暂停一段时间
        if self.sleep_time_per_paper:
            time.sleep(self.sleep_time_per_paper)

    @staticmethod
    def _paper_url_is_file_url(paper_url: str) -> bool:
        file_ext_name = '.pdf'
        if paper_url.lower().endswith(file_ext_name):
            return True

        real_url = downloader.get_real_url(paper_url)
        if real_url and real_url.lower().endswith(file_ext_name):
            return True

        return False

    def _get_paper_list_by_dblp(self, html) -> List[Tuple[str, str]]:
        paper_list = []
        logging.info(f'parsing html from dblp!')
        parser = html_parser.get_parser(html)

        venue_type = self._get_dblp_venue_type()
        if venue_type == _DBLPVenueType.CONFERENCE.value:
            paper_list_selector = '.inproceedings'
        else:
            paper_list_selector = '.article'

        paper_entry_list = parser.select(paper_list_selector)
        logging.info(f'number of papers: {len(paper_entry_list)}')

        for paper_entry in paper_entry_list:
            paper_title = html_parser.get_text_first(paper_entry.select('.title'))
            if not paper_title:
                continue

            paper_url = html_parser.get_href_first(paper_entry.select('.drop-down:first-child a'))
            paper_list.append((paper_title, paper_url))
        return paper_list

    def _get_dblp_venue_type(self) -> str | None:
        start = len(self.dblp_url_prefix)

        # The url has been checked in get_paper_list().
        remaining = self.url[start:]
        if not remaining:
            return None

        slash_idx = remaining.find('/')
        if slash_idx == -1:
            return None
        return self.url[start: start + slash_idx]

    def _get_paper_list_by_diy(self, html) -> List[Tuple[str, str]]:
        result_tuple = self._get_paper_title_and_url_list_by_diy(html)
        if not result_tuple:
            logging.error(f'Unable to extract title and URL from the given URL ({self.url}).')
            return []

        paper_title_list, paper_url_list = result_tuple
        if len(paper_title_list) != len(paper_url_list):
            logging.error(f'Number of titles ({len(paper_title_list)}) != number of urls ({len(paper_url_list)}).')
            return []

        paper_list = []
        for title_tag, url_tag in zip(paper_title_list, paper_url_list):
            paper_title = html_parser.get_text(title_tag)
            if not paper_title:
                continue

            link = html_parser.get_href(url_tag)
            if not link:
                continue

            paper_list.append((paper_title, utils.get_absolute_url(self.url, link)))
        return paper_list

    def _get_filename(self, paper_title: str, paper_url: str, name_suffix: str = None) -> str:
        paper_title = re.sub('[/.]+', '', paper_title)
        paper_title = re.sub(r'\W+', '-', paper_title)

        paper_pathname = os.path.join(self.save_dir, paper_title)
        if name_suffix:
            paper_pathname += f'-{name_suffix}'

        _, paper_ext_name = os.path.splitext(paper_url)
        if not paper_ext_name:
            paper_ext_name = '.pdf'
        return paper_pathname + paper_ext_name

    def _download_paper(self, paper_file_url: str, paper_title: str) -> None:
        if not paper_file_url:
            return

        paper_filename = self._get_filename(paper_title, paper_file_url, name_suffix='Paper')
        if not os.path.exists(paper_filename):
            downloader.download_file(paper_file_url, paper_filename, proxies=self.proxies)

    def _download_slides(self, paper_slides_url: str, paper_title: str) -> None:
        if not paper_slides_url:
            return

        slides_filename = self._get_filename(paper_title, paper_slides_url, name_suffix='Slides')
        if not os.path.exists(slides_filename):
            downloader.download_file(paper_slides_url, slides_filename, proxies=self.proxies)

    @abstractmethod
    def _get_url(self) -> str | None:
        pass

    @abstractmethod
    def _get_paper_title_and_url_list_by_diy(self, html) -> Tuple[List[_Tag], List[_Tag]] | None:
        pass

    @abstractmethod
    def _get_paper_file_url(self, html: str) -> str:
        pass

    @abstractmethod
    def _get_slides_file_url(self, html: str) -> str:
        pass


class _Conference(_Base, metaclass=ABCMeta):
    def __init__(self,
                 year: int,
                 save_dir: str,
                 **kwargs):
        self.year = year
        super().__init__(save_dir, **kwargs)


class _Journal(_Base, metaclass=ABCMeta):
    def __init__(self,
                 volume: int,
                 save_dir: str,
                 **kwargs):
        self.volume = volume
        super().__init__(save_dir, **kwargs)


class _MultiConference(_Conference, metaclass=ABCMeta):
    def __init__(self,
                 venue_name: str,
                 year: int,
                 save_dir: str,
                 **kwargs):
        self.venue_name = venue_name
        super().__init__(year, save_dir, **kwargs)


##################################################################
#                           Conference                           #
##################################################################

class USENIX(_MultiConference):
    def _get_url(self) -> str | None:
        if self.venue_name == 'atc':
            self.venue_name = 'usenix'

        available_confs = ['fast', 'osdi', 'usenix', 'nsdi', 'uss']
        if self.venue_name not in available_confs:
            logging.error(f'error: unknown confernce {self.venue_name}')
            return None

        if self.venue_name == 'usenix' and 1999 <= self.year <= 2006:
            suffix = 'g'
        else:
            suffix = ''

        return f'https://dblp.org/db/conf/{self.venue_name}/{self.venue_name}{self.year}{suffix}.html'

    def _get_paper_title_and_url_list_by_diy(self, html) -> Tuple[List[_Tag], List[_Tag]] | None:
        pass

    def _get_paper_file_url(self, html: str) -> str:
        return html_parser.try_parse_href(html, '.file a', 'a[href$=".pdf"]')

    def _get_slides_file_url(self, html: str) -> str:
        return html_parser.parse_href(html, '.usenix-schedule-slides a')


class NDSS(_Conference):

    def _get_url(self) -> str | None:
        return f'https://dblp.org/db/conf/ndss/ndss{self.year}.html'

    def _get_paper_title_and_url_list_by_diy(self, html) -> Tuple[List[_Tag], List[_Tag]] | None:
        pass

    def _get_paper_file_url(self, html: str) -> str:
        return html_parser.try_parse_href(html, '.pdf-button', 'a[href$=".pdf"]')

    def _get_slides_file_url(self, html: str) -> str:
        return html_parser.parse_href(html, '.button-slides')


class AAAI(_Conference):
    def _get_url(self) -> str | None:
        return f'https://dblp.org/db/conf/aaai/aaai{self.year}.html'

    def _get_paper_title_and_url_list_by_diy(self, html) -> Tuple[List[_Tag], List[_Tag]] | None:
        pass

    def _get_paper_file_url(self, html: str) -> str:
        return html_parser.parse_href(html, '.pdf')

    def _get_slides_file_url(self, html: str) -> str:
        pass


class IJCAI(_Conference):
    def _get_url(self) -> str | None:
        return f'https://dblp.org/db/conf/ijcai/ijcai{self.year}.html'

    def _get_paper_title_and_url_list_by_diy(self, html) -> Tuple[List[_Tag], List[_Tag]] | None:
        pass

    def _get_paper_file_url(self, html: str) -> str:
        return html_parser.parse_href(html, '.btn-download:first-child')

    def _get_slides_file_url(self, html: str) -> str:
        pass


class CVF(_MultiConference):
    def _get_url(self) -> str | None:
        available_confs = ['CVPR', 'ICCV']
        venue_name = self.venue_name.upper()
        if venue_name not in available_confs:
            logging.error(f'error: unknown conference {venue_name}')
            return None

        return f'https://openaccess.thecvf.com/{venue_name}{self.year}?day=all'

    def _get_paper_title_and_url_list_by_diy(self, html) -> Tuple[List[_Tag], List[_Tag]] | None:
        parser = html_parser.get_parser(html)

        paper_title_list = parser.select('.ptitle a')
        paper_url_list = parser.select('.ptitle + dd + dd > a:first-child')

        return paper_title_list, paper_url_list

    def _get_paper_file_url(self, html: str) -> str:
        pass

    def _get_slides_file_url(self, html: str) -> str:
        pass


class ECCV(_Conference):
    def _get_url(self) -> str | None:
        return 'https://www.ecva.net/papers.php'

    def _get_paper_title_and_url_list_by_diy(self, html) -> Tuple[List[_Tag], List[_Tag]] | None:
        start_year = 2018
        if self.year < start_year:
            logging.error(f'{self.__class__.__name__}: Unsupported year: {self.year}, must be [{start_year}, Now]')
            return None

        parser = html_parser.get_parser(html)

        year_idx = -1
        year_tag_list = parser.select('button.accordion')
        for idx, year_tag in enumerate(year_tag_list):
            year = re.search(r'\b(\d{4})\b', year_tag.text.strip())
            if year is None:
                continue

            if int(year.group(1)) == self.year:
                year_idx = idx
                break

        if year_idx == -1:
            return None

        nth_year_paper_list = parser.select('#content')[year_idx]
        paper_title_list = nth_year_paper_list.select('.ptitle a')
        paper_url_list = nth_year_paper_list.select('.ptitle + dd + dd > a')

        return paper_title_list, paper_url_list

    def _get_paper_file_url(self, html: str) -> str:
        pass

    def _get_slides_file_url(self, html: str) -> str:
        pass


class ICLR(_Conference):

    def _get_url(self) -> str | None:
        return f'https://dblp.org/db/conf/iclr/iclr{self.year}.html'

    def _get_paper_title_and_url_list_by_diy(self, html) -> Tuple[List[_Tag], List[_Tag]] | None:
        pass

    def _get_paper_file_url(self, html: str) -> str:
        # arXiv.org
        if self.year <= 2016:
            return html_parser.parse_href(html, '.download-pdf')

        # openreview.net
        return html_parser.parse_href(html, 'a[href^="/pdf"]')

    def _get_slides_file_url(self, html: str) -> str:
        pass


class ICML(_Conference):

    def _get_url(self) -> str | None:
        return f'https://dblp.org/db/conf/icml/icml{self.year}.html'

    def _get_paper_title_and_url_list_by_diy(self, html) -> Tuple[List[_Tag], List[_Tag]] | None:
        pass

    def _get_paper_file_url(self, html: str) -> str:
        # ACM
        if self.year < 2010:
            return ""

        # mlr.press
        if 2010 <= self.year <= 2023:
            return html_parser.parse_href(html, 'a[href$=".pdf"]')

        # openreview.net
        return html_parser.parse_href(html, 'a[href^="/pdf"]')

    def _get_slides_file_url(self, html: str) -> str:
        pass


class NeurIPS(_Conference):

    def _get_url(self) -> str | None:
        if self.year <= 2019:
            venue_name = 'nips'
        else:
            venue_name = 'neurips'

        return f'https://dblp.org/db/conf/nips/{venue_name}{self.year}.html'

    def _get_paper_title_and_url_list_by_diy(self, html) -> Tuple[List[_Tag], List[_Tag]] | None:
        pass

    def _get_paper_file_url(self, html: str) -> str:
        return html_parser.parse_href(html, '.col a[href$=".pdf"]')

    def _get_slides_file_url(self, html: str) -> str:
        pass


class ACL(_MultiConference):
    def _get_url(self) -> str | None:
        available_confs = ['acl', 'emnlp', 'naacl']

        venue_name = self.venue_name
        if venue_name not in available_confs:
            logging.error(f'error: unknown conference {venue_name}')
            return None

        if ((venue_name == 'acl' and self.year >= 2012)
                or (venue_name == 'emnlp' and 2019 <= self.year <= 2021)
                or (venue_name == 'naacl' and 2018 <= self.year <= 2019)):
            suffix = '-1'
        else:
            suffix = ''

        return f'https://dblp.org/db/conf/{venue_name}/{venue_name}{self.year}{suffix}.html'

    def _get_paper_title_and_url_list_by_diy(self, html) -> Tuple[List[_Tag], List[_Tag]] | None:
        pass

    def _get_paper_file_url(self, html: str) -> str:
        return html_parser.parse_href(html, '.acl-paper-link-block .btn-primary')

    def _get_slides_file_url(self, html: str) -> str:
        pass


class RSS(_Conference):

    def _get_url(self) -> str | None:
        return f'https://dblp.org/db/conf/rss/rss{self.year}.html'

    def _get_paper_title_and_url_list_by_diy(self, html) -> Tuple[List[_Tag], List[_Tag]] | None:
        pass

    def _get_paper_file_url(self, html: str) -> str:
        return html_parser.parse_href(html, 'a[href$=".pdf"]')

    def _get_slides_file_url(self, html: str) -> str:
        pass


##################################################################
#                           Journal                              #
##################################################################

class PVLDB(_Journal):

    def _get_url(self) -> str | None:
        return f'https://dblp.org/db/journals/pvldb/pvldb{self.volume}.html'

    def _get_paper_title_and_url_list_by_diy(self, html) -> Tuple[List[_Tag], List[_Tag]] | None:
        pass

    def _get_paper_file_url(self, html: str) -> str:
        pass

    def _get_slides_file_url(self, html: str) -> str:
        pass


class JMLR(_Journal):

    def _get_url(self) -> str | None:
        return f'https://jmlr.org/papers/v{self.volume}/'

    def _get_paper_title_and_url_list_by_diy(self, html) -> Tuple[List[_Tag], List[_Tag]] | None:
        parser = html_parser.get_parser(html)
        paper_title_list = parser.select('dl dt')
        paper_url_list = parser.select('a[href$=".pdf"][target="_blank"]')

        return paper_title_list, paper_url_list

    def _get_paper_file_url(self, html: str) -> str:
        pass

    def _get_slides_file_url(self, html: str) -> str:
        pass


_venue_dict = {
    # Conference
    # Operating System/Storage System
    'fast': {'name': 'FAST', 'publisher': USENIX},
    'osdi': {'name': 'OSDI', 'publisher': USENIX},
    'atc': {'name': 'USENIX ATC', 'publisher': USENIX},

    # Computer Networks
    'nsdi': {'name': 'NSDI', 'publisher': USENIX},

    # Computer security
    'uss': {'name': 'USENIX Security', 'publisher': USENIX},
    'ndss': {'name': 'NDSS', 'publisher': NDSS},

    # Artificial Intelligence
    'aaai': {'name': 'AAAI', 'publisher': AAAI},
    'ijcai': {'name': 'IJCAI', 'publisher': IJCAI},

    # Computer Vision
    'cvpr': {'name': 'CVPR', 'publisher': CVF},
    'iccv': {'name': 'ICCV', 'publisher': CVF},
    'eccv': {'name': 'ECCV', 'publisher': ECCV},

    # Machine Learning
    'iclr': {'name': 'ICLR', 'publisher': ICLR},
    'icml': {'name': 'ICML', 'publisher': ICML},
    'neurips': {'name': 'NeurIPS', 'publisher': NeurIPS},
    # alias for 'neurips'
    'nips': {'name': 'NeurIPS', 'publisher': NeurIPS},

    # Natural Language Processing
    'acl': {'name': 'ACL', 'publisher': ACL},
    'emnlp': {'name': 'EMNLP', 'publisher': ACL},
    'naacl': {'name': 'NAACL', 'publisher': ACL},

    # Robotics
    'rss': {'name': 'RSS', 'publisher': RSS},

    # Journal
    # Databases
    'pvldb': {'name': 'PVLDB(Journal)', 'publisher': PVLDB},

    'jmlr': {'name': 'JMLR(Journal)', 'publisher': JMLR},
}


def get_available_venue_list(lower_case: bool = True) -> List[str]:
    if lower_case:
        venues = _venue_dict.keys()
    else:
        venues = OrderedDict.fromkeys(v['name'] for k, v in _venue_dict.items())
    return list(venues)


def get_available_venues(lower_case: bool = True) -> str:
    return ','.join(get_available_venue_list(lower_case=lower_case))


def get_lower_name(upper_venue_name: str) -> str | None:
    if not upper_venue_name:
        return None

    for k, v in _venue_dict.items():
        if v['name'] == upper_venue_name:
            return k

    return None


def parse_venue(venue: str) -> type | None:
    if not venue:
        return None

    venue = venue.lower()
    if venue not in _venue_dict.keys():
        return None

    return _venue_dict[venue]['publisher']


def is_conference(venue_publisher: type):
    return issubclass(venue_publisher, _Conference)


def is_journal(venue_publisher: type):
    return issubclass(venue_publisher, _Journal)
