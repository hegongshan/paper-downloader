import logging
import os
import random
import shutil
import sys
import unittest

current_dir = os.path.dirname(os.path.realpath(__file__))
parent_dir = os.path.abspath(os.path.join(current_dir, os.pardir))
sys.path.append(parent_dir)

from core import venue

save_dir_prefix = os.path.join('paper', 'test')
sleep_time_per_paper = 2

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')


class Test(unittest.TestCase):
    full_test = False

    def _test_conf(self,
                   venue_name,
                   correct_year_range,
                   error_year_range=None):
        save_dir_ = os.path.join(save_dir_prefix, venue_name)

        venue_publisher = venue.parse_venue(venue_name)

        if self.full_test:
            # 每个年份都要处理
            correct_year_len = len(correct_year_range)
            year_range = list(correct_year_range)
            if error_year_range:
                year_range += list(error_year_range)
        else:
            # 随机选择一个年份
            correct_year_len = 1
            year_range = random.sample(correct_year_range, 1)
            if error_year_range:
                year_range += random.sample(error_year_range, 1)

        for idx, year in enumerate(year_range):
            save_dir = os.path.join(save_dir_, str(year))

            logging.info(f'Start Test: venue = {venue_name}, year = {year}')
            publisher = venue_publisher(save_dir=save_dir,
                                        sleep_time_per_paper=sleep_time_per_paper,
                                        venue_name=venue_name,
                                        year=year,
                                        volume=None,
                                        proxies=None)
            paper_list = publisher.get_paper_list()
            if not paper_list:
                return

            # 随机选择一篇论文
            paper_entry = random.sample(paper_list, 1)[0]
            publisher.process_one(paper_entry)

            count = len(os.listdir(save_dir))
            if idx < correct_year_len:
                # paper + slides
                self.assertTrue(1 <= count <= 2)
            else:
                self.assertTrue(count == 0)
            logging.info(f'Test Done!')

    def test_fast(self):
        venue_name = 'fast'
        self._test_conf(venue_name=venue_name,
                        correct_year_range=range(2002, 2024 + 1))

    def test_icml(self):
        venue_name = 'icml'
        self._test_conf(venue_name=venue_name,
                        correct_year_range=range(2010, 2024 + 1),
                        error_year_range=range(1980, 2009 + 1))


if __name__ == '__main__':
    if os.path.exists(save_dir_prefix):
        shutil.rmtree(save_dir_prefix)

    unittest.main()
