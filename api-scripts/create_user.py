#!/usr/bin/env python3
"""
SUSE Manager / Uyuni API - Create User
"""
import argparse, xmlrpc.client, ssl, getpass, sys

def parse_args():
    p = argparse.ArgumentParser(description="Create User")
    p.add_argument('-s', '--server', help="Server hostname")
    p.add_argument('--url', help="Full API URL")
    p.add_argument('-u', '--user', dest='username', required=True, help="Admin Username")
    p.add_argument('-p', '--password', dest='password', required=False, help="Admin Password")
    p.add_argument('--new-user', required=True, help="New Username")
    p.add_argument('--new-pass', required=True, help="New Password")
    p.add_argument('--email', required=True, help="Email")
    p.add_argument('--first', default="New", help="First Name")
    p.add_argument('--last', default="User", help="Last Name")
    p.add_argument('--verify', dest='verify', action='store_true', help="Verify SSL")
    return p.parse_args()

def main():
    args = parse_args()
    if args.url: api_url = args.url
    elif args.server: api_url = f"https://{args.server}/rpc/api"
    else: print("[!] Error: Provide -s/--server or --url"); sys.exit(1)

    password = args.password or getpass.getpass(prompt=f"Password for {args.username}: ")
    context = ssl.create_default_context()
    if not args.verify:
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

    try:
        client = xmlrpc.client.ServerProxy(api_url, context=context)
        key = client.auth.login(args.username, password)
        # Corrected signature: (key, login, pass, first, last, email, usePam_int)
        # Removed the empty prefix string, added 0 for usePam
        if client.user.create(key, args.new_user, args.new_pass, args.first, args.last, args.email, 0) == 1:
            print(f"[+] User '{args.new_user}' created.")
        client.auth.logout(key)
    except Exception as e: print(f"[!] Error: {e}")

if __name__ == "__main__": main()
