# hubtools
Tools to install and configure SUSE Manager Hub.

##
Files:
/opt/sumahub/hub_dailyrun.py
/opt/sumahub/hub_scp_bootstrap_repos.sh
/opt/sumahub/smconfig.yaml
/srv/formula_metadata/sumahub/form.yml
/srv/formula_metadata/sumahub/metadata.yml
/srv/salt/sumahub/sumahub.sls
/srv/salt/sumahub/update_config_channels.py
/srv/salt/sumahub/sync_software.py
/srv/salt/sumahub/register_slave.py
/README.md

## Installation instructions

* download the files and copy to the hub-master
* Run /opt/sumahub/hub_dailyrun.py
* In the GUI of the SUSE Manager HUB master, create a systemgroup (eg hub-slaves)
* Under the tab **Formulas** select **Sumahub**
* There will be a new tab with the name **Sumahub** and fill in all the information.
* If there are already hub slaves, add them to the systemgroup.
* Create a state configuration channel with the name **sumahub** and for the init.sls use the content of /srv/salt/sumahub/sumahub.sls.
* Assing this configuration channel to the above created systemgroup.

## Add a SUSE Manager HUB slave server:
* Install a new SUSE Manager Server.
* Register the server against the SUSE Manager HUB master.
* Configure the SUSE Manager Server via yast susemanager_setup.
* Goto the GUI of the new installed server, but:
* Add the system to the above created systemgroup.
* Select the systemgroup and go to the tab **Sumahub**
* Add the new server as slave and, if needed, add extra base channels the hub-slave should receive.
* Perfrom a high state on the new hub slave

## Daily jobs running on master ISS
* Create a cron job to run the script /opt/sumahub/hub_scp_bootstrap_repos.sh daily. Or if you want weekly. This script will sync the bootstrap repositories to all systems.  
* Create a cron job to run the script /opt/sumahub/hub_dailyrun.py daily. Or if you want weekly. This script will update the /srv/formula_metadata/sumahub/form.yml with actual data. This should also run after installing these tools.
* example:

## Jobs running on slave
* The job update_config_channels.py will run every day and will update all salt configuration channels. The highstate will create a cron job for this. This will be logged to /var/log/rhn/sumahub/update_config_channels.log
* The job sync_software.py will normally only run during a highstate. When channels to be synchronized are changed (currently only adding, see below), a highstate has to be performed on all slaves. This highstate will update the sumahub.yaml and execute this script. Every night, taskomatic will synchronize all assigned channels automatically. This will be logged to /var/log/rhn/sumahub/sync_software.log. 
* The job register_slave.py will normally only run during a highstate and only the first time. This will be logged to /var/log/rhn/sumahub/register_slave.log 

## What is not in (on the moment)
* Software channels and configuration channels are not been removed via the formula. 

## Known issues
* revision numbers of init.sls can not be set using the API. They will be reported as to be changed on every run of update_config_channels.py
* revision numbers of none init.sls can not be set using the API on creation. During the next change, the revision will be updated. They will be reported as to be changed on every run of update_config_channels.py

