# group_system_update.py
  This script will call the system_update.py script to perform updates on the servers within the given system group. 

Arguments:
* -h, --help → shows the help message and exits
* -g GROUP, --group GROUP → name of the server to receive config update. Required
* -n, --noreboot → Do not reboot the server after patching or product migration.
* -d, --nodryrun → Do not run a dry run before performing a product migration.
* -f, --forcereboot → Force a reboot server after patching or product migration.
* -c, --applyconfig → Apply configuration after and before patching
* -u, --updatescript → Execute the server-specific _start and _end scripts
* -p POST_SCRIPT, --post_script POST_SCRIPT → Execute the given script on the SUSE Manger Server when system_update has finished
* --version → show program's version number and exit

configuration
-------------
The following option in configsm.yaml is used for this script:
<pre>
maintenance:
  wait_between_systems: 2
  wait_between_events_check: 30
</pre>
