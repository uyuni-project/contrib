#!/usr/bin/python3
#
#  runscript_sm.py - eexecute remote commands on a list of machines
#
#  Author: Erico Mendonca (emendonca@suse.com)
#  Sep/2024 (first released on Jan/2014)
#  Versao: 2.0 
#  

import xmlrpc.client
import sys
import getopt
import string
import getpass
from datetime import datetime

def usage():
	print("Usage: " + sys.argv[0] + " \
		\n\n \
		\t-h|--help\t\t\tShows this help text\n \
		\t-u|--user=<username with write access>\t\t\tSpecifies the API user\n \
		\t-p|--password\t\t\tSpecifies the API password\n \
		\t-W\t\t\tAsks for the API password\n \
		\t-f|--hostfile=<file with hosts list>\t\t\tFile containing the hostnames for the machines, one per line\n \
		\t-L|--url=<XMLRPC url>\t\t\tXMLRPM connection URL\n \
		\t-o|--outputfile=<output file name>\t\t\tFile name which will contain all the job IDs. Default: jobs.csv\n \
		\t-s|--script=<bash script>\t\t\tScript to be executed on all machines\n \
		\t-r|--reboot\t\t\tPerform a reboot on the machines after execution\n \
		\t-d|--debug\t\t\tenable debugging\n\n")

def main(argv):

	## defaults
	serverurl = "http://susemanager.suselab.localdomain/rpc/api"
	user = "admin"
	password = ""
	hostfile = ""
	scriptfile = ""
	reboot = 0
	debug = 0
	outputfile = "jobs.csv"
	try:                                
		opts, args = getopt.getopt(argv, "hu:p:f:L:o:s:rdW", ["help", "user=", "password=", "hostfile=", "url=", "outputfile=", "script=","reboot", "debug"])
	except getopt.GetoptError:           
		usage()                          
		sys.exit(2)

	for opt, arg in opts:             
		if opt in ("-h", "--help"): 
			usage()                     
			sys.exit()                  
		elif opt in ("-u", "--user"): 
			user = arg               
		elif opt in ("-p", "--password"): 
			password = arg               
		elif opt in ("-W"): 
			password = getpass.getpass("Password for user \"" + user + "\":")               
		elif opt in ("-f", "--hostfile"): 
			hostfile = arg
		elif opt in ("-L", "--url"): 
			serverurl = arg
		elif opt in ("-s", "--script"): 
			scriptfile = arg
		elif opt in ("-o", "--outputfile"): 
			outputfile = arg
		elif opt in ("-r", "--reboot"): 
			reboot=1
		elif opt in ("-d", "--debug"): 
			debug=1

	source = "".join(args) 

	if debug==1:
		print(f"user={user}\nhostfile={hostfile}\nurl={serverurl}\nscript={scriptfile}")

	if hostfile=="" or user=="" or password=="":
		print("Inform at least the username, password, name of the script and a hosts file.")
		usage()
		sys.exit(1)

	## rotina principal
	hosts=[]
	f = open(hostfile)
	for line in f.readlines():
		if line.rstrip('\n') != "": 
			hosts.append(line.rstrip('\n')) 
	f.close()

	# executa os comandos
	print("---> Using server: " + serverurl)

	client = xmlrpc.client.Server(serverurl, verbose=debug)
	key = client.auth.login(user, password)

	# busca de IDs
	idlist=[]
	runhosts=[]
	foutput = open(outputfile, "w+")
	for k in hosts:
		print("Looking for ID: [", k, "]")
		ret = client.system.searchByName(key, k)
		if len(ret) > 0:
			print(f"---> ID found: {ret[0].get('id')}")
			idlist.append(ret[0].get('id'))
			runhosts.append(k)
		else:
			print("---> could not find ID for the host ",k)
			
	
	print(f"*** Total of {len(idlist)} IDs found from a total of {len(hosts)}.")
	
	if len(idlist) < len(hosts):	
		r=input("Some IDs were not found. Continue (Y/N)?")
		if r == 'Y' or r == 'y':
			print("Continuing...")
		else:
			print ("*** operation aborted.")
			client.auth.logout(key)
			foutput.close()
			sys.exit(1)
	# executa reboot
	if reboot == 1:
		for x in idlist:
			print(f"Scheduling a reboot for ID {x}")
			today = datetime.today()
			earliest_occurrence = xmlrpc.client.DateTime(today)
			client.system.scheduleReboot(key, x, earliest_occurrence)

	# executa comando
	if scriptfile != "":
		print(f"*** Executing script {scriptfile} on IDs {idlist}")
		today = datetime.today()
		earliest_occurrence = xmlrpc.client.DateTime(today)
		f = open(scriptfile)
		scripttext=f.read()
		f.close()
		try:
			jobid=client.system.scheduleScriptRun(key, idlist, 'root', 'root', 600, scripttext, earliest_occurrence)
		except:
			print("---> ERROR while scheduling script execution on hosts")
		
		if jobid > 0:
			print(f"---> Job ID: {jobid}")
			strout=jobid,scriptfile,len(idlist),runhosts
			foutput.write(str(strout).strip('() '))
			foutput.write('\n')
			print(f"*** Success. Jobs list was created on {outputfile}")
			print("*** Use the getresults_sm.py script to fetch the execution status for all jobs and to obtain the script results.")

	client.auth.logout(key)
	foutput.close()


if __name__ == "__main__":
	main(sys.argv[1:])


