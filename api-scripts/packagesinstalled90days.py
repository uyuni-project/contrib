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
    hostname = getfqdn()
    session_key = None
    with xmlrpc.client.ServerProxy(MANAGER_URL) as proxy:
        try:
            session_key = proxy.auth.login(MANAGER_USER, MANAGER_PASS)
            print(f'system_id,system_name,hostname,ip_address,event_id,earliest_action,pickup_date,completed_date,status,event,event_data,synced_date')
            date_now = datetime.today()
            package_actions = ['Package Install', 'Package Upgrade', 'Package Removal', 'Patch Update']
            for s in proxy.system.listSystems(session_key):
                details = proxy.system.getDetails(session_key, s['id'])
                network = proxy.system.getNetwork(session_key, s['id'])
                events = proxy.system.listSystemEvents(session_key, s['id'])
                package_events = []
                for p in events:
                    date_modified = datetime.strptime(p['modified'], "%Y-%m-%d %H:%M:%S.%f")
                    if p['action_type'] in package_actions and (date_now-date_modified).days < 90:
                        if p['completed_date'] != '':
                            result = 'Completed'
                        else:
                            result = 'Failed'
                        # print(f"--> found event: {p['action_type']}")
                        package_list = []
                        if 'additional_info' in p.keys():
                            for pkg in p['additional_info']:
                                package_list.append(pkg['detail'])
                            print(f"{s['id']},{details['profile_name']},{network['hostname']},{network['ip']},{p['id']},{p['earliest_action']},{p['pickup_date']},{p['completed_date']},{result},{p['action_type']},{';'.join(package_list)},{p['modified_date']}")        
                
            if (session_key) is not None:
                proxy.auth.logout(session_key)
        except ConnectionRefusedError as e:
            print(f'Connection error: {e}')

main()

