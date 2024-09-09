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
    try:
        with xmlrpc.client.ServerProxy(MANAGER_URL) as proxy:
            session_key = proxy.auth.login(MANAGER_USER, MANAGER_PASS)
            akeys=proxy.activationkey.listActivationKeys(session_key)
            print("key,description,base_channel_label,child_channel_labels,server_group_ids,package_names,entitlements,usage_limit,universal_default,contact_method,disabled")
            for k in akeys:
                print(f"{k['key']},{k['description']},{k['base_channel_label']},{k['child_channel_labels']},{k['server_group_ids']},{k['package_names']},{k['entitlements']},{k['usage_limit']},{k['universal_default']},{k['contact_method']},{k['disabled']}")
            if (session_key) is not None:
                proxy.auth.logout(session_key)
    except ConnectionRefusedError as e:
        print(f'Connection error: {e}')

main()