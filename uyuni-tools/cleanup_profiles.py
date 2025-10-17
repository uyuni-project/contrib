#!/usr/bin/env python3
#
# cleanup_profiles
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
# - Remove profiles when there is a system installed with the same name and newly installed within the last 2 weeks.
#
#
# Releases:
# 2025-08-14 M.Brookhuis - Initial release
#

"""
This script will delete profiles from which a system has been installed.
"""

import smtools

__smt = None

def get_profiles():
    """
    Retrieves a list of profile labels from a kickstart configuration.

    This function iterates over a list of kickstart configurations and extracts the
    'label' attribute from each configuration, returning a compiled list of these
    labels.

    :return: A list containing the label values from the kickstart configurations.
    :rtype: list
    """
    return [c.get('label') for c in smt.kickstart_list_kickstarts()]

def get_systems():
    """
    Generates and returns a list of system names from the system list.

    This function retrieves information about systems via the `smt.system_listsystems`
    method, extracts the 'name' field from each system, and compiles it into a list.

    :return: A list of system names
    :rtype: list
    """
    return [c.get('name') for c in smt.system_listsystems()]

def start_cleanup_profiles():
    """
    Starts the cleanup process for profiles by checking their existence in systems
    and deleting them if necessary. It identifies relevant profiles by matching
    them with available systems and performs deletions using specific methods.

    :raises Exception: If an unexpected error occurs during the cleanup process.
    """
    profiles = get_profiles()
    systems = get_systems()
    for profile in profiles:
        result = [s for s in systems if profile in s]
        if result:
            sid = smt.get_server_id(False, result[0])
            if sid != 0:
                smt.log_info(f"Deleting profile {profile}")
                smt.kickstart_deleteprofile(profile)
    return

def main():
    """
    Main function to handle execution of the cleanup profiles process.

    This function initializes the `SMTools` utility with the specified operation,
    logs the start of the process, performs a login to the SUMAN system, and calls
    the `start_cleanup_profiles` functionality to perform cleanup operations.
    Depending on the execution result, the program will finalize with a successful
    or error state, logging appropriate messages.

    :global smt: Instance of the `smtools.SMTools` class for handling utility
        operations such as logging and program management.
    :type smt: smtools.SMTools
    """
    global smt
    smt = smtools.SMTools("cleanup_profiles")
    smt.log_info("Start")
    smt.suman_login()
    if start_cleanup_profiles():
        smt.close_program()
        smt.log_info("Finished successfully")
    else:
        smt.close_program(1)
        smt.log_error("Finished with errors")

if __name__ == "__main__":
    SystemExit(main())
