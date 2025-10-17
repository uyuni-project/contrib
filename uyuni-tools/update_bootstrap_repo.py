#!/usr/bin/env python3
#
# (c) 2025 SUSE Linux GmbH, Germany.
# GNU Public License. No warranty. No Support
# For question/suggestions/bugs mail: michael.brookhuis@suse.com
#
# Version: 2025-08-18
#
# Created by: SUSE Michael Brookhuis
#
# This script will manage groups by importing or exporting them from/to a file.
#
# Releases:
# 2025-08-18 M.Brookhuis - initial release.
#

import argparse
import subprocess
from argparse import RawTextHelpFormatter

import smtools

__smt = None

def execute_command(cmd):
    """
    Executes a shell command.

    This function runs the provided shell command using the subprocess module
    and captures both stdout and stderr. The function ensures the command is
    executed in a shell environment and raises an exception if the command fails.

    :param cmd: The shell command to execute.
    :type cmd: str
    :return: The result of the subprocess execution containing stdout and stderr.
    :rtype: subprocess.CompletedProcess
    :raises subprocess.CalledProcessError: If the command execution fails.
    """
    result = None
    try:
        result = subprocess.run(cmd, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError as err:
        smt.log_error(f"Error executing command: {cmd}")
        smt.log_error(f"Error message: {err.stderr.decode('utf-8')}")
    return result

def get_distros():
    """
    Fetches the list of distributions available from the bootstrap repository.

    This function constructs a command by utilizing the configuration
    specified in smtools.CONFIGSM for the bootstrap repository, and executes it
    to retrieve the list of distributions. If the execution fails, error messages
    are logged. The command's standard output containing the list of distributions
    is decoded and returned.

    :raises RuntimeError: Raised if the command execution fails.

    :return: A string containing the list of distributions fetched from the
        bootstrap repository.
    :rtype: str
    """
    command = f"{smtools.CONFIGSM['bootstrap-repo']['command']} -l"
    result = execute_command(command)
    if result.returncode != 0:
        smt.log_error(f"Error executing command: {command}")
        smt.log_error(f"Error message: {result.stderr.decode('utf-8')}")
    return result.stdout.decode('utf-8')

def check_distros(distros, distro):
    """
    Check if a given distribution is present in the list of valid distributions.

    This function verifies whether a specified distribution exists in a provided set
    of distributions. If the distribution is not present, it logs an error message.

    :param distros: List of valid Linux distributions.
    :type distros: list
    :param distro: The specific Linux distribution to check.
    :type distro: str
    :return: True if the distribution is valid, otherwise False.
    :rtype: bool
    """
    if distro in distros:
        return True
    else:
        smt.log_error(f"Distro {distro} not valid")
        return False

def check_channel(channel):
    """
    Check if the provided channel exists and can be retrieved by the system.

    This function validates the existence of a channel by querying the system
    for its details. If the channel does not exist or cannot be found, it logs
    an error and returns False. Otherwise, it confirms the channel's validity
    and returns True.

    :param channel: The name or identifier of the channel to validate.
    :type channel: str
    :return: Returns True if the channel exists and can be successfully queried,
        otherwise returns False.
    :rtype: bool
    """
    if not smt.channel_software_getdetails(channel, True):
        smt.log_error(f"Channel {channel} not found")
        return False
    return True

def start_update():
    """
    Triggers the update process for specified distributions and channels by executing a
    command for each valid distribution and channel combination. It performs checks
    to ensure compatibility of the provided distributions and channels before executing
    the required commands. Logs success or failure for each operation.

    :raises KeyError: If required configuration keys are missing from the
        ``smtools.CONFIGSM`` dictionary.
    :raises AttributeError: If smt.log or related logging methods are incorrectly defined.
    """
    distros = get_distros()
    for dist, channel in smtools.CONFIGSM['bootstrap-repo']['repos'].items():
        smt.log_info(f"Updating {dist} with {channel}")
        if check_distros(distros, dist) and check_channel(channel):
            command_dist = f"/usr/bin/{smtools.CONFIGSM['bootstrap-repo']['command']} -c {dist} --with-parent-channel={channel}"
            result = execute_command(command_dist)
            if result.returncode == 0:
                smt.log.info("success")
            else:
                smt.log_error(f"Error updating {channel}")
                smt.log_error(f"Error message: {result.stderr.decode('utf-8')}")

def main():
    """
    This script provides functionality to update bootstrap repositories. It initializes
    the necessary tools and settings, parses the script arguments, and controls the
    execution flow for performing the update process. The repositories to be updated
    and corresponding configurations are specified within a configuration file.

    :return: None
    """
    global smt
    smt = smtools.SMTools("update_bootstrap_repo")
    parser = argparse.ArgumentParser(formatter_class=RawTextHelpFormatter, description=('''\
         Usage:
         update_bootstrap_repo.py

         This script will update the bootstrap repositories. Which repositories are updated with which channel 
         is defined in the config file. There are no parameters
               '''))
    smt.log_info("Start")
    smt.suman_login()
    start_update()
    smt.log_info("Finished update_bootstrap_repo")
    smt.close_program()


if __name__ == "__main__":
    SystemExit(main())
