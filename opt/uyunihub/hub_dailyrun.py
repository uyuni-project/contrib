#!/usr/bin/python3
#
# (c) 2020 SUSE Linux GmbH, Germany.
# GNU Public License. No warranty. No Support
#
# Version: 2021-01-28
#
# Created by: SUSE Michael Brookhuis,
#
# Description:
# daily run to create:
#    - /srv/formula_metadata/uyunihub/form.yml
#
# Releases:
# 2020-12-01 M.Brookhuis - initial release.
# 2021-01-28 M.Brookhuis - Making ready for uyuni
#
#


import os
import sys
import xmlrpc.client
from shutil import copyfile
import yaml
import logging

if not os.path.exists("/var/log/rhn/uyunihub"):
    os.makedirs("/var/log/rhn/uyunihub")
log_name = "/var/log/rhn/uyunihub/hub_dailyrun.log"

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


if not os.path.isfile(os.path.dirname(__file__) + "/smconfig.yaml"):
    log.error("ERROR: smconfig.yaml doesn't exist. Please create file")
    sys.exit(1)
else:
    with open(os.path.dirname(__file__) + '/smconfig.yaml') as h_cfg:
        uyunihub = yaml.Loader(h_cfg).get_single_data()


def write_form_yml(clm_projects, base_channels, slaves, config_channels):
    src = "/srv/formula_metadata/uyunihub/form.yml"
    dst = "/srv/formula_metadata/uyunihub/form.old"
    copyfile(src, dst)
    f = open(src, "w")
    f.write('''
hub:
  $type: group

  server_username:
    $type: text
    $name: SUSE Manager admin
    $help: On all involved SUSE Manager Servers there should be the same SUSE Manager admin.

  server_password:
    $type: password
    $name: Password for SUSE Manager Admin
    $help: enter the password for the SUSE Manager Admin.
  
  hub_org:
    $type: text
    $name: Name of organization
    $help: This will be the first organization create when there is a new hub.
  
  projects_all:
    $name: "Projects assigned to all slaves"
    $type: "edit-group"
    $itemName: "project"
    $minItems: 0
    $prototype:
      project:
        $type: select
        $default: none
        $values: [''')
    for project in clm_projects:
        f.write('"{}",'.format(project))
    f.write('"none"]')
    f.write('''

  channels_all:
    $name: "Basechannels assigned to all slaves"
    $type: "edit-group"
    $minItems: 0
    $itemName: "basechannel"
    $prototype:
      basechannel:
        $type: select
        $default: none
        $values: [''')
    for channel in base_channels:
        f.write('"{}",'.format(channel))
    f.write('"none"]')
    f.write('''

  config_all:
    $name: "Configuration channels assigned to all slaves"
    $type: "edit-group"
    $minItems: 0
    $itemName: "configchannel"
    $prototype:
      configchannel:
        $type: select
        $default: none
        $values: [''')
    for cchannel in config_channels:
        f.write('"{}",'.format(cchannel))
    f.write('"none"]')
    f.write('''

  slave:      
    $name: "Basechannels and or projects assigned to a specific slave"
    $type: "edit-group"
    $minItems: 0
    $itemName: "slave"
    $prototype:
      slave:
        $type: "select"
        $default: none
        $values: [''')
    for slave in slaves:
        f.write('"{}",'.format(slave))
    f.write('"none"]')
    f.write('''
      projects:
        $name: "Projects assigned to this slave"
        $type: "edit-group"
        $itemName: "project"
        $minItems: 0
        $prototype:
          project:
            $type: select
            $default: none
            $values: [''')
    for project in clm_projects:
        f.write('"{}",'.format(project))
    f.write('"none"]')
    f.write('''
      channels:
        $name: "Basechannels assigned to this slave"
        $type: "edit-group"
        $itemName: "basechannel"
        $minItems: 0
        $prototype:
          basechannel:
            $type: select
            $default: none
            $values: [''')
    for channel in base_channels:
        f.write('"{}",'.format(channel))
    f.write('"none"]')
    f.write('''
      config:
        $name: "Configuration channels assigned to this slave"
        $type: "edit-group"
        $itemName: "confighannel"
        $minItems: 0
        $prototype:
          configchannel:
            $type: select
            $default: none
            $values: [''')
    for cchannel in config_channels:
        f.write('"{}",'.format(cchannel))
    f.write('"none"]')

    f.close()


def get_config_channels(session, client):
    all_configs = None
    try:
        all_configs = client.contentmanagement.listProjects(session)
    except xmlrpc.client.Fault as err:
        log.error('Unable to receive a list of project.')
        log.error('Error:')
        log.error(err)
    apr = []
    for project in all_configs:
        apr.append(project.get('label'))
    return apr


def get_clm_projects(session, client):
    all_projects = None
    try:
        all_projects = client.contentmanagement.listProjects(session)
    except xmlrpc.client.Fault as err:
        log.error('Unable to receive a list of project.')
        log.error('Error:')
        log.error(err)
    apr = []
    for project in all_projects:
        apr.append(project.get('label'))
    return apr


def get_base_channels(session, client):
    all_channels = None
    try:
        all_channels = client.channel.listSoftwareChannels(session)
    except xmlrpc.client.Fault as err:
        log.error("Unable to connect SUSE Manager to login to get a list of all software channels")
        log.error('Error:')
        log.error(err)
    abcl = []
    for c in all_channels:
        if not c.get('parent_label'):
            abcl.append(c.get('label'))
    return abcl


def get_slaves(session, client):
    all_slaves = None
    try:
        all_slaves = client.system.listSystems(session)
    except xmlrpc.client.Fault as err:
        log.error("Unable to connect SUSE Manager to login to get a list of all systems")
        log.error('Error:')
        log.error(err)
    slaves = []
    for c in all_slaves:
        slaves.append(c.get('name'))
    return slaves


def get_slaves_systemgroup(session, client, systemgroup):
    all_slaves = None
    try:
        all_slaves = client.systemgroup.listSystemsMinimal(session, systemgroup)
    except xmlrpc.client.Fault as err:
        log.error("Unable to get a list of systems for systemgroup {}".format(systemgroup))
        log.error('Error:')
        log.error(err)
    slaves = []
    for c in all_slaves:
        slaves.append(c.get('name'))
    return slaves


def main():
    client = xmlrpc.client.Server("http://{}/rpc/api".format(uyunihub['server']['hubmaster']))
    session_key = client.auth.login(uyunihub['server']['user'], uyunihub['server']['password'])
    if len(sys.argv) == 1:
        slaves = get_slaves_systemgroup(session_key, client, sys.argv[1])
    elif len(sys.argv) > 1:
        log.error("Usage: hub_dailyrun.py")
        client.auth.logout(session_key)
        sys.exit(1)
    else:
        slaves = get_slaves(session_key, client)
    clm_projects = get_clm_projects(session_key, client)
    base_channels = get_base_channels(session_key, client)
    config_channels = get_config_channels(session_key, client)
    write_form_yml(clm_projects, base_channels, slaves, config_channels)
    client.auth.logout(session_key)


if __name__ == "__main__":
    SystemExit(main())
