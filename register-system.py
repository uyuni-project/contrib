#!/usr/bin/env python3
#
# register_system.py
#
# (c) 2020 SUSE Linux GmbH, Germany.
# GNU Public License. No warranty. No Support
# For question/suggestions/bugs mail: michael.brookhuis@suse.com
#
# Version: 2020-04-01
#
# Created by: SUSE Michael Brookhuis.
#
# Releases:
# 2020-04-01 M.Brookhuis - initial release.
#
"""This program will add the give system to the software-, configurationchannels and systemgroups after migration"""
import sys
import argparse
from argparse import RawTextHelpFormatter
import os
import xmlrpc.client
import smtools
import datetime
import time

__smt = None


def perform_bootstrap(server, akey):
     try:
         smt.client.system.bootstrap(smt.session, server, 22, "root", "", akey, True)
     except xmlrpc.client.Fault:
         smt.fatal_error("Error bootstrapping server {}".format(server))
     smt.log_info("server {} registered".format(server))


def main():
     """
     Main Function
     """
     global smt
     parser = argparse.ArgumentParser(formatter_class=RawTextHelpFormatter, description=('''\
          Usage:
          register_system.py

                '''))
     parser.add_argument('-s', '--server', help='name of the server to receive config update. Required')
     parser.add_argument('-a', '--activationkey', help='activationkey to use for registration')

     parser.add_argument('--version', action='version', version='%(prog)s 1.0.0, April 1, 2020')
     args = parser.parse_args()
     if not args.server:
         smt = smtools.SMTools("register_system")
         smt.log_error("The option --server is mandatory. Exiting script")
         smt.exit_program(1)
     elif not args.activationkey:
         smt = smtools.SMTools("register_system")
         smt.log_error("The option --activationkey is mandatory. Exiting script")
         smt.exit_program(1)
     else:
         smt = smtools.SMTools("register_system", args.server)
         smt.suman_login()
         smt.set_hostname_only(args.server)
         # login to suse manager
         smt.log_info("Start")
         perform_bootstrap(args.server, args.activationkey)
     smt.close_program()


if __name__ == "__main__":
     SystemExit(main())

