#!/usr/bin/env python3
#
# (c) 2019 SUSE Linux GmbH, Germany.
# GNU Public License. No warranty. No Support
# For question/suggestions/bugs mail: michael.brookhuis@suse.com
#
# Version: 2020-03-23
#
# Created by: SUSE Michael Brookhuis
#
# This script will clone channels from the give environment.
#
# Release:
# 2019-10-23 M.Brookhuis - initial release.
# 2020-02-03 M.Brookhuis - Bug fix: there should be no fatal error.
# 2020-03-21 M.Brookhuis - RC 1 if there has been an error
# 2020-03-23 M.Brookhuis - Added backup option
# 2020-05-02 M.Brookhuis - all api calls moved to smtools.py and added debug logging
#

"""
This program will sync the give environment in all projects
"""

import argparse
import datetime
import time
from argparse import RawTextHelpFormatter

import smtools

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


def check_build_progress(project_name, project_env):
    smt.log_info("In progress")
    while smt.contentmanagement_lookupenvironment(project_name, project_env).get('status') == "building":
        time.sleep(60)
        smt.log_info("In progress")


def update_environment(args):
    """
    Updating an environment within a project
    """
    environment_found = False
    project_list = smt.contentmanagement_listprojects()
    for project in project_list:
        project_details = smt.contentmanagement_listprojectenvironment(project.get('label'))
        if project_details:
            number_in_list = 1
            for environment_details in project_details:
                if environment_details.get('label') == args.environment:
                    environment_found = True
                    smt.log_info(
                        'Updating environment {} in the project {}.'.format(args.environment, project.get('label')))
                    if args.backup:
                        channel_start = project.get('label') + "-" + args.environment
                        for channel in smt.get_labels_all_channels():
                            if channel.startswith(channel_start):
                                if not smt.channel_software_getdetails(channel).get('parent_channel_label').startswith(channel_start):
                                    create_backup(channel)
                                    break
                    dat = ("%s-%02d-%02d" % (datetime.datetime.now().year, datetime.datetime.now().month, datetime.datetime.now().day))
                    build_message = "Created on {}".format(dat)
                    if number_in_list == 1:
                        project_env = environment_details.get('label')
                        smt.contentmanagement_buildproject(project.get('label'), build_message)
                        check_build_progress(project.get('label'), project_env)
                        break
                    else:
                        project_env = environment_details.get('label')
                        smt.contentmanagement_promoteproject(project.get('label'), environment_details.get('previousEnvironmentLabel'))
                        check_build_progress(project.get('label'), project_env)
                        break
                number_in_list += 1
    if not environment_found:
        smt.minor_error("The given environment {} does not exist".format(args.environment))


def main():
    """
    Main section
    """
    global smt
    smt = smtools.SMTools("sync_environment")
    parser = argparse.ArgumentParser(formatter_class=RawTextHelpFormatter, description=('''\
         Usage:
         sync_environment.py
    
               '''))
    parser.add_argument("-e", "--environment", help="the project to be updated. Mandatory with --project")
    parser.add_argument("-b", "--backup", action="store_true", default=0, help="creates a backup of the stage first.")
    parser.add_argument('--version', action='version', version='%(prog)s 1.1.0, May 2, 2020')
    args = parser.parse_args()
    smt.suman_login()
    if args.environment:
        update_environment(args)
    else:
        smt.fatal_error("Option --environment is not given. Aborting operation")

    smt.close_program()


if __name__ == "__main__":
    SystemExit(main())
