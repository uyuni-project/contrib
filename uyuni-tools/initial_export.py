#!/usr/bin/env python3

"""
Description: This script is used for the initial export of channels for the
             customer. This means if they are a new to SUMA, or an existing
             user and we don't know when they got their last update from the
             SCC, or they are getting a new channel for i.e. a new Service Pack.

             This script automates the process of exporting channel data from a
             specified directory, clearing the directory before use, and
             handling file and user permissions. It reads channel names from a
             specified text file and executes a sync/export command for each.

             The script logs each export operation to a daily log file and
             changes the ownership of the exported files to a specific user and
             group.

Constants:
             BASE_DIR - Base directory from which channels are exported.
             RSYNC_USER - Username owning the exported files.
             RSYNC_GROUP - Group owning the exported files.
             LOG_DIR - Directory where logs are stored.
             CHANNELS_FILE - Path to the file containing channel names, one
                             channel per line.
             TODAY - Today's date, used for naming the log file.

Instructions:
             1. THIS SCRIPT REQUIRES THE USE OF THE `mgr-sync -s refresh`
                CREDENTIALS FILE!
             2. Ensure paths for BASE_DIR, LOG_DIR, and CHANNELS_FILE are
                correctly set according to your system configuration.
             3. Adjust RSYNC_USER and RSYNC_GROUP to match appropriate user
                and group on your system.
             4. Ensure 'channels.txt' contains the list of channels to be
                exported, one per line.
             5. Run this script with sufficient permissions to access and modify
                the specified directories and files.
"""

import os
import shutil
import datetime
import subprocess
import configparser
import ssl
import socket
from xmlrpc.client import ServerProxy
import shlex

# Constants
BASE_DIR = "/mnt"
OUTPUT_DIR = os.path.join(BASE_DIR, "export/initial")
LOG_DIR = os.path.join(BASE_DIR, "logs")
SCRIPTS = os.path.join(BASE_DIR, "scripts")
RSYNC_USER = "rsyncuser"
RSYNC_GROUP = "users"
CHANNELS_FILE = os.path.join(SCRIPTS, "channels.txt")
TODAY = datetime.date.today().strftime("%Y-%m-%d")

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
    key = client.auth.login(manager_login, manager_password)
    return client, key

def setup_directories():
    os.makedirs(LOG_DIR, exist_ok=True)
    if os.path.exists(OUTPUT_DIR):
        shutil.rmtree(OUTPUT_DIR)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

def setup_logging():
    log_file_path = os.path.join(LOG_DIR, f"{TODAY}-initial-export.log")
    return log_file_path

def get_channels():
    """
    Check if channels.txt exists and is not empty, or use API call.
    """
    if os.path.exists(CHANNELS_FILE) and os.path.getsize(CHANNELS_FILE) > 0:
        with open(CHANNELS_FILE, 'r') as file:
            channels = [line.strip() for line in file if line.strip()]
    else:
        client, key = create_client()
        channel_data = client.channel.listVendorChannels(key)
        channels = [channel['label'] for channel in channel_data if 'label' in channel]
    return channels

# Initialize directories and logging
setup_directories()
log_file_path = setup_logging()

# Initialized channels list
channels = get_channels()

# Process channel exports
for channel in channels:
    product_dir = os.path.join(OUTPUT_DIR, channel)
    os.makedirs(product_dir, exist_ok=True)
    options_dict = {
            "outputDir": product_dir,
            "logLevel": "error",
            "orgLimit": "2"
    }
    options = ' '.join([f"--{opt}='{val}'" for opt, val in options_dict.items()])
    command = f"inter-server-sync export --channels='{channel}' {options}"
    command_args = shlex.split(command)
    with open(log_file_path, "a") as log_file:
        subprocess.run(command_args, stdout=log_file, stderr=subprocess.STDOUT)
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        completion_message = f"{current_time} Export for channel {channel} completed.\n"
        log_file.write(completion_message)

# Change ownership of the base directory recursively
subprocess.run(['chown', '-R', f'{RSYNC_USER}.{RSYNC_GROUP}', BASE_DIR], check=True)
