#!/usr/bin/env python3
#
# create_repos.py
#
# (c) 2017 SUSE Linux GmbH, Germany.
# GNU Public License. No warranty. No Support
# For question/suggestions/bugs mail: michael.brookhuis@suse.com
#
# Version: 2020-06-30
#
# Created by: SUSE Michael Brookhuis
#
# This script will clone the given channel.
#
# Releases:
# 2020-01-30 M.Brookhuis - initial release.
# 2020-06-30 M.Brookhuis - Version 2.
#                        - changed logging
#                        - moved api calls to smtools.py

#
"""This program will create the needed channels and repositories"""

import argparse
from argparse import RawTextHelpFormatter
import os
import xmlrpc.client
import smtools

__smt = None


def check_present(wanted, item_list):
    """
    check if item is present in the list
    """
    for item in item_list:
        if item.get('description') == wanted:
            return True
    return False


def do_repo_config(repo_config, sync):
    """
    Evaluate the repo config
    """
    all_crypto_keys = smt.kickstart_keys_listallkeys()
    for repo, repo_info in repo_config['repository'].items():
        # check if key, cert, ca exist
        if repo_info['key']:
            if not check_present(repo_info['key'], all_crypto_keys):
                smt.minor_error("The given key {} for repository {} doesn't exist. Continue with next item.".format(repo_info['key'], repo))
                continue
        if repo_info['ca']:
            if not check_present(repo_info['ca'], all_crypto_keys):
                smt.minor_error(
                    "The given ca {} for repository {} doesn't skip. Continue with next item.".format(repo_info['ca'], repo))
                continue
        if repo_info['cert']:
            if not check_present(repo_info['cert'], all_crypto_keys):
                smt.minor_error("The given key {} for repository {} doesn't skip. Continue with next item.".format(repo_info['cert'], repo))
                continue
        # check if repository exist
        if smt.channel_software_getrepodetails(repo, True):
            smt.minor_error("The repository {} already exists. Skipping to next".format(repo))
            continue
        else:
            smt.log_info("Repository {} will be created if channel is not present".format(repo))
        # check if channel exist
        if smt.channel_software_getdetails(repo):
            smt.minor_error("The channel {} already exists. Skipping to next".format(repo))
            continue
        else:
            smt.log_info("Channel {} will be created if parent channel is present".format(repo))
        # check if parent exist
        if not smt.channel_software_getdetails(repo_info['parent']):
            smt.minor_error("Parent channel not present. No repository {} or channel {} will be created".format(repo, repo))
            continue
        # create repo
        if repo_info['key']:
            if not smt.channel_software_createrepo_cert(repo, repo_info['type'], repo_info['url'], repo_info['ca'], repo_info['cert'], repo_info['key'], True):
                continue
        else:
            if not smt.channel_software_createrepo(repo, repo_info['type'], repo_info['url'], True):
                continue

        # create channel
        smt.channel_software_create(repo, repo, repo, "channel-x86_64", repo_info['parent'])
        smt.channel_software_associaterepo(repo, repo)
        smt.channel_software_syncrepo(repo, repo_info['schedule'])
        if sync:
            try:
                smt.client.channel.software.syncRepo(smt.session, repo)
            except xmlrpc.client.Fault:
                smt.log_error("Unable to sync repository {}".format(repo))
            else:
                smt.log_info("Sync of repository {} started.".format(repo))
        smt.log_info("Repositoriy {} and Channel {} created".format(repo, repo))
        smt.log_info(" ")


def main():
    """
    Main Function
    """
    global smt
    smt = smtools.SMTools("create_repos")
    parser = argparse.ArgumentParser(formatter_class=RawTextHelpFormatter, description=('''\
         Usage:
         create_repos.py
               '''))
    parser.add_argument("-r", "--repos", help="file containing the reposotiries to be created")
    parser.add_argument("-s", '--sync', action="store_true", default=0,
                        help="Synchronizechannel after creation. Default off")
    parser.add_argument('--version', action='version', version='%(prog)s 2.0.0, June 30, 2020')
    args = parser.parse_args()
    if not args.repos:
        smt = smtools.SMTools("create_repos")
        smt.log_error("The option --repos is mandatory. Exiting script")
        smt.exit_program(1)
    else:
        if not os.path.exists(args.repos):
            smt = smtools.SMTools("create_repos")
            smt.log_error("The given file {} doesn't exist.".format(args.repos))
            smt.exit_program(1)
        else:
            with open(args.repos) as repo_cfg:
                repo_config = smtools.load_yaml(repo_cfg)
    smt.suman_login()
    do_repo_config(repo_config, args.sync)
    smt.close_program()


if __name__ == "__main__":
    SystemExit(main())
