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
    hostname = getfqdn()
    session_key = None
    if len(args) != 2:
        print(f'Usage: {sys.argv[0]} <System ID> <event ID to search>')
        exit(1)
    else:
        id_machine = sys.argv[1]
        id_event = sys.argv[2]
        print(f'Requesting information on event ID {id_event}...')

    with xmlrpc.client.ServerProxy(MANAGER_URL) as proxy:
        try:
            session_key = proxy.auth.login(MANAGER_USER, MANAGER_PASS)
            earliest_occurrance = xmlrpc.client.DateTime(datetime.now())
            event = proxy.system.getEventDetails(session_key, int(id_machine), int(id_event))

            # print(event)
            print(f"ID: {event['id']}, Type: {event['history_type']}")
            print(f"Summary: {event['summary']}")
            print(f"Date scheduled: {event['earliest_action']}")
            print(f"Date created: {event['created']}")
            print(f"Date picked up: {event['picked_up']}")
            if 'result_msg' in event.keys():
                print(f"Result: {event['result_msg']} (RC={event['result_code']})")
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

