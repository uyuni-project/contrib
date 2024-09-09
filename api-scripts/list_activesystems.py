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
            score_data=proxy.system.getSystemCurrencyScores(session_key)
            print(f'"system name","system ID","critical patches","important patches","moderate patches","low priority patches","bugfixes","enhancement patches","system currency score"')
            for s in proxy.system.listActiveSystems(session_key):
                for score in score_data:
                    if s['id'] == score['sid']:
                        # {'score': 784, 'mod': 30, 'crit': 0, 'low': 5, 'bug': 116, 'imp': 18, 'enh': 4, 'sid': 1000010022}
                        print(f"{s['name']},{s['id']},{score['crit']},{score['imp']},{score['crit']},{score['mod']},{score['low']},{score['bug']},{score['enh']},{score['mod']},{s['last_checkin']}")
            if (session_key) is not None:
                proxy.auth.logout(session_key)
        except ConnectionRefusedError as e:
            print(f'Connection error: {e}')

main()