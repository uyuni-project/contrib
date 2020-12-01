#!/usr/bin/python3
#
# (c) 2020 SUSE Linux GmbH, Germany.
# GNU Public License. No warranty. No Support (only from SUSE Consulting)
#
# Version: 2020-12-01
#
# Created by: SUSE Michael Brookhuis,
#
# Description: missing configuration channels will be created and existing updated.
#
# Releases:
# 2020-12-01 M.Brookhuis - initial release.
#
#


import logging
import os
import socket
import sys
import xmlrpc.client

import yaml

if not os.path.isfile(os.path.dirname(__file__) + "/sumahub.yaml"):
    print("ERROR: sumahub.yaml doesn't exist. Please create file")
    sys.exit(1)
else:
    with open(os.path.dirname(__file__) + '/sumahub.yaml') as h_cfg:
        sumahub = yaml.Loader(h_cfg).get_single_data()

if not os.path.exists("/var/log/rhn/sumahub"):
    os.makedirs("/var/log/rhn/sumahub")
log_name = "/var/log/rhn/sumahub/update_config_channels.log"

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


def sync_config(m_client, m_session, s_client, s_session, hub_slave):
    try:
        slave_configs = s_client.configchannel.listGlobals(s_session)
    except xmlrpc.client.Fault as err:
        log.warning("Unable to get a list of configuration channels on slave. Could be that there are none")
        log.warning("Error:\n{}".format(err))
    try:
        master_configs = m_client.configchannel.listGlobals(m_session)
    except xmlrpc.client.Fault as err:
        log.warning("Unable to get a list of configuration channels on master. Could be that there are none. Aborting")
        log.warning("Error:\n{}".format(err))
        return

    try:
        for channel in sumahub['all']['configchannels']:
            found = False
            for config in slave_configs:
                if channel == config.get('label'):
                    for m_config in master_configs:
                        if channel == m_config.get('label'):
                            update_configchannel(config, m_config, m_client, m_session, s_client, s_session)
                            found = True
                            break
            if not found:
                log.info("Creating channel {}".format(channel))
                # een aparte sectie maken. en kijken waarom channel general toch in deze else wordt gedaan.
                cinfo = m_client.configchannel.getDetails(m_session, channel)
                s_client.configchannel.create(s_session, cinfo.get('label'), cinfo.get('name'),
                                              cinfo.get('description'), "state")
                for m_config in master_configs:
                    if channel == m_config.get('label'):
                        create_configchannel(m_config, m_client, m_session, s_client, s_session)
                        break
    except:
        log.info("no global configchannels")

    try:
        for channel in sumahub[hub_slave]['configchannels']:
            found = False
            for config in slave_configs:
                if channel == config.get('label'):
                    for m_config in master_configs:
                        if channel == m_config.get('label'):
                            update_configchannel(config, m_config, m_client, m_session, s_client, s_session)
                            found = True
                            break
            if not found:
                log.info("Creating channel {}".format(channel))
                cinfo = m_client.configchannel.getDetails(m_session, channel)
                s_client.configchannel.create(s_session, cinfo.get('label'), cinfo.get('name'),
                                              cinfo.get('description'), "state")
                for m_config in master_configs:
                    if channel == m_config.get('label'):
                        create_configchannel(m_config, m_client, m_session, s_client, s_session)
                        break
    except:
        log.info("no slave configchannels")


def update_configchannel(s_channel, m_channel, m_client, m_session, s_client, s_session):
    try:
        m_files = m_client.configchannel.listFiles(m_session, m_channel.get('label'))
    except xmlrpc.client.Fault as err:
        log.warning(
            "Unable to get a list of configuration files for channel {} on master".format(m_channel.get('label')))
        log.warning("Error:\n{}".format(err))
        return
    try:
        s_files = s_client.configchannel.listFiles(s_session, s_channel.get('label'))
    except xmlrpc.client.Fault as err:
        log.warning(
            "Unable to get a list of configuration files for channel {} on slave".format(s_channel.get('label')))
        log.warning("Error:\n{}".format(err))
    for m_file in m_files:
        found = False
        for s_file in s_files:
            if m_file.get('path') == s_file.get('path'):
                try:
                    m_fileinfo = m_client.configchannel.lookupFileInfo(m_session, m_channel.get('label'),
                                                                       [m_file.get('path')])
                except xmlrpc.client.Fault as err:
                    log.warning("Unable to receive fileinfo from file on master: {}".m_file.get('path'))
                    log.warning("Error:\n{}".format(err))
                try:
                    s_fileinfo = s_client.configchannel.lookupFileInfo(s_session, s_channel.get('label'),
                                                                       [s_file.get('path')])
                except xmlrpc.client.Fault as err:
                    log.warning("Unable to receive fileinfo from file on master: {}".m_file.get('path'))
                    log.warning("Error:\n{}".format(err))
                for x in m_fileinfo:
                    for y in s_fileinfo:
                        if y.get('revision') == x.get('revision'):
                            log.info("Up-to-data file:  {}".format(m_file.get('path')))
                            break
                        else:
                            log.info("Updating file:  {} to revision {}".format(m_file.get('path'), x.get('revision')))
                            if m_file.get('type') == "sls":
                                try:
                                    s_client.configchannel.updateInitSls(s_session, s_channel.get('label'),
                                                                         {'contents': x.get('contents')})
                                except xmlrpc.client.Fault as err:
                                    log.warning("Unable to create file: init.sls")
                                    log.warning("Error:\n{}".format(err))
                            else:
                                try:
                                    s_client.configchannel.createOrUpdatePath(s_session, s_channel.get('label'),
                                                                              x.get('path'), False,
                                                                              {'revision': x.get('revision'),
                                                                               'contents': x.get('contents'),
                                                                               'owner': 'root', 'group': 'root',
                                                                               'permissions': '644',
                                                                               'macro-start-delimiter': '{|',
                                                                               'macro-end-delimiter': '|}',
                                                                               'binary': False})
                                except xmlrpc.client.Fault as err:
                                    log.warning("Unable to create file: {}".format(m_file.get('path')))
                                    log.warning("Error:\n{}".format(err))
                found = True
                break
        if not found:
            try:
                m_fileinfo = m_client.configchannel.lookupFileInfo(m_session, m_channel.get('label'),
                                                                   [m_file.get('path')])
            except xmlrpc.client.Fault as err:
                log.warning("Unable to receive fileinfo from file on master: {}".m_file.get('path'))
                log.warning("Error:\n{}".format(err))
            if m_file.get('type') == "sls":
                try:
                    s_client.configchannel.updateInitSls(s_session, s_channel.get('label'),
                                                         {'contents': m_fileinfo[0].get('contents')})
                except xmlrpc.client.Fault as err:
                    log.warning("Unable to create file: init.sls")
                    log.warning("Error:\n{}".format(err))
            else:
                try:
                    s_client.configchannel.createOrUpdatePath(s_session, s_channel.get('label'),
                                                              x.get('path'), False,
                                                              {'revision': m_fileinfo[0].get('revision'),
                                                               'contents': m_fileinfo[0].get('contents'),
                                                               'owner': 'root', 'group': 'root',
                                                               'permissions': '644',
                                                               'macro-start-delimiter': '{|',
                                                               'macro-end-delimiter': '|}',
                                                               'binary': False})
                except xmlrpc.client.Fault as err:
                    log.warning("Unable to create file: {}".format(m_file.get('path')))
                    log.warning("Error:\n{}".format(err))


def create_configchannel(m_channel, m_client, m_session, s_client, s_session):
    try:
        m_files = m_client.configchannel.listFiles(m_session, m_channel.get('label'))
    except xmlrpc.client.Fault as err:
        log.warning("Unable to get a list of configuration files for channel {}".format(m_channel.get('label')))
        log.warning("Error:\n{}".format(err))
        return
    for m_file in m_files:
        try:
            m_fileinfo = m_client.configchannel.lookupFileInfo(m_session, m_channel.get('label'), [m_file.get('path')])
        except xmlrpc.client.Fault as err:
            log.warning("Unable to receive fileinfo from file: {}".m_file.get('path'))
            log.warning("Error:\n{}".format(err))
        if m_file.get('type') == "sls":
            log.info("Creating file: init.sls")
            try:
                s_client.configchannel.updateInitSls(s_session, m_channel.get('label'),
                                                     {'contents': m_fileinfo[0].get('contents')})
            except xmlrpc.client.Fault as err:
                log.warning("Unable to create file: init.sls")
                log.warning("Error:\n{}".format(err))
        else:
            log.info("Creating file: {}".format(m_file.get('path')))
            print(m_fileinfo[0].get('revision'))
            try:
                s_client.configchannel.createOrUpdatePath(s_session, m_channel.get('label'), m_file.get('path'), False,
                                                          {'revision': m_fileinfo[0].get('revision'),
                                                           'contents': m_fileinfo[0].get('contents'),
                                                           'owner': 'root', 'group': 'root', 'permissions': '644',
                                                           'macro-start-delimiter': '{|', 'macro-end-delimiter': '|}',
                                                           'binary': False})
            except xmlrpc.client.Fault as err:
                log.warning("Unable to create file: {}".format(m_file.get('path')))
                log.warning("Error:\n{}".format(err))


def main():
    log.info("start")
    if len(sys.argv) != 1:
        log.fatal("Usage: register_master.py")
        sys.exit(1)
    hub_slave = socket.getfqdn()

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
    sync_config(m_client, m_session, s_client, s_session, hub_slave)
    log.info("finished")


if __name__ == "__main__":
    SystemExit(main())
