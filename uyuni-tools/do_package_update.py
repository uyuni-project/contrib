#!/usr/bin/env python3
#
# do_package_update
#
# (c) 2016 SUSE Linux GmbH, Germany.
# GNU Public License. No warranty. No Support (only from SUSE Consulting
#
# Version: 2016-11-22
#
# Created by: SUSE Michael Brookhuis
#
# This script will update the server with the latest patches available in its assigned channels. 
#
# Releases:
# 2016-01-06 M.Brookhuis - initial release.
# 2016-11-22 M.Brookhuis - before deleting action chain, check if it is present.
# 2017-04-24 M.Brookhuis - Add salt intergration and add more logging 
# 2017-04-25 M.Brookhuis - add package schedule refresh to prevent spmig to fail
# 2018-05-22 M.Brookhuis - Change log file location
# 2019-04-11 M.Brookhuis - Migrated to python3
#                        - added proper logging
#                        - changed config to yaml
# 
# return codes
# 0 = job successfully finished
# 1 = host not found
# 2 = error on SUSE Manager
# 3 = job failed
#
#
#
#

"""
This script will update the configuration of the given server
"""
import sys
sys.path.append('/etc/pnw')
import argparse
from argparse import RawTextHelpFormatter
import xmlrpc.client
import datetime
import smtools
import time

__smt = None


def check_progress(actionid):
    """
    Check progress of event in SUSE Manager
    """
    progress = [{'timestamp': 'init'}]
    while progress:
        try:
            progress = smt.client.schedule.listInProgressSystems(smt.session, actionid)
        except xmlrpc.client.Fault:
            smt.log_error('progress failed')
            return 2
        smt.log_info("in progress")
        time.sleep(15)
    time.sleep(15)
    try:
        failed = smt.client.schedule.listFailedSystems(smt.session, actionid)
    except xmlrpc.client.Fault:
        smt.log_error('Unable get failed status')
        return 2
    if failed:
        smt.log_error("action failed")
        return 3
    try:
        completed = smt.client.schedule.listCompletedSystems(smt.session, actionid)
    except xmlrpc.client.Fault:
        smt.log_error('Unable get completed status')
        return 2
    if completed:
        smt.log_info("action completed")
    return 0


def do_package_update(server_id):
    """
    Update packages
    """
    smt.log_info("Updating the server")
    ai = apply_updates_regular(server_id)
    if ai == 0 or ai == 2 or ai == 3:
        result = ai
    else:
        result = check_progress(ai)
    if result == 0:
        try:
            ai = smt.client.system.schedulePackageRefresh(smt.session, server_id, datetime.datetime.now())
        except xmlrpc.client.Fault as err:
            smt.log_info("unable to schedule package refresh for server. Error: {}".format(err))
            return 2
        smt.log_info("Package refresh running for system")
        time.sleep(120)
        result = check_progress(ai)
    return result


def apply_updates_regular(sd):
    """
    Update packages
    """
    try:
        alluprpms = smt.client.system.listLatestUpgradablePackages(smt.session, sd)
    except xmlrpc.client.Fault:
        smt.log_info('Unable to get a list of updatable rpms {}'.format(smt.hostname))
        return 2
    rpms = []  # this array will contain the IDs of the packeges to install
    for x in alluprpms:
        rpms.append(x.get('to_package_id'))
    try:
        actionid = smt.client.system.schedulePackageInstall(smt.session, sd, rpms, datetime.datetime.now())
    except xmlrpc.client.Fault:
        smt.log_info('Unable to add package to chain')
        return 2
    time.sleep(15)
    return actionid


def main():
    """
    Main function
    """
    global smt
    parser = argparse.ArgumentParser(formatter_class=RawTextHelpFormatter, description=('''\
         Usage:
         do_package_update.py 

               '''))
    parser.add_argument('-s', '--server', help='name of the server to patched (without domain). Required')
    parser.add_argument('--version', action='version', version='%(prog)s 1.0.1, April 11, 2019')
    args = parser.parse_args()
    if not args.server:
        perr = "The option --server <server_to_run_script_on> is required"
        smt = smtools.SMTools("nonamed", "do_package_update")
        smt.set_hostname("nonamed")
        smt.fatal_error(perr)
    else:
        smt = smtools.SMTools(args.server.lower(), "do_package_update")
        smt.suman_login()
        smt.set_hostname(args.server.lower())
    smt.log_info("######################################################")
    smt.log_info("Start")
    smt.log_info("######################################################")
    do_package_update(smt.get_server_id())
    smt.close_program()


if __name__ == "__main__":
    SystemExit(main())
