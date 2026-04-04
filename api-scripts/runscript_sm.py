#!/usr/bin/env python3
"""
SUSE Manager / Uyuni API - Run Script (Bulk Mode)
Reads a list of hosts, executes script, writes Job IDs to CSV.
"""
import argparse, xmlrpc.client, ssl, getpass, sys, datetime, os, csv

def main():
    p = argparse.ArgumentParser()
    p.add_argument('-s', '--server'); p.add_argument('--url'); p.add_argument('-u', '--user', required=True)
    p.add_argument('-p', '--password')
    p.add_argument('--hosts', required=True, help="File containing hostnames (one per line)")
    p.add_argument('--script', required=True, help="File containing the script to execute")
    p.add_argument('--verify', action='store_true')
    args = p.parse_args()

    if args.url: api_url = args.url
    elif args.server: api_url = f"https://{args.server}/rpc/api"
    else: print("[!] Error: Provide -s/--server or --url"); sys.exit(1)

    # Read Script
    if not os.path.exists(args.script): print(f"[!] Script file {args.script} not found."); sys.exit(1)
    with open(args.script, 'r') as f: script_content = f.read()

    # Read Hosts
    if not os.path.exists(args.hosts): print(f"[!] Hosts file {args.hosts} not found."); sys.exit(1)
    with open(args.hosts, 'r') as f: target_hosts = [line.strip() for line in f if line.strip()]

    pwd = args.password or getpass.getpass()
    ctx = ssl.create_default_context()
    if not args.verify: ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE

    try:
        c = xmlrpc.client.ServerProxy(api_url, context=ctx); k = c.auth.login(args.user, pwd)
        print(f"[*] Authenticated. Processing {len(target_hosts)} hosts...")
        
        jobs = []
        
        for host in target_hosts:
            print(f"[*] resolving {host}...")
            # Resolve ID
            try:
                systems = c.system.getId(k, host)
                if not systems:
                    print(f"[-] Host {host} not found.")
                    continue
                
                sid = systems[0].get('id')
                print(f"    -> ID: {sid}. Scheduling script...")
                
                aid = c.system.scheduleScriptRun(k, sid, "root", "root", 600, script_content, datetime.datetime.now())
                print(f"    -> Job ID: {aid}")
                jobs.append([host, aid])
                
            except Exception as e:
                print(f"[!] Error processing {host}: {e}")

        # Write Output
        with open('jobs.csv', 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerows(jobs)
        
        print(f"\n[+] Done. {len(jobs)} jobs scheduled. Saved to 'jobs.csv'.")
        c.auth.logout(k)
        
    except Exception as e: print(f"Global Error: {e}")

if __name__ == "__main__": main()
