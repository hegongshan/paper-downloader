import logging
import os
import random
import shutil
import sys
import unittest

current_dir = os.path.dirname(os.path.realpath(__file__))
parent_dir = os.path.abspath(os.path.join(current_dir, os.pardir))
sys.path.append(parent_dir)

save_dir_prefix = os.path.join('paper', 'test')
sleep_time_per_paper = 2
full_test = False

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

from core import venue


class Test(unittest.TestCase):
    def _process(self,
                 venue_name,
                 correct_range,
                 error_range=None,
                 is_conf=True):
        save_dir_ = os.path.join(save_dir_prefix, venue_name)

        venue_publisher = venue.parse_venue(venue_name)

        if full_test:
            # 每个年份都要处理
            correct_len = len(correct_range)
            test_range = list(correct_range)
            if error_range:
                test_range += list(error_range)
        else:
            # 随机选择一个年份
            correct_len = 1
            test_range = random.sample(correct_range, 1)
            if error_range:
                test_range += random.sample(error_range, 1)

        for idx, year_or_volume in enumerate(test_range):
            save_dir = os.path.join(save_dir_, str(year_or_volume))

            logging.info(f'Start Test: venue = {venue_name}, year/volume = {year_or_volume}')
            publisher = venue_publisher(save_dir=save_dir,
                                        sleep_time_per_paper=sleep_time_per_paper,
                                        venue_name=venue_name,
                                        year=year_or_volume if is_conf else None,
                                        volume=None if is_conf else year_or_volume,
                                        proxies=None)
            paper_list = publisher.get_paper_list()
            if not paper_list:
                return

            # 随机选择一篇论文
            paper_entry = random.sample(paper_list, 1)[0]
            publisher.process_one(paper_entry)

            count = len(os.listdir(save_dir))
            if idx < correct_len:
                # paper + slides
                self.assertTrue(count >= 1)
            else:
                self.assertTrue(count == 0)
            logging.info(f'Test Done!')

        shutil.rmtree(save_dir_)

    ## venue
    ## conference
    def test_aaai(self):
        self._process(venue_name='aaai',
                      correct_range=list(range(1980, 2024 + 1)))

    def test_ijcai(self):
        self._process(venue_name='ijcai',
                      correct_range=list(range(1969, 2015 + 2, 2)) + list(range(2016, 2024 + 1)))

    def test_cvpr(self):
        self._process(venue_name='cvpr',
                      correct_range=list(range(2013, 2024 + 1)))

    def test_iccv(self):
        self._process(venue_name='iccv',
                      correct_range=list(range(2013, 2024 + 1)))

    def test_eccv(self):
        self._process(venue_name='eccv',
                      correct_range=list(range(2018, 2024 + 2, 2)))

    def test_iclr(self):
        self._process(venue_name='iclr',
                      correct_range=list(range(2013, 2024 + 1)))

    def test_icml(self):
        self._process(venue_name='icml',
                      correct_range=range(2010, 2024 + 1),
                      error_range=range(1980, 2009 + 1))

    def test_nips(self):
        self._process(venue_name='nips',
                      correct_range=range(2010, 2023 + 1))

    def test_acl(self):
        self._process(venue_name='acl',
                      correct_range=range(1979, 2024 + 1))

    def test_emnlp(self):
        self._process(venue_name='emnlp',
                      correct_range=range(1996, 2024 + 1))

    def test_naacl(self):
        self._process(venue_name='naacl',
                      correct_range=[
                          2024, 2022, 2021, 2019, 2018, 2016, 2015, 2013, 2012, 2010,
                          2009, 2007, 2006, 2004, 2003, 2001, 2000])

    def test_nsdi(self):
        self._process(venue_name='nsdi',
                      correct_range=list(range(2004, 2024 + 1)))

    def test_uss(self):
        self._process(venue_name='uss',
                      correct_range=list(range(1998, 2024 + 1)) + [1992, 1993, 1995, 1996])

    def test_ndss(self):
        self._process(venue_name='ndss',
                      correct_range=range(1993, 2024 + 1))

    def test_osdi(self):
        self._process(venue_name='osdi',
                      correct_range=list(range(2002, 2022, 2)) + list(range(2021, 2024 + 1)))

    def test_fast(self):
        self._process(venue_name='fast',
                      correct_range=range(2002, 2024 + 1))

    def test_atc(self):
        self._process(venue_name='atc',
                      correct_range=range(1998, 2024 + 1))

    def test_rss(self):
        self._process(venue_name='rss',
                      correct_range=range(2005, 2024 + 1))

    ## Journal
    def test_jmlr(self):
        self._process(venue_name='jmlr',
                      correct_range=range(1, 25 + 1))

    def test_pvldb(self):
        self._process(venue_name='pvldb',
                      correct_range=range(1, 18 + 1))


if __name__ == '__main__':
    if os.path.exists(save_dir_prefix):
        shutil.rmtree(save_dir_prefix)

    unittest.main()
