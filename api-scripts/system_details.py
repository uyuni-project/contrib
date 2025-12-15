#!/usr/bin/env python3
"""
SUSE Manager / Uyuni API - Get System Details
"""
import argparse, xmlrpc.client, ssl, getpass, sys

def parse_args():
    p = argparse.ArgumentParser(description="Get System Details")
    p.add_argument('-s', '--server', help="Server hostname")
    p.add_argument('--url', help="Full API URL")
    p.add_argument('-u', '--user', dest='username', required=True, help="Username")
    p.add_argument('-p', '--password', dest='password', required=False, help="Password")
    p.add_argument('--sid', dest='sid', type=int, required=True, help="System ID")
    p.add_argument('--verify', dest='verify', action='store_true', help="Verify SSL certificate")
    return p.parse_args()

def main():
    args = parse_args()
    if args.url: api_url = args.url
    elif args.server: api_url = f"https://{args.server}/rpc/api"
    else: print("[!] Error: Provide -s/--server or --url"); sys.exit(1)

    password = args.password or getpass.getpass(prompt=f"Password for {args.username}: ")
    context = ssl.create_default_context()
    if not args.verify:
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

    try:
        client = xmlrpc.client.ServerProxy(api_url, context=context)
        key = client.auth.login(args.username, password)
        print(f"[*] Fetching details for System ID: {args.sid}")
        name = client.system.getName(key, args.sid).get('name', 'Unknown')
        print(f"ID: {args.sid}\nHostname: {name}")
        print("\n--- Network Interfaces ---")
        for d in client.system.getNetworkDevices(key, args.sid):
            print(f"Interface: {d.get('interface')} | IP: {d.get('ip')} | MAC: {d.get('hardware_address')}")
        client.auth.logout(key)
    except Exception as e: print(f"[!] Error: {e}")

if __name__ == "__main__": main()
