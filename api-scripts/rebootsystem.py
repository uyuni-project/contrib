#!/usr/bin/python3
import xmlrpc.client
import sys
from socket import getfqdn
from datetime import datetime
import pdb
MANAGER_USER = "infobot"
MANAGER_PASS = "infobot321"
MANAGER_URL = "http://susemanager.suselab.localdomain/rpc/api"


def main():
    args = sys.argv[1:]
    session_key = None
    if len(args) != 1:
        print(f'Usage: {sys.argv[0]} <system ID to be rebooted>')
        exit(1)
    else:
        id_machine = sys.argv[1]
        print('Requesting reboot for system {id_machine}')

    with xmlrpc.client.ServerProxy(MANAGER_URL) as proxy:
        try:
            session_key = proxy.auth.login(MANAGER_USER, MANAGER_PASS)
            earliest_occurrance = xmlrpc.client.DateTime(datetime.now())
            print(f"job_id: {proxy.system.scheduleReboot(session_key, int(id_machine), earliest_occurrance)}")
            if (session_key) is not None:
                proxy.auth.logout(session_key)
        except ConnectionRefusedError as e:
            print(f'Connection error: {e}')
        except ValueError as e:
            print(f'The system ID can only be numeric!')
        except xmlrpc.client.Fault as e:
            print(f'Error submitting job: {e}')
main()

