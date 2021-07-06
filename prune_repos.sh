#!/bin/bash
# Script to remove old packages from the database for all channels and remove from disk.
#######
# /root/.patchuser contains the auth details in this format:
#[Spacewalk]
#spw_server = fqdn-of-uyuni-server
#spw_user   = username
#spw_pass   = userpass
#
# Remove pkgs without a channel
/root/spacewalk-remove-old-packages.py -c /root/.patchuser -w
/root/spacewalk-remove-old-packages.py -c /root/.patchuser -A
/usr/bin/spacewalk-data-fsck -r -S -C -O

