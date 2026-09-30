#!/usr/bin/env python3
"""
SUSE Manager / Uyuni API - Get Event Details (Robust)
"""
import argparse, xmlrpc.client, ssl, getpass, sys

def main():
    p = argparse.ArgumentParser()
    p.add_argument('-s', '--server'); p.add_argument('--url'); p.add_argument('-u', '--user', required=True)
    p.add_argument('-p', '--password'); p.add_argument('--aid', type=int, required=True)
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
        print(f"[*] Checking Action {args.aid} status via lists...")
        
        # Check specific status lists
        states = [("Failed", c.schedule.listFailedSystems), 
                  ("Completed", c.schedule.listCompletedSystems), 
                  ("In Progress", c.schedule.listInProgressSystems)]
        
        found = False
        print(f"{'Host':<30} | {'Status':<15} | {'Date'}")
        print("-" * 60)
        
        for label, method in states:
            try:
                for s in method(k, args.aid):
                    found = True
                    name = s.get('server_name') or s.get('name') or "Unknown"
                    # Fixed date lookup based on user feedback
                    date = str(s.get('timestamp') or "")
                    print(f"{name:<30} | {label:<15} | {date}")
            except: pass
            
        if not found: print("[-] No systems found for this action (or action invalid).")
        c.auth.logout(k)
    except Exception as e: print(f"Error: {e}")

if __name__ == "__main__": main()
