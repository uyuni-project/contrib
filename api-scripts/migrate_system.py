#!/usr/bin/env python3
"""
SUSE Manager / Uyuni API - Migrate System (Classic Style)
Includes checks for available migrations and validation before scheduling.
"""
import argparse, xmlrpc.client, ssl, getpass, sys

def main():
    p = argparse.ArgumentParser()
    p.add_argument('-s', '--server'); p.add_argument('--url'); p.add_argument('-u', '--user', required=True)
    p.add_argument('-p', '--password'); p.add_argument('--sid', type=int, required=True)
    p.add_argument('--target-base', required=True, help="Target Base Channel Label")
    p.add_argument('--dry-run', action='store_true', help="Check migration availability only")
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
        
        # 1. Check System Name
        sname = c.system.getName(k, args.sid).get('name')
        print(f"[*] Checking system: {sname} (ID: {args.sid})")

        # 2. List Available Migrations
        migrations = c.system.listMigrationUpgrades(k, args.sid)
        if not migrations:
            print("[-] No migrations available for this system.")
            c.auth.logout(k)
            return

        # 3. Validate Target
        valid_target = False
        for m in migrations:
            if m.get('label') == args.target_base:
                valid_target = True
                print(f"[+] Found valid migration path to: {m.get('label')}")
                break
        
        if not valid_target:
            print(f"[!] Error: Target base channel '{args.target_base}' is not a valid migration option.")
            print(f"    Available options: {[m.get('label') for m in migrations]}")
            c.auth.logout(k)
            return

        # 4. Schedule
        if args.dry_run:
            print("[*] Dry run complete. Migration is possible.")
        else:
            aid = c.system.scheduleProductMigration(k, args.sid, args.target_base)
            print(f"[+] Migration Scheduled. Action ID: {aid}")
            
        c.auth.logout(k)
    except Exception as e: print(f"Error: {e}")

if __name__ == "__main__": main()
