#!/usr/bin/env python3
"""
SUSE Manager / Uyuni API - Get Results from Job CSV
Reads jobs.csv, fetches results, writes to output.csv
"""
import argparse, xmlrpc.client, ssl, getpass, sys, csv, os

def main():
    p = argparse.ArgumentParser()
    p.add_argument('-s', '--server'); p.add_argument('--url'); p.add_argument('-u', '--user', required=True)
    p.add_argument('-p', '--password')
    p.add_argument('--jobs', default='jobs.csv', help="Input CSV file (hostname,job_id)")
    p.add_argument('--verify', action='store_true')
    args = p.parse_args()

    if args.url: api_url = args.url
    elif args.server: api_url = f"https://{args.server}/rpc/api"
    else: print("[!] Error: Provide -s/--server or --url"); sys.exit(1)

    if not os.path.exists(args.jobs): print(f"[!] Jobs file {args.jobs} not found."); sys.exit(1)

    pwd = args.password or getpass.getpass()
    ctx = ssl.create_default_context()
    if not args.verify: ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE

    try:
        c = xmlrpc.client.ServerProxy(api_url, context=ctx); k = c.auth.login(args.user, pwd)
        
        results_data = []
        
        with open(args.jobs, 'r') as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) < 2: continue
                host, aid = row[0], int(row[1])
                print(f"[*] Checking Job {aid} for {host}...")
                
                try:
                    res = c.system.getScriptResults(k, aid)
                    if not res:
                        print("    -> Pending/No Result")
                        results_data.append([host, aid, "PENDING", ""])
                    else:
                        # Usually returns list, take first
                        r = res[0]
                        rc = r.get('returnCode')
                        raw_out = r.get('output', '')
                        # Flatten output to single line, escape newlines
                        out = raw_out.replace('\r', '').replace('\n', '\\n')
                        
                        print(f"    -> Return Code: {rc}")
                        results_data.append([host, aid, rc, out])
                except Exception as e:
                    print(f"    -> Error: {e}")
                    results_data.append([host, aid, "ERROR", str(e)])

        # Write Output with quoting
        with open('output.csv', 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f, quoting=csv.QUOTE_ALL)
            writer.writerow(['Hostname', 'Job ID', 'Return Code', 'Output'])
            writer.writerows(results_data)
            
        print(f"\n[+] Done. Results saved to 'output.csv'.")
        c.auth.logout(k)
    except Exception as e: print(f"Global Error: {e}")

if __name__ == "__main__": main()
