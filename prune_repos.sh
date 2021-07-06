#!/bin/bash
# A script to purge old and orphaned packages from the database for all channels and then delete from disk to free space. Use at own risk. 
#######
# Remove pkgs without a channel
/root/spacewalk-remove-old-packages.py -c /root/.patchuser -w
/root/spacewalk-remove-old-packages.py -c /root/.patchuser -A
/usr/bin/spacewalk-data-fsck -r -S -C -O
