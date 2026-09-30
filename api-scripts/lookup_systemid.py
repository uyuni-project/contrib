#!/usr/bin/env python3
"""
SUSE Manager / Uyuni API - Lookup System ID
"""
import argparse, xmlrpc.client, ssl, getpass, sys

def main():
    p = argparse.ArgumentParser()
    p.add_argument('-s', '--server'); p.add_argument('--url'); p.add_argument('-u', '--user', required=True)
    p.add_argument('-p', '--password'); p.add_argument('--query', required=True)
    p.add_argument('--verify', action='store_true')
    args = p.parse_args()

    if args.url: api_url = args.url
    elif args.server: api_url = f"https://{args.server}/rpc/api"
    else: print("[!] Error: Provide -s/--server or --url"); sys.exit(1)

    pwd = args.password or getpass.getpass()
    ctx = ssl.create_default_context()
    if not args.verify: ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE

    try:
        c = xmlrpc.client.ServerProxy(api_url, context=ctx); k = c.auth.login(args.user, pwd)
        q = args.query.lower()
        print(f"[*] Searching '{q}' locally in system list...")
        
        for s in c.system.listSystems(k):
            if q in str(s.get('name', '')).lower() or q in str(s.get('id', '')):
                print(f"{s['id']} | {s['name']} | {s.get('last_checkin')}")
        c.auth.logout(k)
    except Exception as e: print(e)

if __name__ == "__main__": main()
