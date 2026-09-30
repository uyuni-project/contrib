#!/usr/bin/env python3
"""
SUSE Manager / Uyuni API - Search Patches (Errata) by CVE
"""
import argparse, xmlrpc.client, ssl, getpass, sys

def main():
    p = argparse.ArgumentParser()
    p.add_argument('-s', '--server'); p.add_argument('--url'); p.add_argument('-u', '--user', required=True)
    p.add_argument('-p', '--password'); p.add_argument('--cve', required=True)
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
        print(f"[*] Searching errata for CVE: {args.cve}")
        results = c.errata.findByCve(k, args.cve)
        
        print(f"{'Advisory':<20} | {'Synopsis'}")
        print("-" * 70)
        for r in results:
            syn = r.get('synopsis') or r.get('advisory_synopsis') or ""
            print(f"{r.get('advisory_name'):<20} | {syn[:48]}")
        
        print(f"\nFound {len(results)} matches.")
        c.auth.logout(k)
    except Exception as e: print(f"Error: {e}")

if __name__ == "__main__": main()
