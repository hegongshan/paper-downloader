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
                self.assertTrue(1 <= count <= 2)
            else:
                self.assertTrue(count == 0)
            logging.info(f'Test Done!')

        shutil.rmtree(save_dir_)

    def test_fast(self):
        self._process(venue_name='fast',
                      correct_range=range(2002, 2024 + 1))

    def test_osdi(self):
        self._process(venue_name='osdi',
                      correct_range=list(range(2002, 2020 + 2, 2)) + list(range(2021, 2024 + 1)))

    def test_atc(self):
        self._process(venue_name='atc',
                      correct_range=range(1998, 2024 + 1))

    def test_icml(self):
        self._process(venue_name='icml',
                      correct_range=range(2010, 2024 + 1),
                      error_range=range(1980, 2009 + 1))


if __name__ == '__main__':
    if os.path.exists(save_dir_prefix):
        shutil.rmtree(save_dir_prefix)

    unittest.main()
