#!/usr/bin/env python3
"""
SUSE Manager / Uyuni API - List Systems Affected by CVE
Uses errata search for maximum compatibility.
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
        print(f"[*] Searching for patches for {args.cve}...")
        
        # Strategy: Find patches first, then systems
        errata = c.errata.findByCve(k, args.cve)
        if not errata:
            print(f"[-] No patches found for {args.cve}")
        else:
            print(f"[*] Found {len(errata)} patches. Checking affected systems...")
            affected_map = {}
            for e in errata:
                advisory = e.get('advisory_name')
                systems = c.errata.listAffectedSystems(k, advisory)
                for s in systems:
                    affected_map[s['id']] = s['name']
            
            print(f"\nAffected Systems ({len(affected_map)}):")
            for sid, name in affected_map.items():
                print(f"{sid} | {name}")

        c.auth.logout(k)
    except Exception as e: print(f"[!] Error: {e}")

if __name__ == "__main__": main()
