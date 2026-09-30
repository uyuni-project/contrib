#!/usr/bin/env python3
"""
SUSE Manager / Uyuni API - Activation Key Checker
"""
import argparse, xmlrpc.client, ssl, getpass, sys

def parse_args():
    p = argparse.ArgumentParser(description="Check SUSE Manager Activation Key Details")
    p.add_argument('-s', '--server', help="Server hostname (defaults to https://<server>/rpc/api)")
    p.add_argument('--url', help="Full API URL (overrides --server)")
    p.add_argument('-u', '--user', dest='username', required=True, help="Username")
    p.add_argument('-p', '--password', dest='password', required=False, help="Password")
    p.add_argument('-k', '--key', dest='key', required=True, help="The Activation Key")
    p.add_argument('--verify', dest='verify', action='store_true', help="Verify SSL certificate")
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
        print(f"[*] Checking details for key: '{args.key}'...")
        d = client.activationkey.getDetails(key, args.key)
        print("\n=== Activation Key Report ===")
        print(f"Key Label:       {d.get('key')}")
        print(f"Base Channel:    {d.get('base_channel_label', 'None')}")
        print(f"Usage Limit:     {d.get('usage_limit', 'Unlimited')}")
        print(f"Child Channels:  {len(d.get('child_channels', []))}")
        for c in d.get('child_channels', []): print(f"  - {c.get('label')}")
        print(f"Packages:        {len(d.get('packages', []))}")
        print(f"Entitlements:    {', '.join(d.get('entitlements', []))}")
        client.auth.logout(key)
    except Exception as e: print(f"[!] Error: {e}")

if __name__ == "__main__": main()
