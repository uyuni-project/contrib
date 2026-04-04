#!/usr/bin/env python3
"""
SUSE Manager / Uyuni API - Update All Packages
"""
import argparse, xmlrpc.client, ssl, getpass, sys, datetime

def main():
    p = argparse.ArgumentParser()
    p.add_argument('-s', '--server'); p.add_argument('--url'); p.add_argument('-u', '--user', required=True)
    p.add_argument('-p', '--password'); p.add_argument('--sid', type=int, required=True)
    p.add_argument('--dry-run', action='store_true'); p.add_argument('--verify', action='store_true')
    args = p.parse_args()

    if args.url: api_url = args.url
    elif args.server: api_url = f"https://{args.server}/rpc/api"
    else: print("[!] Error: Provide -s/--server or --url"); sys.exit(1)

    pwd = args.password or getpass.getpass()
    ctx = ssl.create_default_context()
    if not args.verify: ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE

    try:
        c = xmlrpc.client.ServerProxy(api_url, context=ctx); k = c.auth.login(args.user, pwd)
        pkgs = c.system.listLatestUpgradablePackages(k, args.sid)
        pids = [p['to_package_id'] for p in pkgs]
        
        print(f"Found {len(pids)} updates.")
        if not args.dry_run and pids:
            aid = c.system.schedulePackageInstall(k, args.sid, pids, datetime.datetime.now())
            print(f"[+] Update scheduled. ID: {aid}")
        c.auth.logout(k)
    except Exception as e: print(e)

if __name__ == "__main__": main()
