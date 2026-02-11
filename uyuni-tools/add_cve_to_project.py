#!/usr/bin/env python3
#
# (c) 2025 SUSE Linux GmbH, Germany.
# GNU Public License. No warranty. No Support
# For question/suggestions/bugs mail: michael.brookhuis@suse.com
#
# Version: 2025-11-19
#
# Created by: SUSE Michael Brookhuis
#
# This script will add a CVE to the first stage of a project:
#  - With the option --update it will add the CVEs to the other environments of the project.
#  - When using the option --promote it will promote the other environments of the project.
#  - If no --update or --promote option is used, the script will only add the CVEs to the first environment of the project.
#
# Releases:
# 2025-11-17 M.Brookhuis - initial release.
# 2025-11-19 M.Brookhuis - added the options to also add packages and patches to the project
# 2025-12-09 M.Brookhuis - some more changes
#

import argparse
import sys
import time
from argparse import RawTextHelpFormatter

import smtools


def get_project_source_labels(project):
    """
    Retrieve the source channel labels for a given project.

    This function fetches all source entries associated with the specified
    project and extracts their channel labels into a list. The process
    includes logging debug start and finish messages.

    :param project: The project for which source channel labels are
        to be retrieved
    :type project: str
    :return: A list of channel labels extracted from the project sources
    :rtype: list
    """
    smt.log_debug("Start get_project_source_labels")
    project_sources = smt.contentmanagement_listprojectsources(project)
    channels = []
    for source in project_sources:
        channels.append(source.get('channelLabel'))
    smt.log_debug("Finished get_project_source_labels")
    return channels

def get_advisory_channels(errata):
    """
    Retrieve advisory channels for a given CVE.

    This function fetches the advisory channels linked to the provided CVE
    identifier and extracts their corresponding labels. It ensures that
    only the relevant labels are included in the result.

    :param errata: The CVE identifier for which advisory channels are to be retrieved.
    :type errata: str
    :return: A list of channel labels applicable to the provided CVE.
    :rtype: list
    """
    smt.log_debug("Start get_advisory_channels")
    adv_channels = smt.errata_applicabletochannels(errata, False)
    channels = []
    for source in adv_channels:
        channels.append(source.get('label'))
    smt.log_debug("Finished get_advisory_channels")
    return channels

def get_errata_packages(errata, arch_label):
    """
    Retrieve the list of package IDs associated with a specific CVE.

    This function fetches a list of packages related to a given CVE by querying
    the `smt.errata_listpackages` function. It then processes the result to
    extract and return only the package IDs.

    :param errata: The Common Vulnerabilities and Exposures (CVE) ID for which
        associated package IDs are to be retrieved.
    :type errata: str
    :return: A list of package IDs associated with the provided CVE.
    :rtype: list
    """
    smt.log_debug("Start get_cve_packages")
    cve_packages = smt.errata_listpackages(errata)
    packages = []
    for cve_package in cve_packages:
        if cve_package.get('arch_label') == arch_label:
            packages.append(cve_package.get('id'))
    smt.log_debug("Finished get_cve_packages")
    return packages

def get_all_packages(channel):
    """
    Retrieve all non-retracted packages from a given channel.

    The function fetches a list of packages associated with the provided channel
    using the `smt.channel_software_listallpackages` method. It processes the package details
    to exclude any retracted packages and formats the remaining package information
    into a list of dictionaries, where each dictionary contains the package ID and its
    formatted name. The formatted name is constructed from package name, version, release,
    and architecture label.

    :param channel: The name of the channel to retrieve packages from
    :type channel: str
    :return: A list of dictionaries with keys "id" and "name" for each non-retracted package
    :rtype: list[dict]
    """
    smt.log_debug("Start get_all_packages")
    packages_info = smt.channel_software_listallpackages(channel)
    packages = []
    for package in packages_info:

        if not package.get('retracted'):
            pack_info = {"id": package.get('id'),
                         "name": f"{package.get('name')}-{package.get('version')}-{package.get('release')}.{package.get('arch_label')}"}
            packages.append(pack_info)
    smt.log_debug("Finished get_all_packages")
    return packages

def do_add_packages(project, env, packages):
    """
    Adds specified packages to a project environment by identifying them in
    available project channels. If a package is not found, logs an error
    indicating the missing package.

    :param project: Name of the project to which the packages are being added
    :type project: str
    :param env: The environment within the project where the packages need
        to be added
    :type env: str
    :param packages: List of package names to be added to the project
    :type packages: list[str]
    :return: None
    """
    smt.log_debug("Start do_add_packages")
    project_channels = get_project_source_labels(project)
    packages_found = []
    for project_channel in project_channels:
        smt.log_debug(f"project_channel: {project_channel}")
        all_packages = get_all_packages(project_channel)
        add_package_ids = []
        for package in packages:
            for available_package in all_packages:
                if package == available_package.get('name'):
                    add_package_ids.append(available_package.get('id'))
                    packages_found.append(package)
        smt.channel_software_addpackages(f"{project}-{env}-{project_channel}", add_package_ids)
    for package in packages:
        if package not in packages_found:
            smt.log_error(f"package {package} not found in any channel. Not present or name is wrong. Skipping")
    smt.log_debug("Finished do_add_packages")

def add_errata_channels(project, env, advisory):
    """
    Adds CVE (Common Vulnerabilities and Exposures) to the appropriate software channels.

    This function determines which channels should include the given CVE by analyzing the project's source
    labels and advisory channels. It either skips channels where the CVE is already present or clones
    CVE-related information and adds the necessary packages to the respective channels. It also regenerates
    the YUM cache for updated channels.

    :param project: The project identifier or name to fetch source labels.
    :type project: str
    :param env: The environment name (e.g., production, staging) to distinguish channels.
    :type env: str
    :param advisory: The identifier for the Common Vulnerability and Exposure to be added to channels.
    :type advisory: str
    :return: None
    """
    smt.log_debug("Start add_cve_channels")
    project_channels = get_project_source_labels(project)
    advisory_channels = get_advisory_channels(advisory)
    for project_channel in project_channels:
            channel_to_clone = f"{project}-{env}-{project_channel}"
            if "x86_64" in project_channel:
                arch_label = "x86_64"
            elif "aarch64" in project_channel:
                arch_label = "aarch64"
            elif "ppc64le" in project_channel:
                arch_label = "ppc64le"
            elif "s390x" in project_channel:
                arch_label = "s390x"
            elif "amd64" in project_channel:
                arch_label = "x86_64"
            else:
                arch_label = "noarch"
            if channel_to_clone in advisory_channels:
                smt.log_info(f"CVE is already in channel {channel_to_clone}")
                continue
            if project_channel in advisory_channels:
                advisories= [advisory]
                results = smt.errata_clone(channel_to_clone, advisories)
                for result in results:
                    packages = get_errata_packages(result.get('advisory_name'), arch_label)
                    smt.channel_software_addpackages(channel_to_clone, packages)
                    smt.log_debug(f"packages: {packages}")
                smt.channel_software_regenerateyumcache(channel_to_clone)
                smt.log_info(f"CVE added to channel {channel_to_clone}")
    smt.log_debug("Finished add_cve_channels")

def do_add_errata(project_info, errata):
    """
    Adds errata (Common Vulnerabilities and Exposures) to specified project
    information by associating them with appropriate channels.

    This function iterates through the provided `errata` list and ties each
    CVEs (Common Vulnerabilities and Exposures) to its respective project
    label and first environment. It logs the process start and completion for
    debugging purposes.

    :param project_info: A dictionary containing project details, which includes
        the `label` (project label) and `firstEnvironment` (environment in which
        the project operates).
    :type project_info: dict
    :param errata: A list of CVE identifiers to be added to the project channels.
    :type errata: list
    :return: None
    """
    smt.log_debug("Start do_add_cves")
    for cve in errata:
        add_errata_channels(project_info.get('label'), project_info.get('firstEnvironment'), cve)
    smt.log_debug("Finished do_add_cves")

def perform_update(project, args):
    """
    Performs updates for a given project within specified environments. The function retrieves
    the project details and iterates through its environments. It processes CVEs and advisories
    if specified in the arguments and applies packages and advisories to the environment.

    :param project: The project for which updates need to be performed.
    :type project: Any

    :param args: Command-line arguments or parameters containing options for updates. This
                 can include CVEs, advisories, or packages to be added.
    :type args: Any

    :return: None
    """
    smt.log_debug("Start perform_update")
    project_details = smt.contentmanagement_listprojectenvironment(project)
    for environment_details in project_details:
        env = environment_details.get('label')
        cves = advs = []
        if args.cve:
            cves = get_cves(args.cve)
        if args.advisory:
            advs = get_advisory(args.advisory)
        advisories = advs + cves
        if args.package:
            do_add_packages(project, env, args.package)
        for advisory in advisories:
            add_errata_channels(project, env, advisory)
    smt.log_debug("Finished perform_update")

def perform_promote(project):
    """
    Perform a promotion operation within a content management system for the provided project. The function iterates
    through the project environments, identifies the source environment, and performs an update operation to promote
    changes from the source environment to the target environment.

    :param project: The project identifier or object being promoted, used to retrieve and process environment
                    details.
    :type project: Any
    :return: None
    """
    smt.log_debug("Start perform_promote")
    project_details = smt.contentmanagement_listprojectenvironment(project)
    for environment_details in project_details:
        try:
            source_env = environment_details.get('previousEnvironmentLabel')
        except KeyError:
            continue
        else:
            if source_env:
                target_env = environment_details.get('label')
                promote_environment(project, source_env, target_env)
    smt.log_debug("Finished perform_promote")

def sync_completed(env, project, wait):
    """
    Checks the synchronization status of a specified project environment and waits if directed.

    This function continuously checks the status of a given environment within a project until
    it determines that the synchronization process is complete. If the environment is in a "building"
    or "generating_repodata" state, and the wait parameter is True, the function will periodically
    check the environment's status. It returns True if the environment is successfully built, or
    returns False if the environment has never been built, failed to build, or is still building
    and the wait parameter is False.

    :param env: The label of the environment to be checked.
    :type env: str
    :param project: The identifier or name of the project the environment belongs to.
    :type project: str
    :param wait: A boolean flag to specify whether to wait (with periodic checks) if the environment
                 is still in progress ("building" or "generating_repodata").
    :type wait: bool
    :return: Returns True if the environment is successfully built; False otherwise.
    :rtype: bool
    """
    smt.log_debug("Start sync_completed")
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
                    smt.log_debug(f"environment {env} still being build. Waiting")
                    time.sleep(30)
                else:
                    smt.log_error(f"for environment {env} building is still in progress and option wait is False.")
                    return False

def promote_environment(project, source_env, target_env):
    """
    Updates the environment by promoting the project from a source environment to a
    target environment if the source environment is synchronized successfully. Logs
    debug messages at the beginning and end of the operation. Handles fatal errors
    if synchronization is not ready.

    :param project: The project name being updated
    :type project: str
    :param source_env: The source environment from which the project is promoted
    :type source_env: str
    :param target_env: The target environment to which the project is promoted
    :type target_env: str
    :return: None
    """
    smt.log_debug("Start update_environment")
    smt.log_info(f"promoting project {project} from {source_env} to {target_env}")
    smt.contentmanagement_promoteproject(project, source_env)
    sync_completed(target_env, project, True)
    smt.log_debug("Finished update_environment")

def get_advisory(advisory_list):
    """
    Retrieves a list of valid advisories from the provided advisory identifiers.

    This function takes a list of advisory identifiers, checks their details,
    and filters out the invalid ones. It performs this by utilizing an external
    method to fetch detailed information about each advisory. If details are
    successfully retrieved for an advisory, it is considered valid and appended
    to the resulting list. Otherwise, a warning is logged, and the advisory is
    skipped.

    :param advisory_list: A list of advisory identifiers to be validated.
    :type advisory_list: list
    :return: A list of valid advisory identifiers for which details were found.
    :rtype: list
    """
    smt.log_debug("Start get_advisory")
    advisories = []
    for advisory in advisory_list:
        advisory_info = smt.errata_getdetails(advisory,False)
        if advisory_info:
            advisories.append(advisory)
        else:
            smt.log_warning(f"Advisory {advisory} doesn't exists. Skipping")
    return advisories

def get_cves(cve_list):
    """
    Retrieves a list of advisory names associated with the provided list of CVEs. Each CVE is queried
    to gather associated advisories, and the advisory names are appended to the result. If no valid
    advisory names are found, the operation is aborted with an error.

    :param cve_list: List of CVE identifiers to search for associated advisories
    :type cve_list: list
    :return: List of advisory names found for the CVEs
    :rtype: list
    """
    smt.log_debug("Start get_cves")
    cves = []
    for cve in cve_list:
        cve_infos = smt.errata_findbycve(cve,False)
        if cve_infos:
            for cve_info in cve_infos:
                cves.append(cve_info.get("advisory_name"))
        else:
            smt.log_warning(f"CVE {cve} doesn't exists. Skipping")
    if cves:
        smt.log_debug("Finished get_cves")
        return cves
    else:
        smt.log_error(f"No valid CVEs found. Aborting operation")
        sys.exit(1)

def check_arguments(args):
    """
    Checks the validity of the input arguments and ensures required conditions are met.

    :param args: The parsed arguments provided by the user (e.g., via command line).
    :type args: Namespace
    :return: A boolean indicating whether the specified project exists.
    :rtype: bool
    """
    smt.log_debug("Start check_arguments")

    # check if the project exists
    project_present = smt.contentmanagement_lookupproject(args.project)
    if not project_present:
        smt.log_error(f"Project {args.project} doesn't exists. Aborting operation")
        sys.exit(1)
    if args.promote and args.update:
        smt.log_error(f"The options --promote and --update can not be used together. Aborting operation")
        sys.exit(1)
    if not args.cve and not args.advisory and not args.package:
        smt.log_error(f"At least on of the options --cve, --advisory or --package has to be given. Aborting operation")
        sys.exit(1)
    smt.log_debug("Finished check_arguments")
    # check if CVE exists
    return project_present


def main():
    """
    Main entry point for the script `add_cve_to_project.py`.

    This script facilitates adding a CVE (Common Vulnerabilities and Exposures) to the
    first stage of a specified project. It provides options to include advisories,
    packages, and additional configurations such as updating or promoting all other
    environments of the project.

    :raises SystemExit: Raised when parsing invalid arguments or when help/version
        is requested.
    :raises Exception: Raised if any internal process (logging in, updating, or
        promoting the project) encounters an error.

    :param args Namespace: Parsed command-line arguments that include project name,
        CVEs, advisories, packages, update flag, and promote flag.

    :return: None
    """
    global smt
    smt = smtools.SMTools("add_cve_to_project")
    parser = argparse.ArgumentParser(formatter_class=RawTextHelpFormatter, description=('''\
         Usage:
         add_cve_to_project.py

         This script will add a CVE to the first stage of a project.

               '''))
    parser.add_argument("-p", "--project", help="name of project where the CVE has to be added",
                        required=True)
    parser.add_argument("-c", "--cve", action="append",
                        help="The CVE Number. This option can be used multiple times")
    parser.add_argument("-a", "--advisory", action="append",
                        help="Add an advisory. This option can be used multiple times")
    parser.add_argument("-g", "--package", action="append",
                        help="Add a package. This option can be used multiple times")
    parser.add_argument("-u", "--update", action="store_true", default=0,
                        help="Update all other environments of the project")
    parser.add_argument("-r", "--promote", action="store_true", default=0,
                        help="Promote all other environments of the project")
    parser.add_argument('--version', action='version', version='%(prog)s 1.0.2, December 8, 2025')
    args = parser.parse_args()
    smt.log_info("Start")
    smt.log_debug("Given options: {}".format(args))
    smt.suman_login()
    project_info = check_arguments(args)
    if args.update:
        perform_update(args.project, args)
    else:
        cves = advs = []
        if args.cve:
            cves = get_cves(args.cve)
        if args.advisory:
            advs = get_advisory(args.advisory)
        advisories = advs + cves
        if args.package:
            do_add_packages(project_info.get('label'), project_info.get('firstEnvironment'), args.package)
        if advisories:
            do_add_errata(project_info, advisories)
    if args.promote:
            perform_promote(args.project)
    smt.close_program()


if __name__ == "__main__":
    SystemExit(main())