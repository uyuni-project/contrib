#!/usr/bin/env python3
#
# remove_software_project
#
# (c) 2018 SUSE Linux GmbH, Germany.
# GNU Public License. No warranty. No Support
# For question/suggestions/bugs mail: michael.brookhuis@suse.com
#
# Version: 2025-08-14
#
# Created by: SUSE Michael Brookhuis
#
# This script will perform the following actions:
# - Will remove the given environment of content lifecycle software project
# - If no environment is given, all environments will be removed
# - If select delete activation-keys using the environment(s)
# - If select delete profiles and distribution using the environment(s)
#
#
# Releases:
# 2025-08-12 M.Brookhuis - Initial release
#

"""
This script will delete content lifecycle software project
"""

import argparse

import smtools

__smt = None


def get_parent_channel(project, environment):
    """
    Fetches the parent channel for a specified project and environment.

    This function attempts to retrieve the base channel associated
    with a given project and environment by iterating through the
    list of project sources and comparing against available base
    channel labels. If no match is found, the function returns None.

    :param project: The name of the project for which to determine
        the parent channel.
    :type project: str
    :param environment: The target environment for the project
        (e.g., development, staging, production).
    :type environment: str
    :return: The parent channel label if found, otherwise None.
    :rtype: str or None
    """
    project_sources = smt.contentmanagement_listprojectsources(project)
    for source in project_sources:
        base_channel = f"{project}-{environment}-{source.get('channelLabel')}"
        if base_channel in smt.get_labels_all_basechannels():
            return base_channel
    return None

def do_activationkeys(channel, delete_activationkeys):
    """
    Executes operations on activation keys associated with the given channel. If
    `delete_activationkeys` is set to True, activation keys related to the
    specified channel will be deleted; otherwise, the method issues a warning
    about the existing activation keys.

    :param channel: The channel label to check for associated activation keys
        before processing. It acts as the identifier for filtering activation
        keys.
    :type channel: str

    :param delete_activationkeys: Specifies whether to delete the activation keys
        associated with the given channel. If True, deletes the activation keys;
        otherwise, produces a warning for existing keys.
    :type delete_activationkeys: bool

    :return: True if all activation keys are processed successfully or there are
        no activation keys associated with the channel; False if there are
        activation keys and deletion is not requested.
    :rtype: bool
    """
    activations_keys = smt.activationkey_listactivationkeys()
    for activation_key in activations_keys:
        if activation_key.get('base_channel_label') == channel:
            if delete_activationkeys:
                smt.log_info(f"Deleting activationkey {activation_key.get('key')}")
                smt.activationkey_delete(activation_key.get('key'))
            else:
                smt.log_warning(f"There are activationkeys assigned to channel {channel}. "
                                f"Please remove them before deleting the environment. "
                                f"Or use the option --activationkey to delete them.")
                return False
    return True

def do_distributions(channel, delete_distributions):
    """
    Processes distributions assigned to a given channel. Optionally deletes the distributions.

    This function retrieves a list of distributions associated with a specific channel.
    If distributions are found, it either logs an appropriate warning message or deletes
    them depending on the value of the `delete_distributions` parameter.

    :param channel: The channel to check for assigned distributions.
    :type channel: str
    :param delete_distributions: Flag indicating whether to delete the distributions.
    :type delete_distributions: bool
    :return: True if all distributions were successfully processed or no distributions
        were found. False if distributions exist but were not deleted.
    :rtype: bool
    """
    distributions = smt.kickstart_tree_list(channel)
    if distributions:
        if delete_distributions:
            for distribution in distributions:
                if delete_distributions:
                    smt.log_info(f"Deleting distribution {distribution} and assigned profiles")
                    smt.kickstart_tree_deletetreeandprofiles(distribution.get('label'))
        else:
            smt.log_warning(f"There are distributions assigned to channel {channel}. "
                            f"Please remove them before deleting the environment. "
                            f"Or use the option --distribution to delete them.")
            return False
    return True

def delete_environment(args, environment):
    """
    Deletes the specified environment after ensuring there are no systems assigned
    and required cleanup steps associated with the environment are performed.
    This function checks for systems subscribed to the environment's parent channel,
    removes associated activation keys and distributions if specified,
    and finally attempts to delete the environment.

    :param args: Arguments or configurations needed for the operation. Must include
                 the project and optionally activation key and distribution details
                 for removal.
    :type args: Any
    :param environment: Name of the environment to be deleted.
    :type environment: str
    :return: Boolean indicating whether the environment was successfully deleted
             or if the operation failed.
    :rtype: bool
    """
    smt.log_info(f"Deleting environment {environment}")
    parent_channel = get_parent_channel(args.project, environment)
    subscribed_systems = smt.channel_software_listsubscribedsystems(parent_channel)
    if subscribed_systems:
        smt.log_error(f"There are systems assigned to channel {parent_channel}. "
                      f"Please remove them before deleting the environment.")
        return False
    if not do_activationkeys(parent_channel, args.activationkey):
        return False
    if not do_distributions(parent_channel, args.distribution):
        return False
    if smt.contentmanagement_removeenvironment(args.project, environment):
        smt.log_info(f"Environment {environment} deleted successfully")
    else:
        smt.log_error(f"Unable to delete environment {environment}")
        return False
    return True

def manage_project(args):
    """
    Manages a given project by deleting specified environments or the entire project.
    If a specific environment is provided, it will delete that environment. Otherwise,
    it deletes all environments associated with the project and then the project itself.
    If the project does not exist, a warning is logged, and no action is taken.

    :param args: The input arguments containing details about the project and environments to manage.
    :type args: Namespace
    :return: A boolean indicating whether the operation was successful.
    :rtype: bool
    """
    project_details = smt.contentmanagement_listprojectenvironment(args.project)
    if project_details:
        if args.environment:
            smt.log_info(f"Deleting environment {args.environment} from project {args.project}")
            result = delete_environment(args, args.environment)
            if not result:
                return False
        else:
            for environment_details in project_details:
                result = delete_environment(args, environment_details.get('label'))
                if not result:
                    return False
                smt.log_info(f"Deleting environment {environment_details.get('label')} from project {args.project}")
            smt.contentmanagement_removeproject(args.project)
    else:
        smt.log_warning(f"Project {args.project} do not exists. No actions performed")
        return False
    return True

def main():
    """
    Main function
    """
    global smt
    parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter, description=('''\
        Usage:
        remove_software_project.py 
            '''))
    parser.add_argument('-p', '--project', help='name of the project to be created. Required')
    parser.add_argument("-e", "--environment", help="Environment to be deleted. If none given, the whole project will be deleted.")
    parser.add_argument("-d", '--distribution', action="store_true", default=0, help="Delete the distributions and profiles using this project and environment.")
    parser.add_argument("-a", '--activationkey', action="store_true", default=0, help="Delete the activationkeys using this project and environment.")
    parser.add_argument('--version', action='version', version='%(prog)s 1.0.0, August 12, 2025')
    args = parser.parse_args()
    if not args.project:
        smt = smtools.SMTools("remove_software_project")
        smt.log_error("The option --project is mandatory. Exiting script")
        smt.exit_program(1)
    else:
        smt = smtools.SMTools("remove_software_project")
    # login to suse manager
    smt.log_info("Start")
    smt.suman_login()
    if manage_project(args):
        smt.close_program()
        smt.log_info("Finished successfully")
    else:
        smt.close_program(1)
        smt.log_error("Finished with errors")

if __name__ == "__main__":
    SystemExit(main())
