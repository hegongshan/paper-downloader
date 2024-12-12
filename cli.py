import argparse
import logging
import os
from enum import Enum

import utils
import venue

default_log_file = 'paper-downloader.log'


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
                      help='Set a directory to store these papers. (default value: "./paper")')
    args.add_argument('--log-file',
                      type=str,
                      default=default_log_file,
                      help=f'The filename of the log. (default value: "{default_log_file}")')
    args.add_argument('--sleep-time-per-paper',
                      type=float,
                      default=2,
                      help='The time interval between downloads, measured in seconds. (default value: 2)')
    args.add_argument('--keyword',
                      type=str,
                      help='The keywords or regex patterns that must be present or matched in the title of the paper.')

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

    # config logging
    log_file = args.log_file if args.log_file else default_log_file
    log_dir = os.path.dirname(log_file)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir)
    logging.basicConfig(filename=log_file,
                        level=logging.INFO,
                        format='%(asctime)s [%(levelname)s] %(message)s')

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

    if venue.is_conference(venue_publisher):
        if not args.year:
            utils.print_and_exit(f'Year is a required field.')
        if args.volume:
            utils.print_warning(
                f'The conference "{venue_name}" does not require the volume field, but it is currently set to "{args.volume}".')
    elif venue.is_journal(venue_publisher):
        if not args.volume:
            utils.print_and_exit(f'Volume is a required field.')
        if args.year:
            utils.print_warning(
                f'The journal "{venue_name}" does not require the year field, but it is currently set to "{args.year}".')

    # instantiate venue
    logging.info(args)
    publisher = venue_publisher(save_dir=args.save_dir,
                                sleep_time_per_paper=args.sleep_time_per_paper,
                                keyword=args.keyword,
                                venue_name=venue_name,
                                year=args.year,
                                volume=args.volume,
                                parallel=args.parallel,
                                proxies=proxies)
    publisher.process()
    utils.print_success('Task Done!')
