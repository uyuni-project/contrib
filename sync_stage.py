#!/usr/bin/env python3
#
# (c) 2019 SUSE Linux GmbH, Germany.
# GNU Public License. No warranty. No Support
# For question/suggestions/bugs mail: michael.brookhuis@suse.com
#
# Version: 2019-10-17
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


def clone_channel(channel):
    """
    Clone channel
    """
    chan = channel.get('label')
    smt.log_info('Updating %s' % chan)
    clone_label = smt.channel_software_getdetails(chan).get('clone_original')
    if not clone_label:
        smt.log_error('Unable to get parent data for channel {}. Has this channel been cloned. Skipping'.format(chan))
        return
    smt.log_info('     Errata .....')
    total = smt.channel_software_mergeerrata(clone_label, chan)
    smt.log_info('     Merging {} patches'.format(len(total)))
    time.sleep(60)
    smt.log_info('     Packages .....')
    total = smt.channel_software_mergepackages(clone_label, chan)
    smt.log_info('     Merging {} packages'.format(len(total)))


def update_project(args):
    """
    Updating an environment within a project
    """
    environment_present = False
    project_details = smt.contentmanagement_listprojectenvironment(args.project)
    number_in_list = 1
    for environment_details in project_details:
        if environment_details.get('label') == args.environment.rstrip():
            environment_present = True
            smt.log_info('Updating environment {} in the project {}.'.format(args.environment, args.project))
            if args.backup:
                channel_start = args.project + "-" + args.environment
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
                smt.contentmanagement_buildproject(args.project, build_message)
                break
            else:
                smt.contentmanagement_promoteproject(args.project, environment_details.get('previousEnvironmentLabel'))
                break
        number_in_list += 1
    if not environment_present:
        message = ('Unable to get details of environment {} for project {}.'.format(args.environment, args.project))
        message += ' Does the environment exist?'
        smt.fatal_error(message)


def update_stage(args):
    """
    Updating the stages.
    """
    parent_details = smt.channel_software_getdetails(args.channel)
    if parent_details.get('parent_channel_label'):
        smt.log_debug("Channel_details: {}".format(parent_details))
        smt.fatal_error("Given parent channel {}, is not a parent channel.".format(args.channel))
    child_channels = smt.channel_software_listchildren(args.channel)
    smt.log_info("Updating the following channels with latest patches and packages")
    smt.log_info("================================================================")
    if args.backup:
        create_backup(args.channel)
    for channel in child_channels:
        if "pool" not in channel.get('label'):
            clone_channel(channel)
            time.sleep(10)


def main():
    """
    Main section
    """
    global smt
    smt = smtools.SMTools("sync_stage")
    parser = argparse.ArgumentParser(formatter_class=RawTextHelpFormatter, description=('''\
         Usage:
         sync_channel.py
    
               '''))
    parser.add_argument("-c", "--channel", help="name of the cloned parent channel to be updates")
    parser.add_argument("-b", "--backup", action="store_true", default=0, \
                        help="creates a backup of the stage first.")
    parser.add_argument("-p", "--project", help="name of the project to be updated. --environment is also mandatory")
    parser.add_argument("-e", "--environment", help="the project to be updated. Mandatory with --project")
    parser.add_argument("-m", "--message", help="Message to be displayed when build is updated")
    parser.add_argument('--version', action='version', version='%(prog)s 1.1.0, May 2, 2020')
    args = parser.parse_args()
    smt.suman_login()
    if args.channel:
        update_stage(args)
    elif args.project and args.environment:
        update_project(args)
    else:
        smt.log_debug("Given options: {}".format(args))
        smt.fatal_error("Option --channel or options --project and --environment are not given. Aborting operation")
    smt.close_program()


if __name__ == "__main__":
    SystemExit(main())
