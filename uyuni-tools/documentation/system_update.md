# system_update.py
  This script performs several tasks:
* based on the settings in configsm.yaml it can do a product migration
* it will apply the latest updates available in assigned channels to the server
* will apply configuration channels, if defined
* if updates are being applied, it will reboot the server. This can be prevented with a parameter.
* scripts and/or salt state channels that need to be executed before and after the maintenance can be enabled via an option. 

Arguments:
* -h, --help → shows the help message and exits
* -s SERVER, --server SERVER → name of the server to receive config update. Required
* -n, --noreboot → Do not reboot the server after patching or product migration.
* -d, --nodryrun → Do not run a dry run before performing a product migration.
* -f, --forcereboot → Force a reboot server after patching or product migration.
* -c, --applyconfig → Apply configuration after and before patching
* -u, --updatescript → Execute the server-specific _start and _end scripts
* -p POST_SCRIPT, --post_script POST_SCRIPT → Execute the given script on the SUSE Manger Server when system_update has finished
* --version → show program's version number and exit


monitoring
----------
Starting with version 2.0.1 (December 2025), the script will also report the status of the maintenance to a database. 
The following status will be reported:
* running: the update is still running, and in the comment field the action is recorded
* finished: the maintenance was successful and finished
* error: the maintenance failed. In the comment field the error message is recorded.

To enable this monitoring, the database connection parameters must be set in configsm.yaml. And also the service smtdb should be running. See .... for more information.

The following should be defined in the configsm.yaml (and if needed change the parameters):
<pre>
monitoring:
  hostname: 127.0.0.1
  port: 5000
  monitoring_system_update: True
  monitoring_system_highstate: False
</pre>

product migration
-----------------
To enable product migration, the following should be defined in the configsm.yaml (and if needed change the parameters):
<pre>
maintenance:
  sp_migration_project:
    {current CLM project}: {target CLM project}
  sp_migration:
    {current channel prefix>: {target channel prefix}
  exception_sp:
    {current CLM project or channel prefix}:
      - {hostname as it is registered in MLM}
</pre>
