import argparse
import logging
from enum import Enum
from typing import Tuple

import utils
import venue

logging.basicConfig(filename='paper-downloader.log',
                    level=logging.INFO,
                    format='%(asctime)s [%(levelname)s] %(message)s')


def parse_args():
    args = argparse.ArgumentParser(description='Run PDL.')

    # General options
    args.add_argument('--venue',
                      type=str,
                      required=True,
                      help=f'Available value = {venue.get_available_venues()}.')
    args.add_argument('--save-dir',
                      type=str,
                      default='./paper',
                      help='Set a directory to store these papers. (default value: ./paper)')
    args.add_argument('--sleep-time-per-paper',
                      type=float,
                      default=0.2,
                      help='The time interval between downloads, measured in seconds. (default value: 0.2)')

    # Conference specific options
    args.add_argument('--year',
                      type=int,
                      help='The year of the conference.')

    # Journal specific options
    args.add_argument('--volume',
                      type=int,
                      help='The volume number of the journal.')

    # Advanced options
    args.add_argument('--http-proxy',
                      type=str,
                      help='HTTP Proxy server.')
    args.add_argument('--https-proxy',
                      type=str,
                      help='HTTPS Proxy server.')
    args.add_argument('--parallel',
                      action='store_true',
                      help='Use parallel downloads.')

    return args.parse_args()


if __name__ == '__main__':
    args = parse_args()

    # set proxy server
    proxies = {}
    if args.http_proxy:
        proxies['http'] = args.http_proxy
    if args.https_proxy:
        proxies['https'] = args.https_proxy

    # parse venue
    venue_name = args.venue.lower()
    venue_publisher = venue.parse_venue(venue_name)

    if not venue_publisher:
        utils.print_and_exit(f'Unsupported venue: {venue_name}')

    # instantiate venue
    publisher = venue_publisher(save_dir=args.save_dir,
                                sleep_time_per_paper=args.sleep_time_per_paper,
                                venue_name=venue_name,
                                year=args.year if args.year else None,
                                volume=args.volume if args.volume else None,
                                parallel=args.parallel,
                                proxies=proxies if proxies else None)
    publisher.process()
