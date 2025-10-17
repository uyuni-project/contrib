#!/usr/bin/python3
import xmlrpc.client
import sys
from socket import getfqdn
from datetime import datetime,timedelta
import pdb
MANAGER_USER = "infobot"
MANAGER_PASS = "infobot321"
MANAGER_URL = "http://susemanager.suselab.localdomain/rpc/api"


def main():
    args = sys.argv[1:]
    session_key = None
    if len(args) != 1:
        print(f'Usage: {sys.argv[0]} <System ID>')
        exit(1)
    else:
        id_machine = sys.argv[1]
        print(f'Requesting 30 days of event history for system ID {id_machine}...')

    with xmlrpc.client.ServerProxy(MANAGER_URL) as proxy:
        try:
            session_key = proxy.auth.login(MANAGER_USER, MANAGER_PASS)
            earliest_occurrance = xmlrpc.client.DateTime(datetime.now()-(timedelta(days=30)))
            events = proxy.system.getEventHistory(session_key, int(id_machine), earliest_occurrance, 0, 1000)
            print(events)
            for event in events:
                print()
                print(f"ID: {event['id']}, Type: {event['history_type']}")
                print(f"Summary: {event['summary']}")
                print(f"Date completed: {event['completed']}")
                print(f"Status: {event['status']}")

            if (session_key) is not None:
                proxy.auth.logout(session_key)
        except ConnectionRefusedError as e:
            print(f'Connection error: {e}')
        except ValueError as e:
            print(f'System ID can only be numeric!')
        except xmlrpc.client.Fault as e:
            print(f'Error submitting job: {e}')
main()

