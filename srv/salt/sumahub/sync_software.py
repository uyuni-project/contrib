#!/usr/bin/python3
# compare parent_channel
#  not present on slave --> sync all channels
#  present on slave
#     compare child_channels
#       sync the missing
#
#


import os
import subprocess
import sys
import xmlrpc.client
import socket
import yaml

if not os.path.isfile(os.path.dirname(__file__) + "/sumahub.yaml"):
    print("ERROR: sumahub.yaml doesn't exist. Please create file")
    sys.exit(1)
else:
    with open(os.path.dirname(__file__) + '/sumahub.yaml') as h_cfg:
        sumahub = yaml.Loader(h_cfg).get_single_data()


def sync_channels(needed_base, url_master, url_slave):
    m_client = xmlrpc.client.Server(url_master, verbose=0)
    s_client = xmlrpc.client.Server(url_slave, verbose=0)
    m_session = m_client.auth.login(sumahub['suman']['user'], sumahub['suman']['password'])
    s_session = s_client.auth.login(sumahub['suman']['user'], sumahub['suman']['password'])

    for base in needed_base:
        m_channels = []
        try:
            m_children_raw = m_client.channel.software.listChildren(m_session, base)
        except:
            print("Basechannel {} does not exist on Master".format(base))
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
            sync = ["mgr-inter-sync"]
            for channel in channels:
                sync.append("-c")
                sync.append(channel)
            subprocess.run(sync)


def get_needed_base_channels(hub_slave):
    needed = []
    for channel in sumahub['all']['basechannels']:
        needed.append(channel)

    try:
        for channel in sumahub[hub_slave]['basechannels']:
            needed.append(channel)
    except:
        print("no specific channels for this hub slave")
    return needed


def main():
    if len(sys.argv) != 1:
        print("Usage: register_master.py")
        sys.exit(1)
    hub_slave = socket.getfqdn()

    manager_url_slave = "not set"
    for slave in sumahub['suman']['hubslaves']:
        if hub_slave == slave:
            manager_url_slave = "http://{}/rpc/api".format(hub_slave)
            break
    if manager_url_slave == "not set":
        print("The given hubslave is not in sumahub.yaml. Aborting")
        sys.exit(1)

    manager_url_master = "http://{}/rpc/api".format(sumahub['suman']['hubmaster'])
    manager_url_slave = "http://{}/rpc/api".format(hub_slave)
    needed_base_channels = get_needed_base_channels(hub_slave)
    sync_channels(needed_base_channels, manager_url_master, manager_url_slave)


if __name__ == "__main__":
    SystemExit(main())
