#!/usr/bin/env python3
"""
SUSE Manager / Uyuni API - Search Packages
"""
import argparse, xmlrpc.client, ssl, getpass, sys

def main():
    p = argparse.ArgumentParser()
    p.add_argument('-s', '--server'); p.add_argument('--url'); p.add_argument('-u', '--user', required=True)
    p.add_argument('-p', '--password'); p.add_argument('--query', required=True)
    p.add_argument('-c', '--channel', help="Channel label (Recommended for speed/permissions)")
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
        print(f"[*] Searching packages for: {args.query}")
        
        results = []
        if args.channel:
             print(f"[*] Listing packages in channel '{args.channel}'...")
             try:
                 all_pkgs = c.channel.software.listAllPackages(k, args.channel)
                 results = [p for p in all_pkgs if args.query.lower() in p.get('name','').lower()]
             except Exception as e:
                 print(f"[!] Channel search failed: {e}")
        else:
             # Use only advanced search to avoid 'name' API security exception
             try:
                # Lucene query syntax
                results = c.packages.search.advanced(k, f"name:{args.query}")
             except Exception as e: 
                print(f"[!] Advanced search failed: {e}")
                print("    Try using -c/--channel to search within a specific channel.")
                # Auto-suggest channels
                print("\n[*] Fetching top 5 available channels for reference:")
                try:
                    for ch in c.channel.listSoftwareChannels(k)[:5]:
                         print(f"    - {ch.get('label')}")
                except: pass

        print(f"{'ID':<10} | {'Name':<30} | {'Version'}")
        print("-" * 60)
        for r in results:
             ver = r.get('version') or r.get('package_version')
             rel = r.get('release') or r.get('package_release')
             print(f"{r.get('id'):<10} | {r.get('name'):<30} | {ver}-{rel}")
        print(f"\nFound {len(results)} matches.")
        c.auth.logout(k)
    except Exception as e: print(f"Error: {e}")

if __name__ == "__main__": main()
