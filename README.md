# SUSE-Manager-Tools version 2

This is the new version of the SUSE Manager Tools. The major changes are:
- logging level can be set separately for screen and files.
- for some of the major components in system_update.py it can be configured how the script should react. For example exit the script or only report an error and continue.
- optimized code.
- only use https as connection between the scripts and SUSE Manager Server.

The following scripts will not be longer part of the set. Please let me know if you want them back:
- cve_report.py
- channel_cloner.py

What is still not include:
- The script system_update.py will perform an update of the maintenance stack before applying the other updates. This is only available for "zypper" (SLES). Plan to add other distributions in the future.

The default location is /opt/susemanager.

General configuration is done in configsm.yaml:
- The file configsm.yaml should be in the same directory as the scripts. And before using check the file and correct the information.
- Contains the login credentials and the SUSE Manager Server (which should be given in FQDN) 
- Contains the location of the log and script directories
- Should a mail being send in case of an error and to whom
- Information needed for SP migration for system update
- Containg the settings for logging and how the system_update.py script should react.
- Run update_configsm.sh first!!!


The following scripts are included:
- create_repos.py
From a pre-defined yaml channels will be created in the give parent channels. This also includes the creation of the repositories and sync schedule. Also the initial synchronization can be started.

- create_software_project.py
This will create a new software content lifecycle project. It can also be used to add or remove source channels from an existing project.

- group_system_update.py
This script will update all systems in the given system group.

- smtools.py
This is the library containing all functions and cannot be executed.

- sync_channel.py
This will clone the give channel with the channel it is cloned from.

- sync_environment.py
This script can be used to updated (merge the patches and packages that are available in the channels they are cloned from) an environment across all lifecycle projects. 

- sync_stage.py
This will clone the given basechannel and all its child channels from the channels they are cloned from. Or it will update the given environment in the given project.

- system_rereg.py
When a system needs to be moved from SUSE Manager Server to a SUSE Manager Proxy or from a SUSE Manager Proxy to another SUSE Manager Proxy this script can be used.

- system_update.py
This script will can perform several tasks:
* based on the settings in configsm.yaml it can do a Support Pack Migration
* it will apply the latest updates available in assigned channels to the server
* will apply configuration channels, if defined
* if updates are being applied it will reboot the server. This can be prevented with a parameter.
* scripts and/or salt state channels that need to be executed before and after the maintenance can be enabled via an option. 

- update_configsm.sh
This script will add the new parameters to configsm.yaml. Please run FIRST!!!!


Each script will have a --help to see all available parameters. See included man-page for more information (call with: man -l SUSE-Manager-tools.man).



Known Issues:
=============
- During the execution a python dump is written telling something related to CONFIGSM, this will in general mean that your configsm.yaml is not correct. Please run update_configsm.sh. If you still have problems, compare the configsm.yaml part of this git with yours.
- When you receive an error regarding the SSL certificate (for example: "ssl.CertificateError: hostname 'mbsuma4' doesn't match 'mbsuma4.mb.int'") there are 2 possible causes:
* In configsm.yaml the option [suman][server] should contain the FQDN of the SUSE Manager Server.
* The SUSE Manager Server certificate is not imported. Perform the following steps:
  - copy from the SUSE Manager Server /srv/www/htdocs/pub/RHN-ORG-TRUSTED-SSL-CERT to /etc/pki/trust/anchors/ on the server you are running the scripts.
  - run the command (as root): update_ca_certificates

How to use:
- Each script will have a help option: --help 

GNU Public License. No warranty. No Support 
For question/suggestions/bugs mail: michael.brookhuis@suse.com
Created by: SUSE Michael Brookhuis July 2020



