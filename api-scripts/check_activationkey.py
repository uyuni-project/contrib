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
        print(f'Usage: {sys.argv[0]} <key to search>')
        exit(1)
    else:
        search = sys.argv[1]
        try:
            with xmlrpc.client.ServerProxy(MANAGER_URL) as proxy:
                session_key = proxy.auth.login(MANAGER_USER, MANAGER_PASS)
                akeys=proxy.activationkey.listActivationKeys(session_key)
                for k in akeys:
                    if k['key'] == search:
                        print("key found: " + search)
                        return 0
                    print("key does not exist: " + search)
                if (session_key) is not None:
                    proxy.auth.logout(session_key)
        except ConnectionRefusedError as e:
            print(f'Connection error: {e}')

main()