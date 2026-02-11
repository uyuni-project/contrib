#!/usr/bin/env python3
#
# (c) 2019 SUSE Linux GmbH, Germany.
# GNU Public License. No warranty. No Support
# For question/suggestions/bugs mail: michael.brookhuis@suse.com
#
# Version: 2025-10-28
#
# Created by: SUSE Michael Brookhuis
#
# This script will clone channels from the give parent.
#
# Releasmt.session:
# 2017-01-23 M.Brookhuis - initial release.
# 2019-01-14 M.Brookhuis - Added yaml
#                        - Added logging
# 2019-02-10 M.Brookhuis - General update
# 2019-10-17 M.Brookhuis - Added support for projects and environments
# 2020-03-23 M.Brookhuis - Added backup option
# 2020-04-19 M.Brookhuis - all api calls moved to smtools.py and added debug logging
# 2025-06-06 M.Brookhuis - added check if the sync of the previous environment is completed.
# 2025-07-26 M.Brookhuis - added option --all to update a given environment in all projects
# 2025-10-28 M.Brookhuis - return error when sync status is failed
#

"""
This program will sync the give stage
"""

import argparse
import datetime
import time
import smtools
from argparse import RawTextHelpFormatter

__smt = None


def create_backup(par):
    """
    Create backup from stage
    """
    dat = ("%s%02d%02d" % (datetime.datetime.now().year, datetime.datetime.now().month,
                           datetime.datetime.now().day))
    clo = "bu-" + dat + "-" + par
    if smt.channel_software_getdetails(clo, True):
        smt.fatal_error('The backupchannel {} already exists. Aborting operation.'.format(clo))
    else:
        smt.log_info("Creating backup of current channel. Channel will be called with: {}".format(clo))
    clo = "bu-" + dat + "-" + par
    clo_str = {'name': clo, 'label': clo, 'summary': clo}
    smt.channel_software_clone(par, clo_str, False)
    for channels in smt.channel_software_listchildren(par):
        clo_str = {}
        new_clo = "bu-" + dat + "-" + channels.get('label')
        clo_str['name'] = clo_str['label'] = clo_str['summary'] = new_clo
        clo_str['parent_label'] = clo
        smt.channel_software_clone(channels.get('label'), clo_str, False)
    smt.log_info("Creating backup finished")

def sync_completed(env, project, wait):
    """
    check if the sync of the sync of the previous environment is completed (built) or done (unknown).
    If status is building and wait is true,
    """
    while True:
        project_details = smt.contentmanagement_listprojectenvironment(project)
        for environment_details in project_details:
            if environment_details.get('label') == env:
                if environment_details.get('status') == "built":
                    return True
                if environment_details.get('status') == "unknown":
                    smt.log_error(f"environment {env} has never been build. Please build first")
                    return False
                if environment_details.get('status') == "failed":
                    smt.log_error(f"environment {env} failed to build. Please check logs")
                    return False
                if (environment_details.get('status') == "building" or environment_details.get('status') == "generating_repodata") and wait:
                    smt.log_info(f"environment {env} still being build. Waiting")
                    time.sleep(30)
                else:
                    smt.log_error(f"for environment {env} building is still in progress and option wait is False.")
                    return False

def update_environment(project, args):
    """
    Update an environment.
    :param args:
    :param project:
    :return: True when environment is updated, false otherwise
    """
    environment_present = False
    project_details = smt.contentmanagement_listprojectenvironment(project)
    number_in_list = 1
    for environment_details in project_details:
        if environment_details.get('label') == args.environment.rstrip():
            environment_present = True
            smt.log_info('Updating environment {} in the project {}.'.format(args.environment, project))
            if args.backup:
                channel_start = project + "-" + args.environment
                all_channels_label = smt.get_labels_all_channels()
                for channel in all_channels_label:
                    if channel.startswith(channel_start):
                        channel_details = smt.channel_software_getdetails(channel)
                        if not channel_start in channel_details.get('parent_channel_label') and not "bu-" in channel_details.get('parent_channel_label'):
                            if not channel_details.get('parent_channel_label').startswith(channel_start):
                                create_backup(channel)
                                break
            if args.message:
                build_message = args.message
            else:
                dat = ("%s-%02d-%02d" % (datetime.datetime.now().year, datetime.datetime.now().month, datetime.datetime.now().day))
                build_message = "Created on {}".format(dat)
            if number_in_list == 1:
                smt.contentmanagement_buildproject(project, build_message)
                if args.wait:
                    sync_completed(args.environment, project, args.wait)
                break
            else:
                if sync_completed(environment_details.get('previousEnvironmentLabel'), project, args.wait):
                    smt.contentmanagement_promoteproject(args.project, environment_details.get('previousEnvironmentLabel'))
                    if args.wait:
                        sync_completed(args.environment, project, args.wait)
                else:
                    message = ('Unable to update channel because previous environment is not ready for environment {} for project {}.'.format(args.environment, project))
                    smt.fatal_error(message)
                break
        number_in_list += 1
    if environment_present:
        return True
    else:
        return False

def main():
    """
    Main section
    """
    global smt
    smt = smtools.SMTools("sync_stage")
    parser = argparse.ArgumentParser(formatter_class=RawTextHelpFormatter, description=('''\
         Usage:
         sync_stage.py

               '''))
    parser.add_argument("-b", "--backup", action="store_true", default=0,
                        help="creates a backup of the stage first.")
    parser.add_argument("-w", "--wait", action="store_true", default=0,
                        help="wait until the sync of the previous environment is completed or present.")
    parser.add_argument("-p", "--project", help="name of the project to be updated. --environment is also mandatory")
    parser.add_argument("-e", "--environment", help="the project to be updated. Mandatory with --project")
    parser.add_argument("-m", "--message", help="Message to be displayed when build is updated")
    parser.add_argument('--version', action='version', version='%(prog)s 2.0.1, October 28, 2025')
    args = parser.parse_args()
    smt.suman_login()
    if args.project and args.environment:
        if update_environment(args.project, args):
            smt.log_info("Successfully updated environment: {}".format(args.environment))
        else:
            smt.log_error('Unable to get details of environment {} for project. Does the environment exist? '
                          '{}.'.format(args.environment, args.project))
    else:
        smt.log_debug("Given options: {}".format(args))
        smt.fatal_error("Options --project and --environment are not given. Aborting operation")
    smt.close_program()


if __name__ == "__main__":
    SystemExit(main())
