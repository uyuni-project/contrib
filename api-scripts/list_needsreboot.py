#!/usr/bin/python3
import xmlrpc.client
import sys
from socket import getfqdn
import pdb
MANAGER_USER = "infobot"
MANAGER_PASS = "infobot321"
MANAGER_URL = "http://susemanager.suselab.localdomain/rpc/api"

def main():
    hostname = getfqdn()
    session_key = None
    with xmlrpc.client.ServerProxy(MANAGER_URL) as proxy:
        try:
            session_key = proxy.auth.login(MANAGER_USER, MANAGER_PASS)
            systems = proxy.system.listSuggestedReboot(session_key)
            print(f"system_id,system_name,hostname,ip_address")
            for s in systems:
                details = proxy.system.getDetails(session_key, s['id'])
                network = proxy.system.getNetwork(session_key, s['id'])
                # print(details)
                # print(network)
                print(f"{s['id']},{s['name']},{network['hostname']},{network['ip']}")
            if (session_key) is not None:
                proxy.auth.logout(session_key)
        except ConnectionRefusedError as e:
            print(f'Connection error: {e}')

main()