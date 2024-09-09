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
            print(f'channel_label,channel_name,parent_label,channel_arch,end_of_life')
            for s in proxy.channel.listSoftwareChannels(session_key):
                print(f"{s['label']},{s['name']},{s['parent_label']},{s['arch']},{'True' if s['end_of_life'] != '' else 'False'}")
            if (session_key) is not None:
                proxy.auth.logout(session_key)
        except ConnectionRefusedError as e:
            print(f'Connection error: {e}')

main()

