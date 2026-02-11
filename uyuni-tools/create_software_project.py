#!/usr/bin/env python3
#
# Create_software_project
#
# (c) 2018 SUSE Linux GmbH, Germany.
# GNU Public License. No warranty. No Support
# For question/suggestions/bugs mail: michael.brookhuis@suse.com
#
# Version: 2025-10-28
#
# Created by: SUSE Michael Brookhuis
#
# This script will perform the following actions:
# - Will create a new content lifecycle software project
# - Will create the given environments.
# - Will add the give channels (parent or separate channels)
#
# What is not present at the moment:
# - add a filter
#
# The script will not build or promote the project environments.
# Run sync_stage.py --project <project> --environment <environment>
# Start with the first environment and give the system enough time to perform the update.
#
# Releases:
# 2019-04-29 M.Brookhuis - Initial release
# 2020-07-08 M.Brookhuis - Version 2.
#                        - changed logging
#                        - moved api calls to smtools.py
# 2025-06-06 M.Brookhuis - change in description to use sync_stage
# 2025-06-19 M.Brookhuis - changed behavior of add and delete. They will display warning if more options are given
# 2025-10-28 M.Brookhuis - added that channels are build/promoted after the environment is created
#                        - added option --nobuild to not perform a build or promote
#                        - added option --activationkey to create activationkeys for each environment. Will not work with --no-build

"""
A script for managing content lifecycle software projects.

This script provides an interface to create new content lifecycle software projects,
manage their environments, and attach or detach software channels. It is capable of
updating project environments and creating activation keys for software projects. The
main goal is to facilitate automating lifecycle management processes.

Functions:
- sync_completed: Verifies if the environment sync/build process is completed.
- update_environment: Updates a specific environment within a project.
- create_activation_key: Responsible for generating unique activation keys.
- channels_to_project: Adds or deletes channels from a project.
- create_project: Creates a new project along with its environments.
- add_child_channels: Retrieves child channels of a given base channel.
- manage_project: Manages the existence and state of a project and its components.
"""

import argparse
import datetime
import time

import smtools

__smt = None

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
                if (environment_details.get('status') == "building" or environment_details.get('status') == "generating_repodata") and wait:
                    smt.log_info(f"environment {env} still being build. Waiting")
                    time.sleep(30)
                else:
                    smt.log_error(f"for environment {env} building is still in progress and option wait is False.")
                    return False

def update_environment(project, env):
    """
    Update an environment.
    :param env:
    :param project:
    :return: True when the environment is updated, false otherwise
    """
    environment_present = False
    project_details = smt.contentmanagement_listprojectenvironment(project)
    number_in_list = 1
    for environment_details in project_details:
        if environment_details.get('label') == env.rstrip():
            environment_present = True
            smt.log_info('Updating environment {} in the project {}.'.format(env, project))
            dat = ("%s-%02d-%02d" % (datetime.datetime.now().year, datetime.datetime.now().month, datetime.datetime.now().day))
            build_message = "Created on {}".format(dat)
            if number_in_list == 1:
                smt.contentmanagement_buildproject(project, build_message)
                sync_completed(env, project, True)
                break
            else:
                if sync_completed(environment_details.get('previousEnvironmentLabel'), project, True):
                    smt.contentmanagement_promoteproject(project, environment_details.get('previousEnvironmentLabel'))
                    sync_completed(env, project, True)
                else:
                    message = ('Unable to update channel because previous environment is not ready for environment {} for project {}.'.format(env, project))
                    smt.fatal_error(message)
                break
        number_in_list += 1
    if environment_present:
        return True
    else:
        return False

def create_activation_key(project, env):
    """
    Creates an activation key for a given project and environment. This method is responsible
    for generating and returning a unique activation key associated with the specified project
    and environment settings.

    :param project: The name of the project for which the activation key will be created.
    :type project: str
    :param env: The environment (e.g., development, testing, production) associated with
        the project.
    :type env: str
    :return: A string representing the generated unique activation key for the specified
        project and environment.
    :rtype: str
    """
    smt.log_info(f"Creating activation key for project {project} and environment {env}")
    project_channels = smt.contentmanagement_listprojectsources(project)
    parent_channel = ""
    child_channels = []
    key_name = f"{project}-{env}"
    key_id  = f"1-{project}-{env}"
    for channel in project_channels:
        details = smt.channel_software_getdetails(channel.get('channelLabel'))
        if not details.get('parent_channel_label'):
            parent_channel = channel.get('channelLabel')
        else:
            child_channels.append(channel.get('channelLabel'))
    smt.activationkey_create_vh(key_name, key_name, parent_channel, False)
    smt.activationkey_add_child_channels(key_id, child_channels)
    smt.log_info("Activation key created")

def channels_to_project(project, channels, action):
    """
    Add the channels to the project
    """
    for channel in channels.split(","):
        smt.log_info(f"{action} channel '{channel}' to project '{project}'")
        if smt.channel_software_getdetails(channel):
            if action == "add":
                if smt.contentmanagement_attachsource(project, channel, False):
                    smt.log_info("completed")
                else:
                    smt.log_warning(f"unable to add channel '{channel}'. Skipping")
            if action == "delete":
                if smt.contentmanagement_detachsource(project, channel, False):
                    smt.log_info("completed")
                else:
                    smt.log_warning(f"unable to remove channel '{channel}'. Skipping")
        else:
            smt.log_warning(f"Channel '{channel}' doesn't exist. Skipping")


def create_project(project, environment, basechannel, addchannel, description):
    """
    Create a new software project
    """
    if not description:
        dat = ("%s-%02d-%02d" % (datetime.datetime.now().year, datetime.datetime.now().month,
                                 datetime.datetime.now().day))
        description = f"Created on {dat}"
    smt.log_info(f"Creating project {project}")
    smt.contentmanagement_createproject(project, project, description)
    pre_env = ""
    for env in environment.split(","):
        smt.log_info(f"Adding environment {env}")
        env_desc = env + " " + description
        smt.contentmanagement_createenvironment(project, pre_env, env, env, env_desc)
        pre_env = env
    all_channels = ""
    if basechannel:
        if smt.channel_software_getdetails(basechannel, True):
            all_channels = basechannel + "," + add_child_channels(basechannel)
        else:
            smt.log_warning(f"The given basechannel {basechannel} doesn't exist. Please check. "
                            f"Continue with next step.")
    if addchannel:
        if all_channels:
            all_channels = all_channels + "," + addchannel
        else:
            all_channels = addchannel
    if all_channels:
        channels_to_project(project,all_channels,"add")

def add_child_channels(basechannel):
    """
    collect the child channels of the given basechannel
    """
    channels_to_add = ""
    for child in smt.channel_software_listchildren(basechannel):
        if not channels_to_add:
            channels_to_add = child.get('label')
        else:
            channels_to_add += ","
            channels_to_add += child.get('label')
    return channels_to_add


def manage_project(args):
    """
    creating project
    valid options (m manadatory, o optional:
    - create new project: project (m), environment (m), basechannel (o), addchannel (o)
    - add channel to existing project: project (m), addchannel (m)
    - delete channel from existing project: project (m), deletechannel (m)
    """
    project_present = smt.contentmanagement_lookupproject(args.project)
    if project_present:
        # project is present so only add and delete channel is valid
        if args.environment and args.basechannel:
            smt.log_warning(f"Project {args.project} already exists. The options --environment and "
                            f"--basechannel are ignored")
        if args.addchannel:
            channels_to_project(args.project, args.addchannel, "add")
        if args.deletechannel:
            channels_to_project(args.project, args.deletechannel, "delete")
    else:
        # project is not present so needs to be created.
        create_project(args.project, args.environment, args.basechannel, args.addchannel, args.description)
    if not args.nobuild:
        for env in args.environment.split(","):
            update_environment(args.project, env)
    if args.activationkey and not args.nobuild:
        for env in args.environment.split(","):
            create_activation_key(args.project, env)

def main():
    """
    Main function
    """
    global smt
    parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter, description=('''\
        Usage:
        create_software_project.py 
            '''))
    parser.add_argument('-p', '--project', help='name of the project to be created. Required')
    parser.add_argument("-e", "--environment", help="Comma delimited list without spaces of the environments to be created. Required")
    parser.add_argument("-b", '--basechannel', help="The base channel on which the project should be based.")
    parser.add_argument("-a", '--addchannel', help="Comma delimited list without spaces of the channels to be added. Can be used together with --basechannel")
    parser.add_argument("-d", '--deletechannel', help="Comma delimited list without spaces of the channels to be removed from the project.")
    parser.add_argument("-m", '--description', help="Description of the project to be created.")
    parser.add_argument("-n", "--nobuild", action="store_true", help="Don't perform a build or promote", default=0)
    parser.add_argument("-k", "--activationkey", action="store_true", help="create activationkeys for each environment. Will not work with --no-build", default=0)
    # parser.add_argument("-t", "--distribution", action="create distribution for each environment", default=0,)
    parser.add_argument('--version', action='version', version='%(prog)s 2.0.2, October 28, 2025')
    args = parser.parse_args()
    if not args.project:
        smt = smtools.SMTools("create_software_project")
        smt.log_error("The option --project is mandatory. Exiting script")
        smt.exit_program(1)
    else:
        smt = smtools.SMTools("create_software_project")
    # login to suse manager
    smt.log_info("Start")
    smt.suman_login()
    manage_project(args)
    smt.close_program()

if __name__ == "__main__":
    SystemExit(main())
