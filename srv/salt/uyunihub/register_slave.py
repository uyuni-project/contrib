#!/usr/bin/python3
#
# (c) 2020 SUSE Linux GmbH, Germany.
# GNU Public License. No warranty. No Support 
#
# Version: 2021-01-28
#
# Created by: SUSE Michael Brookhuis,
#
# Description: This script will register the slave to the master
#
# Releases:
# 2020-12-01 M.Brookhuis - initial release.
# 2021-01-28 M.Brookhuis - Making ready for uyuni


import os
import sys
import xmlrpc.client
import yaml
import socket
import logging

if not os.path.exists("/var/log/rhn/uyunihub"):
    os.makedirs("/var/log/rhn/uyunihub")
log_name = "/var/log/rhn/uyunihub/register_slave.log"

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


def load_yaml(stream):
    """
    Load YAML data.
    """
    loader = yaml.Loader(stream)
    try:
        return loader.get_single_data()
    finally:
        loader.dispose()


if not os.path.isfile(os.path.dirname(__file__) + "/uyunihub.yaml"):
    log.error("ERROR: uyunihub.yaml doesn't exist. Please create file")
    sys.exit(1)
else:
    with open(os.path.dirname(__file__) + '/uyunihub.yaml') as h_cfg:
        uyunihub = load_yaml(h_cfg)

if len(sys.argv) != 1:
    log.error("Usage: register_master.py")
    sys.exit(1)

hub_slave = socket.getfqdn()

manager_url = "http://{}/rpc/api".format(uyunihub['server']['hubmaster'])
client = xmlrpc.client.Server(manager_url)
session_key = client.auth.login(uyunihub['server']['user'], uyunihub['server']['password'])

try:
    previous_slave = client.sync.slave.getSlaveByName(session_key, hub_slave)
    client.sync.slave.delete(session_key, previous_slave["id"])
    log.info("Pre-existing Slave deleted.")
except:
    pass

slave = client.sync.slave.create(session_key, hub_slave, True, True)

log.info("Slave added to this Master.")

orgs = client.org.listOrgs(session_key)
result = client.sync.slave.setAllowedOrgs(session_key, slave["id"], [org["id"] for org in orgs])
if result != 1:
    log.error("Got error %d on setAllowedOrgs" % result)
    sys.exit(1)

log.info("All orgs exported.")

client.auth.logout(session_key)

manager_url = "http://{}/rpc/api".format(hub_slave)
client = xmlrpc.client.Server(manager_url)
session_key = client.auth.login(uyunihub['server']['user'], uyunihub['server']['password'])

try:
    previous_master = client.sync.master.getMasterByLabel(session_key, uyunihub['server']['hubmaster'])
    client.sync.master.delete(session_key, previous_master["id"])
    log.info("Pre-existing Master deleted.")
except:
    pass

master = client.sync.master.create(session_key, uyunihub['server']['hubmaster'])

log.info("Master added to this Slave.")

result = client.sync.master.makeDefault(session_key, master["id"])
if result != 1:
    log.error("Got error %d on makeDefault" % result)
    sys.exit(1)

log.info("Master made default.")

result = client.sync.master.setCaCert(session_key, master["id"], "/etc/pki/trust/anchors/RHN-ORG-TRUSTED-SSL-CERT")
if result != 1:
    log.error("Got error %d on setCaCert" % result)
    sys.exit(1)

log.info("CA cert path set.")
client.auth.logout(session_key)

log.info("Done.")
