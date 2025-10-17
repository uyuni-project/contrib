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
	if len(args) != 3:
		print(f'Usage: {sys.argv[0]} <hostname> <key> <value>')
		exit(1)
	else:
		hostname = sys.argv[1]
		field_name = sys.argv[2]
		field_value = sys.argv[3]
		try:
			with xmlrpc.client.ServerProxy(MANAGER_URL) as proxy:
				session_key = proxy.auth.login(MANAGER_USER, MANAGER_PASS)
				hosts = proxy.system.getId(session_key, hostname)
				system_id = hosts[0].get('id')
				try:
					print(f'Updating {hostname} with system ID {system_id}...')
					proxy.system.set_CustomValues(session_key,system_id,{field_name: field_value})
				except Exception as e:
					print("{e} Key does not exist, creating...")
					proxy.system.custominfo.createKey(session_key, field_name, field_name)
				
				proxy.system.set_CustomValues(session_key,system_id,{field_name: field_value})
				print(f"Key {field_name}={field_value} set successfully!")
				if (session_key) is not None:
					proxy.auth.logout(session_key)
		except ConnectionRefusedError as e:
			print(f'Connection error: {e}')

main()