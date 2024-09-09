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
            print(f'group_id,group_name,group_description,org_id,system_count')
            for s in proxy.systemgroup.listAllGroups(session_key):
                # print(s)
                print(f"{s['id']},{s['name']},{s['description']},{s['org_id']},{s['system_count']}")
            if (session_key) is not None:
                proxy.auth.logout(session_key)
        except ConnectionRefusedError as e:
            print(f'Connection error: {e}')

main()