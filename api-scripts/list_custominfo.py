#!/usr/bin/python3
import xmlrpc.client
import sys
from socket import getfqdn
import pdb
MANAGER_USER = "infobot"
MANAGER_PASS = "infobot321"
MANAGER_URL = "http://susemanager.suselab.localdomain/rpc/api"

def main():
    session_key = None
    args = sys.argv[1:]
    if len(args) != 1:
        print(f'Usage: {sys.argv[0]} <hostname>')
        exit(1)
    else:
        hostname = sys.argv[1]
        try:
            with xmlrpc.client.ServerProxy(MANAGER_URL) as proxy:
                session_key = proxy.auth.login(MANAGER_USER, MANAGER_PASS)
                hosts = proxy.system.getId(session_key, hostname)
                system_id = hosts[0].get('id')
                print(f'Fetching custom info for {hostname} with system ID {system_id}...')
                print(proxy.system.getCustomValues(session_key,system_id))
                if (session_key) is not None:
                    proxy.auth.logout(session_key)
        except ConnectionRefusedError as e:
            print(f'Connection error: {e}')

main()