#!/usr/bin/env python3
"""
SUSE Manager / Uyuni API - Update Custom Info
"""
import argparse, xmlrpc.client, ssl, getpass, sys

def main():
    p = argparse.ArgumentParser()
    p.add_argument('-s', '--server'); p.add_argument('--url'); p.add_argument('-u', '--user', required=True)
    p.add_argument('-p', '--password'); p.add_argument('--sid', type=int, required=True)
    p.add_argument('--key', required=True); p.add_argument('--value', required=True)
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
        print(f"[*] Setting Custom Info for System {args.sid}...")
        print(f"    Key:   {args.key}")
        print(f"    Value: {args.value}")

        payload = {args.key: args.value}

        try:
            c.system.setCustomValues(k, args.sid, payload)
            print("[+] Custom info updated successfully.")
        except xmlrpc.client.Fault as f:
            if "not defined" in f.faultString:
                print(f"[*] Key '{args.key}' does not exist. Creating it now...")
                try:
                    c.system.custominfo.createKey(k, args.key, "Created via API")
                    print(f"[+] Key '{args.key}' created.")
                    c.system.setCustomValues(k, args.sid, payload)
                    print("[+] Custom info updated successfully on retry.")
                except Exception as creation_err:
                    print(f"[!] Failed to create key: {creation_err}")
            else:
                print(f"[!] API Fault: {f.faultString}")

        c.auth.logout(k)
    except Exception as e: print(e)

if __name__ == "__main__": main()
