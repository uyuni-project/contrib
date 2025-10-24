#!/usr/bin/python3
from datetime import datetime
import getpass
import xmlrpc.client
import sys
from socket import getfqdn
import getopt
import pdb

def usage():
	print("Usage: " + sys.argv[0] + " \
		\n\n \
		-h|--help\t\t\t\tShows this help text\n \
		-u|--user=<username with write access>\tSpecifies the API user\n \
		-p|--password\t\t\t\tSpecifies the API password\n \
		-W|--ask\t\t\t\tAsks for the API password\n \
		-L|--url=<url XMLRPC>\t\t\tXMLRPC connection URL\n \
		-s|--systemid <hostname>\t\thostname to migrate\n\n")


def main(argv):
    # defaults
    MANAGER_USER = "infobot"
    MANAGER_PASS = "infobot321"
    MANAGER_URL = "http://susemanager.suselab.localdomain/rpc/api"
    dry_run = True

    try:                                
        opts, args = getopt.getopt(argv, "hu:p:s:u:Wy", ["help", "user=", "password=", "systemid=", "url=", "ask", "yes"])
    except getopt.GetoptError:           
        usage()                          
        sys.exit(2)

    for opt, arg in opts:             
        if opt in ("-h", "--help"): 
                usage()                     
                sys.exit()                  
        elif opt in ("-u", "--user"): 
            MANAGER_USER = arg               
        elif opt in ("-p", "--password"): 
            MANAGER_PASS = arg               
        elif opt in ("-W"): 
            MANAGER_PASS = getpass.getpass("User password for \"" + MANAGER_USER + "\":")               
        elif opt in ("-L", "--url"): 
            MANAGER_URL = arg
        elif opt in ("-s", "--systemid"): 
            hostname = arg   
        elif opt in ("-y", "--yes"): 
            dry_run = False            

    session_key = None
    with xmlrpc.client.ServerProxy(MANAGER_URL) as proxy:
        session_key = proxy.auth.login(MANAGER_USER, MANAGER_PASS)
        print(f'Requesting information about {hostname}...')
        hosts = proxy.system.getId(session_key, hostname)
        try:
            system_id = hosts[0].get('id')
            print(f'The System ID for {hostname} is {system_id}')
        except IndexError as e:
            print(f"Cannot find system ID for {hostname}!")
            exit(1)
        try:
            # fetches list of migration targets available, with friendly names
            migration_data = proxy.system.listMigrationTargets(session_key,system_id, 'excludeTargetWhereMissingSuccessors' )
            count=0
            print("Available migration options:")
            for item in migration_data:
                print(f"{count} - {item['friendly']}")
                count+=1

            if count==0:
                print("NO migration options available, check SUMA WebUI")
                exit(1)
            
            try:
                answer = input("Select an option: ")
                identlist=migration_data[int(answer)]['ident']
                friendly=migration_data[int(answer)]['friendly']
            except ValueError as e:
                print("Invalid answer. Numbers only!")
                exit(1)


            base_channels = []
            for s in proxy.channel.listSoftwareChannels(session_key):
                if s['parent_label'] == '':
                    base_channels.append([s['label'], s['name']])
            print("Select a base channel:")
            count=0
            for c in base_channels:
                print(f"{count} - {c[0]} ({c[1]})")
                count=count+1
                      
            try:
                answer = input("Select an option: ")
                base = base_channels[int(answer)][0]
            except ValueError as e:
                print("Invalid answer. Numbers only!")
                exit(1)

            print(f"\n\ndestination product: {friendly}")
            print(f"selected products: {identlist}")
            print(f"base channel: {base})")
            print(f"--> DRY RUN is {str(dry_run)} (use --yes to do a real migration)\n\n")
            answer = input("Is this correct? y/n ")
            print(answer)
            if answer.lower() == "y":
                print(f"Starting migration now...")
                now = datetime.now()

                jobid=proxy.system.scheduleProductMigration(session_key, system_id, identlist , base, [], dry_run, True, True, now)
                print(f"---> Job ID: {jobid}")
                print(f"*** Use the command './get_eventdetails.py {system_id} {jobid}' to fetch the execution results for the update.")
            elif answer.lower() == "n":
                print("No, quitting now...")
        
            if (session_key) is not None:
                proxy.auth.logout(session_key)
        except ConnectionRefusedError as e:
            print(f'Connection error: {e}')
        except xmlrpc.client.Fault as e:
            print(f'Error migrating system: {e}')
            print(f'Please consider updating the system first.')
            proxy.auth.logout(session_key)
            exit(1)

if __name__ == "__main__":
	main(sys.argv[1:])

