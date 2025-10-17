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
import sys
from argparse import RawTextHelpFormatter

import smtools

__smt = None

def check_group_exist(group):
    """
    Check if a group exists in the system.

    The function uses the `smt.systemgroup_get_details` to verify if a
    specific group exists. If the group is found, it returns True;
    otherwise, it returns False.

    :param group: The name of the group to check.
    :type group: str
    :return: A boolean indicating whether the group exists.
    :rtype: bool
    """
    smt.log_debug("Start check_group_exist")
    result = smt.systemgroup_get_details(group, False)
    if not result:
        return False
    smt.log_debug("Finished check_group_exist")
    return True

def add_remove_systems(group, hosts, add=True):
    """
    Adds or removes systems from a system group based on the specified mode.

    This function interfaces with the `smt.systemgroup_add_or_remove_systems`
    method to either add systems to or remove systems from a specified system
    group. The operation performed depends on the value of the `add` parameter.

    :param group: The name of the system group to which systems will be added or
                  from which they will be removed.
    :type group: str
    :param hosts: A list of systems (hosts) to add or remove from the group.
    :type hosts: list[str]
    :param add: A boolean flag indicating the mode of operation. If True, the
                function will add systems to the group. If False, it will remove
                systems from the group. Defaults to True.
    :type add: bool
    :return: None. The function performs the add/remove operation and does not
             return any value.
    :rtype: None
    """
    smt.log_debug("Start add_remove_systems")
    smt.systemgroup_add_or_remove_systems(group, hosts, add)
    smt.log_debug("Finished add_remove_systems")
    return

def read_file(file):
    """
    Read a file and extract server IDs from its lines.

    This function opens a given file, reads its lines and attempts to extract a
    server ID for each line using the `smt.get_server_id` method. If the server ID
    is found and valid, it appends the ID to a list which is later returned. If the
    file cannot be opened or if a line does not correspond to a valid server ID,
    appropriate error messages are logged.

    :param file: The path to the file to be read.
    :type file: str
    :return: A list of extracted server IDs from the lines of the file.
    :rtype: list[int]
    :raises IOError: If the file cannot be opened for reading.
    """
    smt.log_debug("Start read_file")
    export_file = None
    hosts = []
    try:
        export_file = open(file, 'r')
    except IOError:
        smt.fatal_error(f"Can't open file {file} for reading")
    for line in export_file:
        sid = smt.get_server_id(False, line)
        if sid == 0:
            smt.log_error(f"System {line} not found")
        else:
            hosts.append(sid)
    smt.log_debug("Finished read_file")
    return hosts

def get_systems(group):
    """
    Retrieves a list of system IDs for the provided system group. This function queries
    the minimal set of systems using the specified group, attempts to resolve each system's
    server ID, and accumulates the IDs for valid and found systems.

    :param group: The system group for which the systems need to be retrieved
    :type group: str
    :return: A list of system IDs that belong to the specified group
    :rtype: list
    """
    smt.log_debug("Start get_systems")
    hosts = []
    systems = smt.systemgroup_listsystemminimal(group)
    for system in systems:
        hosts.append(system.get('id'))
    smt.log_debug("Finished get_systems")
    return hosts

def export_group(group, file):
    """
    Exports the list of systems in a system group to a specified file. The function
    writes each system name contained within the given group to the provided file.
    If the file cannot be opened for writing, an error is logged, and the process
    is halted.

    :param group: The system group containing the list of systems to be exported.
    :type group: Any
    :param file: The path of the file where the system names will be written.
    :type file: str
    :return: None
    """
    smt.log_debug("Start export_group")
    export_file = None
    try:
        export_file = open(file, 'w')
    except IOError:
        smt.fatal_error("Can't open file %s for writing" % file)
    systems = smt.systemgroup_listsystemminimal(group)
    for system in systems:
        export_file.write(system.get('name') + '\n')
    smt.log_debug("Finished export_group")
    return


def start_sync(args):
    """
    Starts the synchronization process based on the provided arguments. The function performs
    various operations such as exporting, adding or removing systems, and reading host data
    from a file, depending on the configurations given in the `args` parameter.

    :param args: Contains the configuration options for the synchronization process. It includes
        attributes like `export`, `group`, `file`, `system`, `overwrite`, `add`, and `remove`. Each
        attribute determines a specific behavior or operation related to the synchronization.

    :return: None
    """
    smt.log_debug("Start sync")
    if args.export:
        export_group(args.group, args.file)
        return
    hosts = []
    if args.system:
        sid = smt.get_server_id(True, args.system)
        if sid == 0:
            smt.fatal_error("System {} not found".format(args.system))
        else:
            hosts.append(sid)
    if args.file:
        hosts = read_file(args.file)
    if args.file and args.overwrite:
        systems = get_systems(args.group)
        add_remove_systems(args.group, systems, False)
    if args.add:
        add_remove_systems(args.group, hosts, True)
        return
    if args.remove:
        add_remove_systems(args.group, hosts, False)
        return
    smt.log_debug("Finished sync")
    return

def check_arguments(args):
    """
    Check if the required arguments are passed.

    :param args:
    :return:
    """
    smt.log_debug("Start check_arguments")
    if not args.group:
        smt.log_error("Option --group not given and is required. Aborting operation")
        sys.exit(1)
    if args.export and not args.file:
        smt.log_error("Option --file not given and is required when using --export. Aborting operation")
        sys.exit(1)
    if (args.add or args.overwrite) and args.export:
        smt.log_error("Option --add/--overwrite and --export can not be used together. Aborting operation")
        sys.exit(1)
    if args.create and args.export:
        smt.log_warning("Option --create has no function when using with --export")
    if args.export:
        present = check_group_exist(args.group)
        if not present:
            smt.log_error(f"Group {args.group} not found. Aborting operation")
            sys.exit(1)
    if args.add or args.overwrite:
        present = check_group_exist(args.group)
        if args.create and not present:
            smt.systemgroup_create(args.group, args.group)
        if not args.create and not present:
            smt.log_error(f"Group {args.group} not found. Aborting operation")
            sys.exit(1)
    if args.system and args.overwrite:
        smt.log_warning("Option --overwrite has no function when using with --system")
    if args.file and args.system:
        smt.log_error("Option --file and --system can not be used together. Aborting operation")
        sys.exit(1)
    smt.log_debug("Finished check_arguments")

def main():
    """
    Main section
    """
    global smt
    smt = smtools.SMTools("manage_group")
    parser = argparse.ArgumentParser(formatter_class=RawTextHelpFormatter, description=('''\
         Usage:
         manage_group.py

         This script will either export the members of a system group to a file, or import the systems from a file 
         to a system group. When the option -c is given, the system group will be created is not existing during an 
         import.
               '''))
    parser.add_argument("-f", "--file",
                        help="File name of the file to export,add or remove.")
    parser.add_argument("-s", "--system",
                        help="System to be added or removed.")
    parser.add_argument("-g", "--group",
                        help="group to be managed. Mandatory.")
    parser.add_argument("-e", "--export", action="store_true", default=0,
                        help="Export the members of a system group to a file.")
    parser.add_argument("-a", "--add", action="store_true", default=0,
                        help="Add the members of a system group from a file.")
    parser.add_argument("-r", "--remove", action="store_true", default=0,
                        help="Remove the members of a system group from a file.")
    parser.add_argument("-c", "--create", action="store_true", default=0,
                        help="Create the system group if it doesn't exist by an import.")
    parser.add_argument("-o", "--overwrite", action="store_true", default=0,
                        help="On import, remove all that is currently present in system group.")

    parser.add_argument('--version', action='version', version='%(prog)s 1.0.0, August 18, 2025')
    args = parser.parse_args()
    smt.log_info("Start")
    smt.log_debug("Given options: {}".format(args))
    smt.suman_login()
    check_arguments(args)
    start_sync(args)
    smt.log_info("Finished manage_group")
    smt.close_program()


if __name__ == "__main__":
    SystemExit(main())
