#!/usr/bin/env python3
#
# SystemHighstate
#
# (c) 2025 SUSE Linux GmbH, Germany.
# GNU Public License. No warranty. No Support
#
# Version: 2025-07-29
#
# Created by: SUSE Michael Brookhuis
#
# This script will perform a highstate.
#
# Releases:
# 2025-07-29 M.Brookhuis - Initial release
#

"""
This script will perform a highstate on the give system
"""

import argparse
import datetime
import xmlrpc.client

import smtools



def main():
    """
    Main function
    """
    try:
        parser = argparse.ArgumentParser(description="Update the give system.")
        parser.add_argument('-s', '--server', help='name of the server to receive config update. Required')
        parser.add_argument('--version', action='version', version='%(prog)s 2.0.0, July 29, 2025')
        args = parser.parse_args()
        if not args.server:
            smt = smtools.SMTools("system_highstate")
            smt.log_error("The option --server is mandatory. Exiting script")
            smt.exit_program(1)
        else:
            smt = smtools.SMTools("system_highstate", args.server, True)
        # login to suse manager
        smt.log_info("Start")
        smt.log_debug("The following arguments are set: ")
        smt.log_debug(args)
        smt.suman_login()
        smt.set_hostname(args.server)
        smt.system_scheduleapplyhighstate(xmlrpc.client.DateTime(datetime.datetime.now()))
        smt.close_program()
    except Exception as err:
        smt.log_error("general error:")
        smt.log_error(err)
        raise

if __name__ == "__main__":
    SystemExit(main())
