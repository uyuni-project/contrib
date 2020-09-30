# hubtools
Tools to install and configure SUSE Manager Hub.

## Installation instructions

* download the files and copy to the hub-master
* In the GUI of the SUSE Manager HUB master, create a systemgroup (eg hub-slaves)
* Under the tab **Formulas** select **Sumahub**
* There will be a new tab with the name **Sumahub** and fill in all the information.
* Add the systemgroup to the activation key used to register the SUSE Manager Server that will become a HUB slave.


## Add a SUSE Manager HUB slave server:
* Install a new SUSE Manager Server.
* Register the server against the SUSE Manager HUB master.
* Configure the SUSE Manager Server.
* Goto the GUI of the new installed server, but:
  * use the same organization name as from the HUB Master
  * the admin should be the same a entered in the formula
* Issue the following command: __salt-call state.apply hub

## Note
* Working on a state that will configure the SUSE Mananager on the HUB slave
* Working on a script to run mgr-inter-sync to synchronize all the software channels
* Working on a state to sync the bootstrap repositories



