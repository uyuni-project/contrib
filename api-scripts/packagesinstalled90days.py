#!/usr/bin/env python3
"""
SUSE Manager / Uyuni API - Audit Packages > 90 Days via Events
"""
import argparse, xmlrpc.client, ssl, getpass, sys
from datetime import datetime, timedelta

def main():
    p = argparse.ArgumentParser()
    p.add_argument('-s', '--server'); p.add_argument('--url'); p.add_argument('-u', '--user', required=True)
    p.add_argument('-p', '--password'); p.add_argument('--sid', type=int, required=True)
    p.add_argument('--days', type=int, default=90); p.add_argument('--verify', action='store_true')
    args = p.parse_args()

    if args.url: api_url = args.url
    elif args.server: api_url = f"https://{args.server}/rpc/api"
    else: print("[!] Error: Provide -s/--server or --url"); sys.exit(1)

    pwd = args.password or getpass.getpass()
    ctx = ssl.create_default_context()
    if not args.verify: ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE

    try:
        c = xmlrpc.client.ServerProxy(api_url, context=ctx); k = c.auth.login(args.user, pwd)
        
        name = c.system.getName(k, args.sid).get('name')
        print(f"[*] Analyzing events for {name} > {args.days} days ago...")
        
        now = datetime.today()
        actions = ['Package Install', 'Package Upgrade', 'Patch Update']
        count = 0

        # Iterate history events
        for e in c.system.listSystemEvents(k, args.sid):
            atype = e.get('action_type')
            if atype not in actions: continue
            
            # Parse Date (often 'modified' or 'created' field, format varies)
            d_str = str(e.get('created', e.get('modified', '')))
            dt = None
            for fmt in ["%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y%m%dT%H:%M:%S"]:
                try: dt = datetime.strptime(d_str, fmt); break
                except: continue
            
            if dt and (now - dt).days > args.days:
                status = "Completed" if e.get('completed_date') else "Failed/Pending"
                # Extract package info
                details = []
                if 'additional_info' in e:
                    for item in e['additional_info']:
                        if isinstance(item, dict): details.append(item.get('detail',''))
                        else: details.append(str(item))
                
                print(f"{dt} | {atype} | {status} | {';'.join(details)[:50]}...")
                count += 1
        
        print(f"[+] Found {count} matching events.")
        c.auth.logout(k)
    except Exception as e: print(f"Error: {e}")

if __name__ == "__main__": main()
