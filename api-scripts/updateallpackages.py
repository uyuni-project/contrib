#!/usr/bin/python3
from datetime import datetime
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
        print(f'Usage: {sys.argv[0]} <hostname to migrate>')
        exit(1)
    else:
        hostname = sys.argv[1]
        with xmlrpc.client.ServerProxy(MANAGER_URL) as proxy:
            session_key = proxy.auth.login(MANAGER_USER, MANAGER_PASS)
            print(f'Requesting information about {hostname}...')
            hosts = proxy.system.getId(session_key, hostname)
            try:
                system_id = hosts[0].get('id')
                print(f'The System ID for {hostname} is {system_id}')
            except IndexError as e:
                print(f"Cannot find system ID for {hostname}!")
                exit(1)
            try:
                session_key = proxy.auth.login(MANAGER_USER, MANAGER_PASS)
                print(f'Scheduling complete package upgrades for system {system_id}...')
                jobid = proxy.system.schedulePackageUpdate(session_key,[system_id], datetime.now() )

                if jobid > 0:
                    print(f"---> Job ID: {jobid}")
                    print(f"*** Use the command './get_eventdetails.py {system_id} {jobid}' to fetch the execution results for the update.")
                if (session_key) is not None:
                    proxy.auth.logout(session_key)
            except ConnectionRefusedError as e:
                print(f'Connection error: {e}')
            except xmlrpc.client.Fault as e:
                print(f'Error migrating system: {e}')
                print(f'Please consider updating the system first.')
                proxy.auth.logout(session_key)
                exit(1)
main()