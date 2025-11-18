#!/usr/bin/python3
#
#  getresults_sm.py - fetches results of a batch remote command execution from SUSE Manager
#
#  Author: Erico Mendonca (emendonca@suse.com)
#  Sep/2024 (first released on Jan/2014)
#  Version: 2.0 
#  

import xmlrpc.client
import sys
import getopt
import string
import getpass
from datetime import datetime

def dequote(s):
	s=s.strip()
	if s.startswith( ("'", '"') ) and s.endswith( ("'",'"') ) and (s[0] == s[-1]):
		s = s[1:-1]
	return s

def usage():
	print("Usage: " + sys.argv[0] + " \
		\n\n \
		\t-h|--help\t\t\tShows this help text\n \
		\t-u|--user=<username with write access>\t\t\tSpecifies the API user\n \
		\t-p|--password\t\t\tSpecifies the API password\n \
		\t-W\t\t\tAsks for the API password\n \
		\t-R|--resultsfile=<jobs list CSV file>\t\t\tFile containing the corresponding hostnames and jobs, one per line\n \
		\t-L|--url=<url XMLRPC>\t\t\tXMLRPC connection URL\n \
		\t-d|--debug\t\t\tenable debugging\n\n")

def main(argv):

	## defaults
	serverurl = "http://susemanager.suselab.localdomain/rpc/api"
	user = "admin"
	password = ""
	debug = 0
	resultsfile = "jobs.csv"
	outputfile = "results.csv"
	try:                                
		opts, args = getopt.getopt(argv, "hu:p:R:L:s:ro:dW", ["help", "user=", "password=", "resultsfile=", "url=", "outputfile=", "debug"])
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
			password = getpass.getpass("User password for \"" + user + "\":")               
		elif opt in ("-R", "--resultsfile"): 
			resultsfile = arg
		elif opt in ("-o", "--outputfile"): 
			outputfile = arg
		elif opt in ("-L", "--url"): 
			serverurl = arg
		elif opt in ("-d", "--debug"): 
			debug=1

	source = "".join(args) 

	if debug==1:
		print("user=" + user + "\nresultsfile=" + resultsfile + "\nurl=" + serverurl + "\noutputfile=" + outputfile)

	if resultsfile=="" or user=="" or password=="":
		print("Please inform at least a user, password and results file name.")
		usage()
		sys.exit(1)

	## rotina principal
	idlist=[line.rstrip('\n').split(',') for line in open (resultsfile)]

	print(f"*** Total of {len(idlist)} events to process.")

	# executa os comandos
	client = xmlrpc.client.Server(serverurl, verbose=debug)
	key = client.auth.login(user, password)

	foutput = open(outputfile,"w+")
	for k in idlist:
		print(f"Looking up results for job # [{k[0]}], command: [{k[1]}] executed on {k[2]} hosts.")
		ret = client.system.getScriptResults(key, int(k[0]))
		if len(ret) > 0:
			for x in ret:
				print(f"---> Return code: {x.get('returnCode')}")
				strout=dequote(k[1]),x.get('serverId'),x.get('returnCode'),x.get('startDate').value,x.get('stopDate').value,x.get('output')
				foutput.write(str(strout).strip('() '))
				foutput.write('\n')
		else:
			print("... action not completed")
			strout=k[1],k[0],-1,"",""
			foutput.write(str(strout).strip('() '))
			foutput.write('\n')

	client.auth.logout(key)
	foutput.close()

	print(f"*** Success. Results written to {outputfile}")
if __name__ == "__main__":
	main(sys.argv[1:])


