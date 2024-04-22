#!/usr/bin/env python3
"""
Script Name: Last Update Export

Description:
This script automates the export of software channels using an XML-RPC client to interface with a server for use in Airgapped Environments or Disconnected SUMA.
It is designed to operate on a scheduled basis (daily), removing the previous day's export data, and writing new export logs into designated directories.
The concept behind the script is to use the API's to determine which channels have been updated within the defined dates, and export only those channels, as such, 
this creates a more streamlined export/import for Disconnected or Airgapped systems.

Instructions:
1. Ensure Python 3.x is installed on your system.
2. This script must be run with root privileges to manage file permissions and perform system-level operations.
3. Before running the script, update the `/root/.mgr-sync` configuration file with the correct manager login credentials using `mgr-sync -s refresh` to create the credentials file.
4. Customize the directory path, by default `/mnt` was chosen but this could be any location you want, ensure the location has ample free space.
5. Customize the 'RSYNC_USER' and 'RSYNC_GROUP' in the script to match the user and group names on your system.
6. Schedule this script using a cron job or another scheduler for daily execution.

Intended Usage:
- Scheduled daily exports of software channel data.
- Logging of export operations in '/mnt/logs'.
- Exports are stored in '/mnt/export/updates'.
- This script is intended for systems administrators managing software channel updates for Airgapped Environments.

Ensure the server and paths are correctly configured and accessible before running the script.
"""

import os
import subprocess
import datetime
from xmlrpc.client import ServerProxy
import ssl
import socket
import configparser
import shutil
import shlex

# Configuration Variables
BASE_DIR = "/mnt"  # Define base directory where the exports will be.
OUTPUT_DIR = os.path.join(BASE_DIR, "export/updates")
LOG_DIR = os.path.join(BASE_DIR, "logs")
TODAY = datetime.date.today()
TARGET_DATE = TODAY - datetime.timedelta(days=1)  # Define the number of days back for export, 1 day by default
RSYNC_USER = "rsyncuser"  # Define rsync user
RSYNC_GROUP = "users"     # Define rsync group

def setup_directories(base_path, output_path, log_path):
    if not os.path.exists(base_path):
        os.makedirs(base_path, exist_ok=True)
    if not os.path.exists(log_path):
        os.makedirs(log_path, exist_ok=True)
    if os.path.exists(output_path):
        shutil.rmtree(output_path)
    os.makedirs(output_path, exist_ok=True)

def setup_logging(LOG_DIR, TODAY):
    log_file_path = os.path.join(LOG_DIR, f"{TODAY}-daily_export.log")
    return log_file_path

def create_client():
    config_path = os.path.expanduser('/root/.mgr-sync')
    config = configparser.ConfigParser()
    with open(config_path, 'r') as f:
        config.read_string('[DEFAULT]\n' + f.read())
    manager_login = config.get('DEFAULT', 'mgrsync.user')
    manager_password = config.get('DEFAULT', 'mgrsync.password')
    suma_fqdn = socket.getfqdn()
    manager_url = f"https://{suma_fqdn}/rpc/api"
    context = ssl.create_default_context()
    client = ServerProxy(manager_url, context=context)
    return client, client.auth.login(manager_login, manager_password)

# Setup Directories and Logging
setup_directories(BASE_DIR, OUTPUT_DIR, LOG_DIR)
log_file_path = setup_logging(LOG_DIR, TODAY)

# Create XML-RPC Client
client, key = create_client()

# Process channels
channel_list = client.channel.listVendorChannels(key)
for channel in channel_list:
    build_date, channel_label = client.channel.software.getChannelLastBuildById(key, channel["id"]).split()[0], channel["label"]
    build_date = datetime.datetime.strptime(build_date, "%Y-%m-%d").date()

    if TARGET_DATE <= build_date <= TODAY:
        channel_OUTPUT_DIR = os.path.join(OUTPUT_DIR, channel_label)
        os.makedirs(channel_OUTPUT_DIR, exist_ok=True)
        options_dict = {
            "outputDir": channel_OUTPUT_DIR,
            "orgLimit": "2",  # Define the default Organization, 2 by default assuming there is only 1, if multiple set this to the one you assign for exporting.
            "logLevel": "error",  # Set as 'error' by default but change to 'debug' for detailed logging
            "packagesOnlyAfter": TARGET_DATE.strftime('%Y-%m-%d')
        }
        options = ' '.join([f"--{opt}='{val}'" for opt, val in options_dict.items()])
        command = f"inter-server-sync export --channels='{channel_label}' {options}"
        command_args = shlex.split(command)
        with open(log_file_path, "a") as log_file:
            subprocess.run(command_args, stdout=log_file, stderr=subprocess.STDOUT, check=True)
            current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            completion_message = f"{current_time} Export for channel {channel_label} completed.\n"
            log_file.write(completion_message)

# Change ownership of the output directory
subprocess.run(["chown", "-R", f"{RSYNC_USER}:{RSYNC_GROUP}", OUTPUT_DIR], check=True)
