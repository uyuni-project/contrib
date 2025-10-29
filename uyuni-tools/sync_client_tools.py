#!/usr/bin/env python3
"""
# Copyright (c) 2025 SUSE LLC, Germany.
# GNU Public License. No warranty. No Support
# For question/suggestions/bugs mail: amehmood@suse.com
#
# Version:2025-10-15
#
# Created by: Abid Mehmood
#
# Using this script user can sync the client tools if they are not already synced for already mirrored products on SUSE Multi-Linux Manager and Uyuni.
#
# 2025-10-15  Abid - initial release.

"""

import xmlrpc.client
import time
import argparse

SUSE_MULTI_LINUX_MANAGER_SERVER = "<your-server>"
USERNAME = "<username>"
PASSWORD = "<password>"



def log(message):
    """Simple logging function."""
    print(f"[INFO] {message}")

def dry_run_log(message):
    """Dry-run logging function."""
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

def find_extensions_of_synced_products(client, key):
    """Get all the extensions of the already synced products"""
    all_extensions = []
    products = client.sync.content.listProducts(key)
    for product in products:
        if product.get('status', '').lower() == 'installed':
            product_name = product.get('friendly_name', 'Unknown Product')
            extensions = product.get('extensions', [])
            if extensions:
                for ext in extensions:
                    all_extensions.append(ext)
            else:
                print(f"No extensions found for {product_name}.")
    return all_extensions

def add_client_tools_channels(client, key, extensions, dry_run):
    """Add all the client tools channels available which aren't synced yet"""
    for ext in extensions:
        if "Client Tools" in ext.get('friendly_name', ''):
            channels = ext.get('channels', [])
            if not channels:
                print("  No channels found.")
                continue
            for ch in channels:
                if ch.get('family') == 'SLE-M-T' and not ch.get('optional', False):
                    if ch.get('status', '').lower() == 'installed':
                        log(f"already synced: {ch.get('label')}")
                        continue
                    label = ch.get('label', 'N/A')
                    family = ch.get('family', 'N/A')
                    if dry_run:
                        dry_run_log(f"Would add channel: {label}")
                    else:
                        log(f"Adding channel: {label}")
                        client.sync.content.addChannel(key, label, '')

def main():
    """Main function to run the entire workflow."""
    parser = argparse.ArgumentParser(description="A script to add client tools channels to SUSE Manager.",
                                    formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--no-dry-run", action="store_true", 
                        help="Perform actual changes instead of a dry run.\n"
                            "The script runs in dry-run mode by default.")
    args = parser.parse_args()
    dry_run = not args.no_dry_run

    if dry_run:
        log("Script is running in DRY-RUN mode. No changes will be made.")
    else:
        log("WARNING: Script is running in LIVE mode. Changes will be applied.")

    client, key = connect_and_login()
    if not client:
        return

    try:
        extensions = find_extensions_of_synced_products(client, key)
        add_client_tools_channels(client, key, extensions, dry_run)
        log("INFO: Channels have been added and will be synced with the next scheduled repository sync. If you want to sync them now, you can schedule the 'Single run schedule' task from the 'mgr-sync-refresh-bunch' family of tasks.")
    
    except Exception as e:
        print(f"[ERROR] An unexpected error occurred: {e}")
    finally:
        if key:
            client.auth.logout(key)
            log("Logged out successfully.")

if __name__ == "__main__":
    main()
