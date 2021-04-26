#!/usr/bin/env python3
#
# (c) 2017 SUSE Linux GmbH, Germany.
# GNU Public License. No warranty. No Support
# For question/suggestions/bugs mail: michael.brookhuis@suse.com
#
# Version: 2020-05-02
#
# Created by: SUSE Michael Brookhuis
#
# This script will clone the given channel.
#
# Releases:
# 2017-01-23 M.Brookhuis - initial release.
# 2019-01-14 M.Brookhuis - Added yaml
#                        - Added logging
# 2019-02-10 M.Brookhuis - General update
# 2020-05-02 M.Brookhuis - all api calls moved to smtools.py and added debug logging


"""This program will sync the give channel"""

import argparse
import time
from argparse import RawTextHelpFormatter
import smtools

__smt = None


def main():
    """
    Main Function
    """
    global smt
    smt = smtools.SMTools("sync_channel")
    parser = argparse.ArgumentParser(formatter_class=RawTextHelpFormatter, description=('''\
         Usage:
         sync_channel.py
    
               '''))
    parser.add_argument("-c", "--channel", help="name of the cloned parent channel to be updates")
    parser.add_argument('--version', action='version', version='%(prog)s 1.1.0, May 2, 2019')
    args = parser.parse_args()
    if not args.channel:
        smt.fatal_error("No parent channel to be cloned given. Aborting operation")
    else:
        channel = args.channel
    smt.suman_login()
    smt.log_info("Updating the following channel with latest patches and packages")
    smt.log_info("===============================================================")
    # noinspection PyUnboundLocalVariable
    smt.log_info("Updating: %s" % channel)
    clone_label = smt.channel_software_getdetails(channel).get('clone_original')
    if not clone_label:
        smt.log_error('Unable to get parent data for channel {}. Has this channel been cloned. Skipping'.format(channel))
        return
    smt.log_info('     Errata .....')
    smt.log_info('     Merging {} patches'.format(len(smt.channel_software_mergeerrata(clone_label, channel))))
    time.sleep(60)
    smt.log_info('     Packages .....')
    smt.log_info('     Merging {} packages'.format(len(smt.channel_software_mergepackages(clone_label, channel))))
    smt.log_info("FINISHED")
    smt.close_program()


if __name__ == "__main__":
    SystemExit(main())
