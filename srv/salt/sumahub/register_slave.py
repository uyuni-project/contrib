#!/usr/bin/python3
#
# register slave ISS on master ISS
import os
import sys
import xmlrpc.client
import yaml
import socket


def load_yaml(stream):
    """
    Load YAML data.
    """
    loader = yaml.Loader(stream)
    try:
        return loader.get_single_data()
    finally:
        loader.dispose()


if not os.path.isfile(os.path.dirname(__file__) + "/sumahub.yaml"):
    print("ERROR: sumahub.yaml doesn't exist. Please create file")
    sys.exit(1)
else:
    with open(os.path.dirname(__file__) + '/sumahub.yaml') as h_cfg:
        sumahub = load_yaml(h_cfg)

if len(sys.argv) != 1:
    print("Usage: register_master.py")
    sys.exit(1)

hub_slave = socket.getfqdn()
slave_present = False
for slave in sumahub['suman']['hubslaves']:
    if hub_slave == slave:
        slave_present = True
        break
if not slave_present:
    print("The given hubslave is not in sumahub.yaml. Aborting")
    sys.exit(1)

manager_url = "http://{}/rpc/api".format(sumahub['suman']['hubmaster'])
client = xmlrpc.client.Server(manager_url, verbose=0)
session_key = client.auth.login(sumahub['suman']['user'], sumahub['suman']['password'])

try:
    previous_slave = client.sync.slave.getSlaveByName(session_key, hub_slave)
    client.sync.slave.delete(session_key, previous_slave["id"])
    print("Pre-existing Slave deleted.")
except:
    pass

slave = client.sync.slave.create(session_key, hub_slave, True, True)

print("Slave added to this Master.")

orgs = client.org.listOrgs(session_key)
result = client.sync.slave.setAllowedOrgs(session_key, slave["id"], [org["id"] for org in orgs])
if result != 1:
    print("Got error %d on setAllowedOrgs" % result)
    sys.exit(1)

print("All orgs exported.")

client.auth.logout(session_key)

manager_url = "http://{}/rpc/api".format(hub_slave)
client = xmlrpc.client.Server(manager_url, verbose=0)
session_key = client.auth.login(sumahub['suman']['user'], sumahub['suman']['password'])

try:
    previous_master = client.sync.master.getMasterByLabel(session_key, sumahub['suman']['hubmaster'])
    client.sync.master.delete(session_key, previous_master["id"])
    print("Pre-existing Master deleted.")
except:
    pass

master = client.sync.master.create(session_key, sumahub['suman']['hubmaster'])

print("Master added to this Slave.")

result = client.sync.master.makeDefault(session_key, master["id"])
if result != 1:
    print("Got error %d on makeDefault" % result)
    sys.exit(1)

print("Master made default.")

result = client.sync.master.setCaCert(session_key, master["id"], "/etc/pki/trust/anchors/RHN-ORG-TRUSTED-SSL-CERT")
if result != 1:
    print("Got error %d on setCaCert" % result)
    sys.exit(1)

print("CA cert path set.")
client.auth.logout(session_key)

print("Done.")