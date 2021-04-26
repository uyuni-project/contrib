#!/bin/bash
for x in $(spacecmd -q -- system_list|awk -F " : " '{ print $1 }');do echo ssh -o "StrictHostKeyChecking=no" root@$x "rm -r /srv/www/htdocs/pub/repositories/*"; scp -r -o "StrictHostKeyChecking=no" /srv/www/htdocs/pub/repositories/* root@$x:/srv/www/htdocs/pub/repositories;done
