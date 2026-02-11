#!/usr/bin/env python3
#
# (c) 2025 SUSE Linux GmbH, Germany.
# GNU Public License. No warranty. No Support
# For question/suggestions/bugs mail: michael.brookhuis@suse.com
#
# Version: 2026-01-05
#
# Created by: SUSE Michael Brookhuis
#
# This script will import data from a file to mlm.
#
# Releases:
# 2026-01-05 M.Brookhuis - initial release.
#

import argparse
import re
import sys

import smtools

def read_file(input_file, get_lines=False):
    """
    Reads content from a file and returns it either as a string or as a list of lines.

    This function provides functionality to read from a file. It can either return the entire content
    of the file as a single string or, if the `get_lines` flag is set to True, return the content as
    a list of lines. If the file is not found, a fatal error is logged, and an empty list is returned.

    :param input_file: The path to the file from which the content will be read.
    :type input_file: str
    :param get_lines: Optional flag to indicate if the content should be returned as a list of lines.
                      If False or not provided, the full content will be returned as a string.
                      Defaults to False.
    :type get_lines: bool
    :return: The content of the file. Returns a string if `get_lines` is False, or a list of strings
             (each representing a line) if `get_lines` is True. If the file is not found, an empty
             list is returned.
    :rtype: str | list[str]
    """
    try:
        with open(input_file, 'r') as f:
            if get_lines:
                return f.readlines()
            else:
                return f.read()
    except FileNotFoundError:
        smt.fatal_error(f"Error: Input file not found at {input_file}")
        return []

def get_repos(content):
    """
    Parses repository information from the given content and returns a list of dictionaries
    representing each repository. The content is expected to include repository details in
    a predefined key-value format. Labels such as "Repository Label", "Repository URL",
    and others provide details about specific repositories.

    Key-value pairs are mapped to corresponding keys in the resulting dictionaries using a
    predefined mapping. Empty lines in the content reset the state, and each repository's
    values are aggregated until a new label is encountered or the content ends.

    :param content: List of strings containing repository data in key-value format.
    :type content: list of str
    :return: A list of dictionaries, each representing a repository with mapped values.
    :rtype: list of dict
    """
    parsed_repos = []
    current_repo = None
    state = 'KEY_VALUE'
    key_map = {
        "Repository Label": "label",
        "Repository URL": "url",
        "Repository Type": "type",
        "Repository SSL Ca Certificate": "sslCaCert",
        "Repository SSL Client Certificate": "sslCliCert",
        "Repository SSL Client Key": "sslCliKey",
    }
    for line in content:
        line = line.strip()
        if not line and current_repo:
            state = 'KEY_VALUE'
            continue
        if state == 'KEY_VALUE':
            match = re.match(r"(\w+\s?\w+\s?\w+\s?\w+):\s*(.*)", line)
            if match:
                key = match.group(1).strip()
                value = match.group(2).strip()
                if key == "Repository Label":
                    if current_repo:
                        parsed_repos.append(current_repo)
                    current_repo = {key_map[key]: value}
                elif key in key_map and current_repo:
                    current_repo[key_map[key]] = value
    if current_repo:
        parsed_repos.append(current_repo)
    return parsed_repos

def create_repo(repo):
    """
    Creates a repository based on the provided configuration.

    This function initializes a repository using the given parameters in the
    `repo` dictionary. Depending on whether an SSL CA certificate is specified
    or not, it invokes the appropriate method to create the repository with
    or without SSL certificates.

    :param repo: A dictionary containing repository details. Must include
        'label', 'type', 'url', and optionally SSL-related keys such as
        'sslCaCert', 'sslCliCert', and 'sslCliKey'.
    :type repo: dict
    :return: None
    """
    smt.log_info(f"Creating repo: {repo['label']}")
    if repo['sslCaCert'] == "None":
        smt.channel_software_createrepo(repo['label'], repo['type'], repo['url'],True)
    else:
        smt.channel_software_createrepo_cert(repo['label'], repo['type'], repo['url'], repo['sslCaCert'], repo['sslCliCert'], repo['sslCliKey'],True)

def process_repos(input_file):
    """
    Processes a list of repositories from an input file.

    This function reads the content of the given input file, extracts a list of
    repository details, and creates repositories based on the extracted information.

    :param input_file: The file path to the input file containing repository details
    :type input_file: str
    :return: None
    """
    content = read_file(input_file, True)
    repos = get_repos(content)
    for repo in repos:
        create_repo(repo)

def get_users(content):
    """
    Parses user data from a given content, extracting user details, roles, and assigned groups.

    The function parses a list of strings containing user details in a specific format. It identifies
    the different sections such as key-value pairs, roles, and groups, and constructs a list of
    dictionaries for each user with their respective information. The structure of the parsed user
    data includes keys for 'login', 'firstName', 'lastName', 'email', 'roles', and 'groups'.

    :param content: List of strings representing user data to be parsed.
    :type content: list[str]
    :return: A list of dictionaries, each representing a user and their details including roles
             and groups.
    :rtype: list[dict]
    """
    parsed_users = []
    current_user = None
    state = 'KEY_VALUE'
    key_map = {
        "Username": "login",
        "First Name": "firstName",
        "Last Name": "lastName",
        "Email Address": "email",
    }
    for line in content:
        line = line.strip()
        if not line and current_user:
            state = 'KEY_VALUE'
            continue
        if line == "Roles":
            state = 'ROLES_LIST'
            continue
        if line == "Assigned Groups":
            state = 'GROUPS_LIST'
            continue
        if "-----" in line:
            continue
        if state == 'KEY_VALUE':
            match = re.match(r"(\w+\s?\w+):\s*(.*)", line)
            if match:
                key = match.group(1).strip()
                value = match.group(2).strip()
                if key == "Username":
                    if current_user:
                        parsed_users.append(current_user)
                    current_user = {'roles': [], 'groups': [], key_map[key]: value}
                elif key in key_map and current_user:
                    current_user[key_map[key]] = value
        elif state == 'ROLES_LIST':
            if line and current_user:
                current_user['roles'].append(line)
        elif state == 'GROUPS_LIST':
            if line and current_user:
                current_user['groups'].append(line)
    if current_user:
        parsed_users.append(current_user)
    return parsed_users

def create_user(user):
    """
    Creates a user in the system with the specified details.

    This function logs the creation, adds the user with the provided login, first name,
    last name, email, a default password, and disables immediate activation. It also
    assigns the user to the specified roles and system groups.

    :param user: A dictionary containing user details:
                 - login: str - The login name of the user.
                 - firstName: str - The first name of the user.
                 - lastName: str - The last name of the user.
                 - email: str - The email address of the user.
                 - roles: list[str] - A list of roles to assign to the user.
                 - groups: list[str] - A list of system groups to assign to the user.
    :return: None
    """
    smt.log_info(f"Creating user: {user['login']}")
    smt.user_create(user['login'], user['firstName'], user['lastName'], user['email'], "Passw0rd", False)
    for role in user['roles']:
        smt.user_add_role(user['login'], role)
    smt.user_add_assigned_system_groups(user['login'], user['groups'])

def process_user(input_file):
    """
    Processes user data from a file and creates user entries accordingly.

    This function reads content from the provided input file, retrieves user data,
    and creates user profiles based on the extracted information. The input file
    is expected to be formatted properly to ensure successful processing.

    :param input_file: The path to the input file containing user data.
    :type input_file: str
    :return: None
    """
    content = read_file(input_file, True)
    users = get_users(content)
    for user in users:
        create_user(user)

def process_group(input_file):
    """
    Processes a group configuration from an input file and creates system groups
    based on the parsed data.

    This function reads lines from the given file, extracts system group `Name`
    and `Description` information, and uses these attributes to create system
    groups. Each group is created when both a name and description have been
    identified.

    :param input_file: Path to the file containing the group configuration
    :type input_file: str
    :return: None
    """
    lines = read_file(input_file, True)

    name = description = ""
    for line in lines:
        line = line.strip()
        if line.startswith("Name"):
            name = line.split(":")[1].strip()
        if line.startswith("Description"):
            description = line.split(":")[1].strip()
        if name and description:
            smt.systemgroup_create(name, description, False)
            name = description = ""


def parse_arguments(args):
    """
    Parses command-line arguments using argparse.
    group, user, and repo are mutually exclusive, and one is required.
    an inputfile is also required.
    """
    parser = argparse.ArgumentParser(
        description="This script will import data from a file to mlm. Valid options are user, repo, group."
    )

    parser.add_argument('--version', action='version', version='%(prog)s 1.0.0, January 5, 2026')

    # 1. Add the required inputfile argument
    parser.add_argument(
        '-f', '--file', type=str, required=True,
        help='The required input file path.'
    )

    group_type = parser.add_mutually_exclusive_group(required=True)
    group_type.add_argument(
        '-g', '--group', action='store_true', default=False,
        help='Operate on a group. Create input file with:'
             '\n for x in $(spacecmd -q -- group_list);do spacecmd -q -- group_details $x;echo;done > groups.txt'
             '\n(mutually exclusive with --user and --repo).')
    group_type.add_argument(
        '-u', '--user', action='store_true', default=False,
        help='Operate on a user. Create input file with:'
             '\n for x in $(spacecmd -q -- user_list);do spacecmd -q -- user_details $x;echo;done > users.txt'
             '\n(mutually exclusive with --user and --repo).')
    group_type.add_argument(
         '-r', '--repo', action='store_true', default=False,
        help='Operate on a repository. Create input file with:'
             '\n for x in $(spacecmd -q -- repo_list);do spacecmd -q -- repo_details $x;echo;done > repos.txt'
             '\n(mutually exclusive with --user and --group).')

    return parser.parse_args(args)

# Example usage:
if __name__ == '__main__':
    # Parse the arguments
    global smt
    smt = smtools.SMTools("import_suma_data")
    smt.log_info("Start")

    smt.suman_login()
    try:
        args = parse_arguments(sys.argv[1:])
        smt.log_debug("Given options: {}".format(args))
        if args.group:
            smt.log_info("Operation Type: Group")
            process_group(args.file)
        elif args.user:
            smt.log_info("Operation Type: User")
            process_user(args.file)
        elif args.repo:
            smt.log_info("Operation Type: Repo")
            process_repos(args.file)
    except SystemExit as e:
        if e.code != 0:
            print("\nError encountered.")
    smt.close_program()
