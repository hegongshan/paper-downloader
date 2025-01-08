import logging
import os
import random
import shutil
import unittest

import core.venue as venue

save_dir_prefix = os.path.join('paper', 'test')
sleep_time_per_paper = 2

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')


class Test(unittest.TestCase):

    def _test_conf(self, venue_name, correct_year_range, error_year_range=None):
        save_dir_ = os.path.join(save_dir_prefix, venue_name)

        venue_publisher = venue.parse_venue(venue_name)

        if error_year_range:
            year_range = list(correct_year_range) + list(error_year_range)
        else:
            year_range = correct_year_range

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

            paper_entry = random.sample(paper_list, 1)[0]
            publisher.process_one(paper_entry)
            if idx < len(correct_year_range):
                self.assertEqual(len(os.listdir(save_dir)), 1)
            else:
                self.assertEqual(len(os.listdir(save_dir)), 0)
            logging.info(f'Test Done!')

    def test_icml(self):
        venue_name = 'icml'
        self._test_conf(venue_name=venue_name,
                        correct_year_range=range(2010, 2024 + 1),
                        error_year_range=range(1980, 2009 + 1))


if __name__ == '__main__':
    if os.path.exists(save_dir_prefix):
        shutil.rmtree(save_dir_prefix)

    unittest.main()
