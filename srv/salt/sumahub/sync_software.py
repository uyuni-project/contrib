#!/usr/bin/python3
#
# (c) 2020 SUSE Linux GmbH, Germany.
# GNU Public License. No warranty. No Support (only from SUSE Consulting)
#
# Version: 2020-12-01
#
# Created by: SUSE Michael Brookhuis,
#
# Description:
# compare parent_channel
#  not present on slave --> sync all channels
#  present on slave
#     compare child_channels
#       sync the missing
#
# Releases:
# 2020-12-01 M.Brookhuis - initial release.
#

import os
import subprocess
import sys
import xmlrpc.client
import socket
import yaml
import logging

if not os.path.isfile(os.path.dirname(__file__) + "/sumahub.yaml"):
    print("ERROR: sumahub.yaml doesn't exist. Please create file")
    sys.exit(1)
else:
    with open(os.path.dirname(__file__) + '/sumahub.yaml') as h_cfg:
        sumahub = yaml.Loader(h_cfg).get_single_data()

if not os.path.exists("/var/log/rhn/sumahub"):
    os.makedirs("/var/log/rhn/sumahub")
log_name = "/var/log/rhn/sumahub/sync_software.log"

formatter = logging.Formatter('%(asctime)s |  %(levelname)s | %(message)s', '%d-%m-%Y %H:%M:%S')
fh = logging.FileHandler(log_name, 'a')
fh.setLevel("DEBUG")
fh.setFormatter(formatter)
console = logging.StreamHandler()
console.setLevel("DEBUG")
console.setFormatter(formatter)
log = logging.getLogger('')
log.setLevel(logging.DEBUG)
log.addHandler(console)
log.addHandler(fh)


def sync_channels(needed_base, m_client, m_session, s_client, s_session):
    for base in needed_base:
        m_channels = []
        try:
            m_children_raw = m_client.channel.software.listChildren(m_session, base)
        except:
            log.warning("Basechannel {} does not exist on Master".format(base))
            break
        m_channels.append(base)
        for channel in m_children_raw:
            m_channels.append(channel.get('label'))
        try:
            s_children_raw = s_client.channel.software.listChildren(s_session, base)
        except:
            s_channels = []
        else:
            s_channels = [base]

        if s_channels:
            for channel in s_children_raw:
                s_channels.append(channel.get('label'))
        channels = []
        if s_channels:
            for x in m_channels:
                if x in s_channels:
                    continue
                else:
                    channels.append(x)
        else:
            channels = m_channels
        if channels:
            log.info("Adding the following channels: {}".format(channels))
            sync = ["mgr-inter-sync"]
            for channel in channels:
                sync.append("-c")
                sync.append(channel)
            subprocess.run(sync)


def get_needed_base_channels(hub_slave, m_client, m_session):
    # get all base channels
    try:
        all_channels = m_client.channel.listSoftwareChannels(m_session)
    except xmlrpc.client.Fault as err:
        log.fatal("Unable to connect SUSE Manager {} to login to get a list of all software channels".format(
            sumahub['suman']['hubmaster']))
        log.fatal("Error:\n{}".format(err))
        sys.exit(1)
    abcl = []
    for c in all_channels:
        if not c.get('parent_label'):
            abcl.append(c.get('label'))
    # defined basechannels
    needed = []
    try:
        for channel in sumahub['all']['basechannels']:
            needed.append(channel)
        try:
            for channel in sumahub[hub_slave]['basechannels']:
                needed.append(channel)
        except:
            log.info("no specific channels for this hub slave")
    except:
        log.info("no general channels defined")
    # defined projects
    try:
        for project in sumahub['all']['projects']:
            for channel in abcl:
                if channel.startswith(project):
                    needed.append(channel)
        try:
            for project in sumahub[hub_slave]['projects']:
                for channel in abcl:
                    if channel.startswith(project):
                        needed.append(channel)
        except:
            log.info("no specific projects for this hub slave")
    except:
        log.info("no general projects defined")
    return needed


def main():
    if len(sys.argv) != 1:
        print("Usage: register_master.py")
        log.error("Usage: register_master.py")
        sys.exit(1)
    hub_slave = socket.getfqdn()
    log.info("start")
    manager_url_slave = "http://{}/rpc/api".format(hub_slave)
    manager_url_master = "http://{}/rpc/api".format(sumahub['suman']['hubmaster'])

    try:
        m_client = xmlrpc.client.Server(manager_url_master)
    except xmlrpc.client.Fault as err:
        log.fatal("Unable to login to SUSE Manager server {}".format(sumahub['suman']['hubmaster']))
        log.fatal("Error:\n{}".format(err))
        sys.exit(1)
    try:
        s_client = xmlrpc.client.Server(manager_url_slave)
    except xmlrpc.client.Fault as err:
        log.fatal("Unable to login to SUSE Manager server {}".format(hub_slave))
        log.fatal("Error:\n{}".format(err))
        sys.exit(1)
    try:
        m_session = m_client.auth.login(sumahub['suman']['user'], sumahub['suman']['password'])
    except xmlrpc.client.Fault as err:
        log.fatal("Unable to login to SUSE Manager server {}".format(sumahub['suman']['hubmaster']))
        log.fatal("Error:\n{}".format(err))
        sys.exit(1)
    try:
        s_session = s_client.auth.login(sumahub['suman']['user'], sumahub['suman']['password'])
    except xmlrpc.client.Fault as err:
        log.fatal("Unable to login to SUSE Manager server {}".format(hub_slave))
        log.fatal("Error:\n{}".format(err))
        sys.exit(1)

    needed_base_channels = get_needed_base_channels(hub_slave, m_client, m_session)
    sync_channels(needed_base_channels, m_client, m_session, s_client, s_session)
    log.info("finished")


if __name__ == "__main__":
    SystemExit(main())
