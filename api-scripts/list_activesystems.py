#!/usr/bin/env python3
"""
SUSE Manager / Uyuni API - List Active Systems
"""
import argparse, xmlrpc.client, ssl, getpass, sys
from datetime import datetime, timedelta

def main():
    p = argparse.ArgumentParser()
    p.add_argument('-s', '--server'); p.add_argument('--url'); p.add_argument('-u', '--user', required=True)
    p.add_argument('-p', '--password'); p.add_argument('--days', type=int, default=1)
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
        cutoff = datetime.now() - timedelta(days=args.days)
        print(f"[*] Listing systems active since {cutoff}")
        
        count = 0
        for s in c.system.listSystems(k):
            lc = s.get('last_checkin')
            if not lc: continue
            
            # Try parsing date formats
            dt = None
            for fmt in ["%Y-%m-%d %H:%M:%S", "%Y%m%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S"]:
                try: dt = datetime.strptime(str(lc), fmt); break
                except: continue
            
            if dt and dt >= cutoff:
                print(f"{s['id']} | {s['name']} | {dt}")
                count += 1
        print(f"[+] Total: {count}")
        c.auth.logout(k)
    except Exception as e: print(e)

if __name__ == "__main__": main()
