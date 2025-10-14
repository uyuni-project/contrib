"""
# (c) 2019 SUSE Linux GmbH, Germany.
# GNU Public License. No warranty. No Support
# For question/suggestions/bugs mail: amehmood@suse.com
#
# Version: 2025-10-14
#
# Created by: Abid Mehmood
#
# Using this cscript you can update your actiavation keys and CLM projects by removing the old client tools and switching to new client tools. 
# This script assumes that new client tools have been already syned in your MLM/Uyuni instance.
#
# Releasmt.session:
# 2017-01-2 Abid - initial release.

"""
import xmlrpc.client
import time
import sys
import argparse
from argparse import RawTextHelpFormatter

# --- Configuration ---
SUSE_MULTI_LINUX_MANAGER_SERVER = "<your-server>"
USERNAME = "<username>"
PASSWORD = "<password>"

def log(message):
    print(f"[INFO] {message}")

def dry_run_log(message):
    print(f"[DRY-RUN] {message}")

def connect_and_login():
    """Connects to the XML-RPC API and returns a session key."""
    try:
        log(f"Connecting to {SUSE_MULTI_LINUX_MANAGER_SERVER}...")
        client = xmlrpc.client.Server(f"http://{SUSE_MULTI_LINUX_MANAGER_SERVER}/rpc/api")
        key = client.auth.login(USERNAME, PASSWORD)
        log("Successfully logged in.")
        return client, key
    except Exception as e:
        print(f"[ERROR] Failed to connect or login: {e}")
        return None, None

def list_and_find_base_channels(client, key):
    """Lists all software channels and returns a list of base channel labels."""
    channels = client.channel.listSoftwareChannels(key)
    base_channels = [ch["label"] for ch in channels if not ch.get("parent_label")]
    return base_channels

def process_clm_project(client, key, project_label, base_channels, dry_run):
    """Processes a single CLM project, updating channels and promoting environments."""
    log(f"\n=== Processing Project: {project_label} ===")

    sources = client.contentmanagement.listProjectSources(key, project_label)
    # It's assumed that old client tools channels contain 'manager-tools' and new ones 'managertools' in their labels
    old_tools = [s['channelLabel'] for s in sources if 'manager-tools' in s.get('channelLabel', '').lower()]
    new_tools = [s['channelLabel'] for s in sources if 'managertools' in s.get('channelLabel', '').lower()]

    if not old_tools and not new_tools:
        log("No old client tools channels to detach or new ones to attach. Skipping project promotion.")
        return

    log(f"Old client tools channels (to be detached): {old_tools}")
    log(f"New client tools channels already present: {new_tools}")

    if old_tools:
        log("\n=== Detaching Old Client Tools Channels ===")
        for old in old_tools:
            if dry_run:
                dry_run_log(f"Would detach old client tools channel: {old}")
            else:
                log(f"Detaching old client tools channel: {old}")
                client.contentmanagement.detachSource(key, project_label, 'software', old)
    else:
        log("No old client tools channels to detach.")

    if not new_tools:
        log("\n=== Attaching New Client Tools Channel ===")
        source_labels = [s.get('channelLabel', '') for s in sources]
        base_channel_label = next((lbl for lbl in source_labels if lbl in base_channels), None)

        if base_channel_label:
            log(f"Base channel determined for project: {base_channel_label}")
            children = client.channel.software.listChildren(key, base_channel_label)
            managertools_labels = [c['label'] for c in children if c.get('channel_family_label') == 'SLE-M-T']

            if managertools_labels:
                for label in managertools_labels:
                    if dry_run:
                        dry_run_log(f"Would attach new client tools: {label}")
                    else:
                        log(f"Attaching new client tools: {label}")
                        client.contentmanagement.attachSource(key, project_label, 'software', label)
            else:
                log("No client tools channels found for the matched base channel. Skipping attachment.")
        else:
            log("Could not determine a base channel for this project. Skipping new tools attachment.")
    else:
        log("New client tools channel already present in project sources. Skipping attachment.")

    log("\n=== Building and Promoting Selected Environments ===")
    all_envs = client.contentmanagement.listProjectEnvironments(key, project_label)
    
    if not all_envs:
        log("No environments found for this project.")
        return

    first_env_label = all_envs[0]['label']
    
    for i, env in enumerate(all_envs):
        env_label = env['label']
        is_first_env = (env_label == first_env_label)

        if is_first_env:
                description = "Build for new client tools channels."
                if dry_run:
                    dry_run_log(f"Would build initial environment {env_label}")
                else:
                    log(f"Building initial environment (label: {env_label})")
                    client.contentmanagement.buildProject(key, project_label, description)
                    if not wait_for_completion(client, key, project_label, env_label):
                        log("Build failed or timed out. Aborting promotion process.")
                        return
        else:
            prev_env_label = env['previousEnvironmentLabel']
            if dry_run:
                dry_run_log(f"Would promote the environment {prev_env_label} to {env_label}")
            else:
                log(f"Promoting the environment {prev_env_label} to {env_label}")
                client.contentmanagement.promoteProject(key, project_label, prev_env_label)
                if not wait_for_completion(client, key, project_label, prev_env_label):
                    log("Promotion failed or timed out. Aborting promotion process.")
                    return
        
        if not dry_run and i < len(all_envs) - 1:
            log("Waiting 30 seconds before next promotion...")
            time.sleep(30)


def wait_for_completion(client, key, project_label, env_label, wait_interval=30):
    """Polls the project environment status until it is 'built' or an error occurs."""
    log(f"Waiting for environment '{env_label}' to complete its operation...")
    while True:
        try:
            current_env = client.contentmanagement.lookupEnvironment(key, project_label, env_label)
            
            if not current_env:
                log(f"Environment '{env_label}' not found, assuming an issue occurred.")
                return False

            status = current_env['status']
            log(f"Current status for '{env_label}': {status}")
            
            if status == "built":
                log(f"Environment '{env_label}' successfully built.")
                return True
            else:
                log(f"Still building environment '{env_label}' with status: {status}.")
                time.sleep(wait_interval)
        except Exception as e:
            print(f"[ERROR] Polling failed: {e}")
            return False

# --- Skeleton Functions for other Components ---

def process_activation_keys(client, key, activation_keys, dry_run):
    """Function to process one or more activation keys."""
    log("\n=== Processing Activation Keys ===")
    
    # We need a list of all channels to dynamically find the 'managertools' channel
    all_channels = client.channel.listSoftwareChannels(key)

    for ak_key in activation_keys:
        log(f"Processing activation key: {ak_key}")
        
        try:
            detail = client.activationkey.getDetails(key, ak_key)
            child_channel_labels = detail.get('child_channel_labels', [])
        except xmlrpc.client.Fault as e:
            log(f"Failed to get details for activation key {ak_key}: {e}. Skipping.")
            continue

        old_tools = [label for label in child_channel_labels if 'manager-tools' in label.lower()]
        
        channels_to_attach = []
        # Find the new 'managertools' channel based on the base channel of the activation key
        base_channel_label = detail.get('base_channel_label')
        
        if base_channel_label:
            # Find children of the base channel
            children = client.channel.software.listChildren(key, base_channel_label)
            # Filter for the new client tools channel
            new_tools = [c['label'] for c in children if c.get('channel_family_label') == 'SLE-M-T']
            
            # Condition: Only proceed if there are old tools to remove and new tools to add.
            if old_tools and new_tools:
                channels_to_attach = new_tools
            elif old_tools and not new_tools:
                 log(f"No new client tools channel found for base channel {base_channel_label}. Skipping update for key {ak_key}.")
                 continue
            else:
                 log(f"No old client tools channels found for key {ak_key}. Skipping update.")
                 continue
        else:
            log(f"Could not determine base channel for key {ak_key}. Skipping update.")
            continue

        if dry_run:
            if old_tools:
                dry_run_log(f"Would remove the old client tools channels {old_tools} from key {ak_key}")
            if channels_to_attach:
                dry_run_log(f"Would add new client tools channels {channels_to_attach} to key {ak_key}")
        else:
            log(f"Updating channels for activation key {ak_key}...")
            if old_tools:
                log(f"Detaching channels: {old_tools}")
                client.activationkey.removeChildChannels(key, ak_key, old_tools)
            if channels_to_attach:
                log(f"Attaching channels: {channels_to_attach}")
                client.activationkey.addChildChannels(key, ak_key, channels_to_attach)

def process_autoinstallation_profiles(client, key, profiles_to_process, dry_run):
    """Skeleton function to process one or more autoinstallation profiles."""
    log("\n=== Not implemented yet ===")

def main():
    parser = argparse.ArgumentParser(formatter_class=RawTextHelpFormatter, description='''
Usage:
    script_name.py -c <component> <label> [--no-dry-run]
    
    Specify the component and the label(s) to process.

    Components:
    - clmprojects: Process CLM projects. Provide 'all' or a project label.
    - activationkeys: Process activation keys. Provide 'all' or a key.
    - autoinstallprofiles: Process autoinstallation profiles. Provide 'all' or a label.
    
    The script runs in dry-run mode by default.

    Examples:
    - Process a single CLM project and all its environments:
      python3 script_name.py -c clmprojects clm2

    - Process all CLM projects:
      python3 script_name.py -c clmprojects all

    - Process a single activation key:
      python3 script_name.py -c activationkeys 1-sles15sp4-x86_64

    - Process all autoinstallation profiles with actual changes:
      python3 script_name.py -c autoinstallprofiles all --no-dry-run
    ''')
    
    parser.add_argument("-c", "--component", choices=['clmprojects', 'activationkeys', 'autoinstallprofiles'], required=True, help="The component to process.")
    parser.add_argument("labels", nargs='+', help="The label(s) of the component to process, or 'all'.")
    parser.add_argument("--no-dry-run", action='store_true', help="Perform actual changes instead of a dry run.")
    
    args = parser.parse_args()

    dry_run = not args.no_dry_run
    labels_to_process = args.labels[0].split(',') if args.labels[0].lower() != 'all' else ['all']

    client, key = connect_and_login()
    if not client:
        sys.exit(1)

    try:
        if args.component == 'clmprojects':
            if 'all' in labels_to_process:
                projects_to_process = [p['label'] for p in client.contentmanagement.listProjects(key)]
            else:
                projects_to_process = labels_to_process
            
            base_channels = list_and_find_base_channels(client, key)
            for project_label in projects_to_process:
                if not any(p['label'] == project_label for p in client.contentmanagement.listProjects(key)):
                    log(f"Project '{project_label}' not found. Skipping.")
                    continue
                process_clm_project(client, key, project_label, base_channels, dry_run)

        elif args.component == 'activationkeys':
            if 'all' in labels_to_process:
                ak_to_process = [k['key'] for k in client.activationkey.listActivationKeys(key)]
            else:
                ak_to_process = labels_to_process
            process_activation_keys(client, key, ak_to_process, dry_run)
            
        elif args.component == 'autoinstallprofiles':
            if 'all' in labels_to_process:
                profiles_to_process = [p['label'] for p in client.autoinstallation.listProfiles(key)]
            else:
                profiles_to_process = labels_to_process
            process_autoinstallation_profiles(client, key, profiles_to_process, dry_run)

    except Exception as e:
        print(f"[ERROR] An unexpected error occurred: {e}")
    finally:
        if key:
            client.auth.logout(key)
            log("Logged out successfully.")

if __name__ == "__main__":
    main()