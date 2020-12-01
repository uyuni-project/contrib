# hubtools
Tools to install and configure SUSE Manager Hub.

##
Files:
./opt/sumahub/hub_dailyrun.py
./opt/sumahub/hub_scp_bootstrap_repos.sh
./opt/sumahub/smconfig.yaml
./srv/formula_metadata/sumahub/metadata.yml
./srv/salt/sumahub/sumahub.sls
./srv/salt/sumahub/update_config_channels.py
./srv/salt/sumahub/sync_software.py
./srv/salt/sumahub/register_slave.py
./README.md

## Installation instructions

* download the files and copy to the hub-master
* Run __/opt/sumahub/hub_dailyrun.py
* In the GUI of the SUSE Manager HUB master, create a systemgroup (eg hub-slaves)
* Under the tab **Formulas** select **Sumahub**
* There will be a new tab with the name **Sumahub** and fill in all the information.
* If there are already hub slaves, add them to the systemgroup.

## Add a SUSE Manager HUB slave server:
* Install a new SUSE Manager Server.
* Register the server against the SUSE Manager HUB master.
* Configure the SUSE Manager Server via __yast susemanager_setup.
* Goto the GUI of the new installed server, but:
* Add the system to the above created systemgroup.
* Select the systemgroup and go to the tab **Sumahub**
* Add the new server as slave and, if needed, add extra base channels the hub-slave should receive.
* Perfrom a high state on the new hub slave

## Daily Bootstrap Repositories Sync
* Create a cron job to run the script /opt/sumahub/hub_scp_bootstrap_repos.sh daily. Or if you want weekly. This script will sync the bootstrap repositories to all systems.  




