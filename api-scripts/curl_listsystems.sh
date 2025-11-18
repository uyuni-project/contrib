#!/bin/bash

API="https://susemanager.suselab.localdomain/rhn/manager/api"
POSTDATA='{"login": "infobot", "password": "infobot321"}'
CMD="curl -LSks -c cookies.txt -b cookies.txt -H @headers.txt"

# do the login
$CMD -d "${POSTDATA}" ${API}/auth/login
if [ $? -eq 0 ]; then
	echo
	echo "authenticated successfully"
	echo

	# execute the command...
	OUTPUT=$($CMD ${API}/system/listSystems)

	# do the logout
	# the POST data here can be empty, as it uses cookie data
	$CMD -d "" ${API}/auth/logout
	if [ $? -eq 0 ]; then
		echo
		echo "logged out"
		echo
	else
		echo "error logging out"
		exit 1
	fi
else
	echo "error authenticating"
	exit 1
fi


echo "result: $OUTPUT"
