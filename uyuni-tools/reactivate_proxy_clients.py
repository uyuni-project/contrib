#!/bin/python3

"""
This script reactivates all clients which uses specified proxy FQDN as salt master.

Workflow:

1) use salt grains targeting to get the list of salt minion ids
2) use XMLRPC API to generate reactivation for each salt client
3) update susemanager.conf of the client to inject reactivation key
4) restart salt minion

Restart of salt minion will trigger automatic reactivation of the client system
which will update client's connection path in the database.
"""

import argparse
import getpass
import salt.client
import sys
from xmlrpc.client import ServerProxy

parser = argparse.ArgumentParser(description = "Reactivate all online clients attached to the specified proxy (determined by salt clients 'master' grain)")
parser.add_argument("--dryrun", default=False, action="store_true", help = "Show the actions, but do not do anything")
parser.add_argument("--limit", default=None, help = "Limit the number of modified salt clients (default unlimited)", type=int)
parser.add_argument("--host", help = "SUSE Manager hostname")
parser.add_argument("--user", help = "SUSE Manager username for login. If not provided, will be asked for")
parser.add_argument("--password", help = "SUSE Manager password for login. If not provided, will be asked for")
parser.add_argument("proxy_fqdn", help = "FQDN or proxy which clients are to be reactivated")

args = parser.parse_args()

if args.host is None:
    args.host = input("Host for SUSE Manager: ")

if args.user is None:
    args.user = input("User for SUSE Manager API on {}: ".format(args.host))

if args.password is None:
    args.password = getpass.getpass("Password for SUSE Manager API user {} on {}: ".format(args.user, args.host))

if args.dryrun:
    print('INFO: running in DRYRUN mode. No changes will be done')

maxclients = sys.maxsize
if args.limit is not None:
    print('INFO: limiting number of modified clients to {}'.format(args.limit))
    maxclients = args.limit

MANAGER_URL = "https://{}/rpc/api".format(args.host)

if __name__ == "__main__":
    suma_rpc = ServerProxy(MANAGER_URL)
    key = suma_rpc.auth.login(args.user, args.password)

    clients = []
    nclients = 0

    client_mapping = suma_rpc.system.getMinionIdMap(key)
    suma_salt = salt.client.LocalClient()
    res = suma_salt.cmd_iter("master:{}".format(args.proxy_fqdn), "grains.item", ["id", "saltpath"], tgt_type="grain", timeout = 2)
    for c in res:
        nclients += 1
        if maxclients < nclients:
            break
        
        salt_ret = list(c.values())[0]["ret"]
        c_saltid = salt_ret["id"]
        c_configpath = "/etc/venv-salt-minion/minion.d/susemanager.conf" \
            if "venv" in salt_ret.get("saltpath", "") \
            else "/etc/salt/minion.d/susemanager.conf"

        print('Processing salt client {}'.format(c_saltid))
        c_id = client_mapping.get(c_saltid)
        if c_id is None:
            print('ERROR: Cannot find server id for salt client {}'.format(c_saltid))
            continue
        # check if already assigned to correct proxy
        skip = False
        rpc_ret = suma_rpc.system.getConnectionPath(key, c_id)
        for path in rpc_ret:
            if path.get('position') == 1 and path.get('hostname') == args.proxy_fqdn:
                print('INFO: Skipping client {}, already connected to correct proxy.'.format(c_saltid))
                skip = True
        if skip:
            continue

        c_key = "reactivation key"
        if args.dryrun:
            print('DRYRUN: suma_rpc.system.obtainReactivationKey(key, {})'.format(c_id))
        else:
            c_key = suma_rpc.system.obtainReactivationKey(key, c_id)
        clients.append((c_saltid, c_configpath, c_key))

    for c, p, r in clients:
        sed_cmd = "sed -i -e 's/^\(\s*\)susemanager:.*$/\\1susemanager:\\n\\1    management_key: {}/' {}".format(r, p)
        if args.dryrun:
            print('DRYRUN: suma_salt.cmd({}, "cmd.run", ["{}"])'.format(c, sed_cmd))
            print('DRYRUN: suma_salt.cmd({}, "cmd.run_bg", ["sleep 2;service salt-minion restart"])'.format(c))
        else:
            suma_salt.cmd(c, "cmd.run", [sed_cmd])
            print('Salt client {} reactivation key grain set, restarting salt-minion'.format(c))
            suma_salt.cmd(c, "cmd.run_bg", ["sleep 2;service salt-minion restart"])

    print("All done, wait until all salt clients reactivates and check proxy connections")
