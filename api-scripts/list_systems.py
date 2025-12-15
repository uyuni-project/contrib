#!/usr/bin/env python3
"""
SUSE Manager / Uyuni API - List Systems
"""
import argparse, xmlrpc.client, ssl, getpass, sys

def parse_args():
    p = argparse.ArgumentParser(description="List Systems")
    p.add_argument('-s', '--server', help="Server hostname")
    p.add_argument('--url', help="Full API URL")
    p.add_argument('-u', '--user', dest='username', required=True, help="Username")
    p.add_argument('-p', '--password', dest='password', required=False, help="Password")
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
        print(f"{'ID':<10} | {'Hostname':<40} | {'Last Check-in'}")
        print("-" * 75)
        for s in client.system.listSystems(key):
            print(f"{s['id']:<10} | {s['name']:<40} | {s['last_checkin']}")
        client.auth.logout(key)
    except Exception as e: print(f"[!] Error: {e}")

if __name__ == "__main__": main()
