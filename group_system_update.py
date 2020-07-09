#!/usr/bin/env python3
#
# group_system_update
#
# (c) 2018 SUSE Linux GmbH, Germany.
# GNU Public License. No warranty. No Support (only from SUSE Consulting
#
# Version: 2020-06-29
#
# Created by: SUSE Michael Brookhuis
#
# This script will perform the following actions:
# - will call system_update for all systems in the given systemgroup.
# - if the config should also be deployed, the option --applyconfig should be given.
#
# Releases:
# 2019-11-02 M.Brookhuis - Initial release
# 2020-01-15 M.Brookhuis - Added update script option.
# 2020-06-29 M.Brookhuis - Version 2.
#                        - changed logging
#                        - moved api calls to smtools.py
#

"""
This script will perform a complete system maintenance
"""

import argparse
import subprocess
import time
from argparse import RawTextHelpFormatter

import smtools

__smt = None


def group_update_server(args):
    """
    start update process
    """
    smt.log_info("Processing systemgroup '{}'.".format(args.group))
    group_systems = smt.systemgroup_listsystemminimal(args.group)
    if group_systems:
        for system in group_systems:
            program_call = smtools.CONFIGSM['dirs']['scripts_dir'] + "/system_update.py -s " + system.get('name')
            if args.applyconfig:
                program_call += " -c"
            if args.updatescript:
                program_call += " -u"
            if args.noreboot:
                program_call += " -n"
            if args.forcereboot:
                program_call += " -f"
            smt.log_info("Update started for {}".format(system.get('name')))
            smt.log_debug("Command issued: {}".format(program_call))
            subprocess.Popen(program_call, shell=True)
            time.sleep(smtools.CONFIGSM['maintenance']['wait_between_systems'])
    else:
        smt.log_warning("The given systemgroup '{}' has no systems.".format(args.group))


def main():
    """
    Main function
    """
    global smt
    parser = argparse.ArgumentParser(formatter_class=RawTextHelpFormatter, description=('''\
        Usage:
        do_swat.py 
            '''))
    parser.add_argument('-g', '--group', help='name of the server to receive config update. Required')
    parser.add_argument("-c", '--applyconfig', action="store_true", default=0,
                        help="Apply configuration after and before patching")
    parser.add_argument("-u", "--updatescript", action="store_true", default=0,
                        help="Excute the server specific _start and _end scripts")
    parser.add_argument("-n", "--noreboot", action="store_true", default=0,
                        help="Do not reboot server after patching or supportpack upgrade.")
    parser.add_argument("-f", "--forcereboot", action="store_true", default=0,
                        help="Force a reboot server after patching or supportpack upgrade.")
    parser.add_argument('--version', action='version', version='%(prog)s 2.0.0, June 29, 2020')
    args = parser.parse_args()
    smt = smtools.SMTools("group_system_update")
    if not args.group:
        smt.log_error("The option --group is mandatory. Exiting script")
        smt.exit_program(1)
    # login to suse manager
    smt.log_info("Start")
    smt.suman_login()
    group_update_server(args)
    smt.close_program()


if __name__ == "__main__":
    SystemExit(main())
