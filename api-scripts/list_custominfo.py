#!/usr/bin/env python3
"""
SUSE Manager / Uyuni API - List Custom Info
"""
import argparse, xmlrpc.client, ssl, getpass, sys

def main():
    p = argparse.ArgumentParser()
    p.add_argument('-s', '--server'); p.add_argument('--url'); p.add_argument('-u', '--user', required=True)
    p.add_argument('-p', '--password'); p.add_argument('--sid', type=int, required=True)
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
        vals = c.system.getCustomValues(k, args.sid)
        
        if isinstance(vals, dict):
            for key, val in vals.items(): print(f"{key}: {val}")
        elif isinstance(vals, list):
            for v in vals:
                # Handle varying dict keys for label
                lbl = v.get('key_label') or v.get('label') or 'Unknown'
                val = v.get('value', '')
                print(f"{lbl}: {val}")
        
        c.auth.logout(k)
    except Exception as e: print(f"Error: {e}")

if __name__ == "__main__": main()
