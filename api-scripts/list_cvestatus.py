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
        print(f'Usage: {sys.argv[0]} <CVE ID to search>')
        exit(1)
    else:
        cve_id = sys.argv[1]
        print(f'Requesting information about {cve_id}...')

        with xmlrpc.client.ServerProxy(MANAGER_URL) as proxy:
            try:
                session_key = proxy.auth.login(MANAGER_USER, MANAGER_PASS)
                #print(f"{cve_id}")
                for s in proxy.audit.listSystemsByPatchStatus(session_key, cve_id):
                    details = proxy.system.getDetails(session_key, s['system_id'])
                    #print(f"\tHostname: {details['hostname']} (id: {s['system_id']}) PATCH STATUS: {s['patch_status']}") 
                    #print(f"\tchannel: {s['channel_labels']}, errata advisories: {s['errata_advisories']}")
                    print(f"{cve_id},{details['hostname']},{s['system_id']},{s['channel_labels']},{s['errata_advisories']},{s['patch_status']}")
                if (session_key) is not None:
                    proxy.auth.logout(session_key)
            except ConnectionRefusedError as e:
                print(f'Connection error: {e}')
            except xmlrpc.client.Fault as e:
                print(f'Error searching for CVE: {e}')


main()

