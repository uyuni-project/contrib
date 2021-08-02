#!/usr/bin/env python3
#
# SystemUpdate
#
# (c) 2018 SUSE Linux GmbH, Germany.
# GNU Public License. No warranty. No Support
#
# Version: 2020-06-29
#
# Created by: SUSE Michael Brookhuis
#
# This script will perform the following actions:
# - will check spmig and see if for the given system a SPMigration can be done. 
# - if not SPMigration can be performed, the system will be updated.
#
# Releases:
# 2019-04-29 M.Brookhuis - Initial release
# 2020-01-15 M.Brookhuis - Added update scripts
# 2020-01-16 M.Brookhuis - Bug fix: systems with capitals are never found.
# 2020-06-29 M.Brookhuis - Version 2.
#                        - changed logging
#                        - moved api calls to smtools.py
#
#

"""
This script will perform a complete system maintenance
"""

import argparse
import datetime
import os
import xmlrpc.client
import subprocess
import smtools
import time

__smt = None


def do_update_minion(updateble_patches):
    """
    schedule action chain with updates for errata
    """
    system_entitlement = smt.system_getdetails().get('base_entitlement')
    if not "salt" in system_entitlement:
        return
    patches = []
    for patch in updateble_patches:
        if "salt" in patch.get('advisory_synopsis').lower():
            patches.append(patch.get('id'))
    if not patches:
        smt.log_info('No update for salt-minion"')
        return
    smt.system_scheduleapplyerrate(patches, datetime.datetime.now(), "SALT minion update", "minor")
    smt.system_schedulepackagerefresh(datetime.datetime.now())
    return


def do_update_zypper(updateble_patches):
    """
    schedule action chain with updates for errata
    """
    patches = []
    for patch in updateble_patches:
        if "zlib" in patch.get('advisory_synopsis').lower() or "zypp" in patch.get('advisory_synopsis').lower():
            patches.append(patch.get('id'))
    if not patches:
        smt.log_info('No update for zypper"')
        return
    smt.system_scheduleapplyerrate(patches, datetime.datetime.now(), "zypper update", "minor")
    smt.system_schedulepackagerefresh(datetime.datetime.now())
    return


def do_upgrade(no_reboot, force_reboot):
    """
    do upgrade of packages
    """
    updateble_patches = smt.system_getrelevanterrata()
    if updateble_patches:
        do_update_minion(updateble_patches)
        do_update_zypper(updateble_patches)
    updateble_patches = smt.system_getrelevanterrata()
    if updateble_patches:
        patches = []
        patchnames = []
        for patch in updateble_patches:
            patches.append(patch.get('id'))
            patchnames.append(patch.get('advisory_name'))
        smt.log_debug("The following patches are planned:")
        smt.log_debug(patchnames)
        smt.system_scheduleapplyerrate(patches, datetime.datetime.now(), "Errata update")
        smt.system_schedulepackagerefresh(datetime.datetime.now())
        reboot_needed_errata = True
    else:
        smt.log_info('Errata update not needed. Checking for package update')
        if force_reboot:
            reboot_needed_errata = True
        else:
            reboot_needed_errata = False
    rpms = []
    rpmnames = []
    for rpm in smt.system_listlatestupgradablepackages():
        rpms.append(rpm.get('to_package_id'))
        rpmnames.append(rpm.get('name'))
    if rpms:
        smt.log_debug("The following packages are planned:")
        smt.log_debug(rpmnames)
        smt.system_schedulepackageinstall(rpms, datetime.datetime.now(), "Packages update")
        smt.system_schedulepackagerefresh(datetime.datetime.now())
        reboot_needed_package = True
        reboot_needed_errata = True
    else:
        smt.log_info("Package update not needed.")
        if reboot_needed_errata:
            reboot_needed_package = True
        else:
            reboot_needed_package = False
    if reboot_needed_errata:
        smt.log_debug("Reboot needed for Errata")
    else:
        smt.log_debug("No reboot needed for Errate")
    if reboot_needed_package:
        smt.log_debug("Reboot needed for updated packages")
    else:
        smt.log_debug("No reboot needed for updated packages")
    if no_reboot:
        smt.log_debug("Option no_reboot given")
    if force_reboot:
        smt.log_debug("Option force_reboot given")
    if not no_reboot and reboot_needed_package and reboot_needed_errata:
        smt.system_schedulereboot(datetime.datetime.now())
    smt.system_schedulehardwarerefresh(datetime.datetime.now(), True)
    return


def do_spmigrate(new_basechannel, no_reboot):
    """
    Perform a sp migration for the given server
    """
    checked_new_child_channels = []
    old_basechannel = smt.system_getsubscribedbasechannel()
    (migration_available, migration_targets) = check_spmigration_available()
    if not migration_available:
        smt.log_error("For the system {} no higher SupportPack is available. Please check in SUSE Manager GUI!!".format(smt.hostname))
    sp_old = "sp" + str(old_basechannel.get('label').split("sp")[1][:1])
    sp_new = "sp" + str(new_basechannel.split("sp")[1][:1])
    smt.log_debug("sp_old: {}".format(sp_old))
    smt.log_debug("sp_new: {}".format(sp_new))
    smt.log_debug("current child channels:".format(smt.system_listsubscribedchildchannels()))
    if not smt.channel_software_getdetails(new_basechannel):
        smt.log_info("There is a newer SP available, but that has not been setup for the stage the server is in")
        return
    new_child_channels = [c.get('label').replace(sp_old, sp_new) for c in smt.system_listsubscribedchildchannels()]
    if smtools.CONFIGSM['maintenance']['sp_migration_project']:
        temp_child_channels = []
        for child_channel in new_child_channels:
            for project, new_pr in smtools.CONFIGSM['maintenance']['sp_migration_project'].items():
                if project in child_channel:
                    temp_child_channels.append(child_channel.replace(project, new_pr))
                elif new_pr in child_channel:
                    temp_child_channels.append(child_channel)
        new_child_channels = temp_child_channels
    all_child_channels = [c.get('label') for c in smt.channel_software_listchildren(new_basechannel)]
    for channel in new_child_channels:
        if check_channel(channel, all_child_channels):
            checked_new_child_channels.append(channel)
    do_upgrade(False, False)
    time.sleep(60)
    spident = None
    for migration_target in migration_targets:
        if sp_new.upper() in migration_target['friendly']:
            spident = migration_target['ident']
            break
    result_spmig = False
    if spident:
        if smt.system_schedulespmigration(spident, new_basechannel, checked_new_child_channels, True, datetime.datetime.now(), "SupportPack Migration dry run"):
            time.sleep(20)
            result_spmig = smt.system_schedulespmigration(spident, new_basechannel, checked_new_child_channels, False, datetime.datetime.now(), "SupportPack Migration")
        if result_spmig and not no_reboot:
            smt.log_info("Support Pack migration completed successful, rebooting server {}".format(smt.hostname))
            smt.system_schedulereboot(datetime.datetime.now())
        elif result_spmig and no_reboot:
            smt.log_info("Support Pack migration completed successful, but server {} will not be rebooted. Please reboot manually ASAP.".format(smt.hostname))
        smt.system_schedulepackagerefresh(datetime.datetime.now())
        smt.system_schedulehardwarerefresh(datetime.datetime.now())
    else:
        smt.log_error("SP Migration failed. No SP update available")


def check_channel(channel, channel_all):
    """
    Check if the channel exists.
    """
    for chan in channel_all:
        if channel in chan:
            return True
    return False


def check_spmigration_available():
    """
    Check if there is a SP migration is available
    """
    migration_targets = smt.system_listmigrationtargets()
    if migration_targets:
        return True, migration_targets
    else:
        return False, migration_targets

def remove_ltss():
    child_channels = smt.system_listsubscribedchildchannels()
    new_child_channels = []
    for child_channel in child_channels:
        if "ltss" in child_channel.get('label'):
            continue
        else:
            new_child_channels.append(child_channel.get('label'))
    smt.system_schedulechangechannels(smt.system_getsubscribedbasechannel().get('label'), new_child_channels, datetime.datetime.now())
    installed_packages = smt.system_listinstalledpackages()
    remove_packages = []
    for package in installed_packages:
        if 'ltss' in package.get('name'):
            remove_packages.append(package.get('name'))
    script = "#!/bin/bash\nzypper -n rm "
    if remove_packages:
        for x in remove_packages:
            script += "{} ".format(x)
        smt.system_schedulescriptrun(script, 60, datetime.datetime.now())
        smt.system_schedulepackagerefresh(datetime.datetime.now())
    return


def check_for_sp_migration():
    """
    Check if a sp migration is released for this server
    """
    current_version = None
    current_bc = smt.system_getsubscribedbasechannel().get('label')
    if "sle" not in current_bc:
        smt.log_info("System is not running SLE. SP Migration not possible")
        return False, ""
    if "sp" not in current_bc:
        current_sp = "sp0"
    else:
        current_sp = "sp" + str(current_bc.split("sp")[1].split("-")[0])
    all_bc = smt.get_labels_all_basechannels()
    if smtools.CONFIGSM['maintenance']['sp_migration_project']:
        for project, new_pr in smtools.CONFIGSM['maintenance']['sp_migration_project'].items():
            if server_is_exception(new_pr):
                return False, ""
            project_environments = smt.contentmanagement_listprojectenvironment(project, True)
            if project_environments:
                for env in smt.contentmanagement_listprojectenvironment(project, True):
                    calc_current_bc = project + "-" + env['label']
                    if calc_current_bc in current_bc:
                        part_new_bc = calc_current_bc.replace(project, new_pr)
                        new_base_channel = None
                        for bc in all_bc:
                            if part_new_bc in bc:
                                new_base_channel = bc
                                remove_ltss()
                                return True, new_base_channel
                        if not new_base_channel:
                            smt.log_info("Given SP Migration path is not available. There are no channels available.")
                            return False, ""
    if smtools.CONFIGSM['maintenance']['sp_migration']:
        #if "11-" in current_bc:
        #    current_version = "sles11-"
        #elif "12-" in current_bc:
        #    current_version = "sles12-"
        #elif "15-" in current_bc:
        #    current_version = "sles15-"
        #current_version += current_sp
        for key, value in smtools.CONFIGSM['maintenance']['sp_migration'].items():
            if key == current_bc and not server_is_exception(value):
                return True, value
    return False, ""


def server_is_exception(new_channel):
    """
    Check if server is an exception
    """
    if smtools.CONFIGSM['maintenance']['exception_sp']:
        for key, value in smtools.CONFIGSM['maintenance']['exception_sp'].items():
            if key == new_channel:
                for server_exception in value:
                    if smt.hostname == server_exception:
                        return True
    return False


def system_is_inactive():
    """
    Check if the system is not inactive for at least 1 day
    """
    for system in smt.system_listinactivesystems():
        if smt.systemid == system.get('id'):
            return True
    return False


def server_is_exception_update():
    """
    Check if server is an exception for updating
    """
    if smtools.CONFIGSM['maintenance']['exclude_for_patch']:
        for server_exl in smtools.CONFIGSM['maintenance']['exclude_for_patch']:
            if server_exl == smt.hostname:
                return True
    return False


def read_update_script(phase, filename, script, list_channel):
    if not os.path.exists(smtools.CONFIGSM['dirs']['update_script_dir'] + "/" + filename):
        smt.minor_error("There is no update script \'{}\' available for server.".format(filename))
        return script, list_channel, 60
    else:
        with open(smtools.CONFIGSM['dirs']['update_script_dir'] + "/" + filename) as uc_cfg:
            update_script = smtools.load_yaml(uc_cfg)
    try:
        commands = update_script[phase]['commands']
        for com in commands:
            script += com.rstrip()
            script += "\n"
    except Exception as e:
        pass
    try:
        states = update_script[phase]['state']
        for state in states:
            if smt.configchannel_channelexists(state) == 1:
                list_channel.append(state)
            else:
                smt.minor_error("The state configchannel {} doesn't exist".format(state))
    except Exception as e:
        pass
    return script, list_channel, update_script[phase]['timeout']


def do_update_script(phase):
    """
    execute script before and after maintenance
    """
    script = ""
    list_channel = []
    (script, list_channel, timeout) = read_update_script(phase, "general", script, list_channel)
    (script, list_channel, timeout) = read_update_script(phase, smt.hostname, script, list_channel)
    if script:
        smt.log_info("Execute {} update scripts".format(phase))
        smt.system_schedulescriptrun("#!/bin/bash\n" + script, timeout, xmlrpc.client.DateTime(datetime.datetime.now()))
    else:
        smt.log_info("There is no {} update script available for server.".format(phase))
    if list_channel:
        list_systems = [smt.systemid]
        smt.system_config_addchannels(list_systems, list_channel)
        smt.log_info("Performing high state for {} state channels".format(phase))
        smt.system_scheduleapplyhighstate(xmlrpc.client.DateTime(datetime.datetime.now()))
        smt.system_config_removechannels(list_systems, list_channel)
        return True
    else:
        smt.log_info("There are no {} update state configuration channels available for server".format(phase))
        return False


def update_server(args):
    """
    start update process
    """
    if server_is_exception_update():
        smt.fatal_error("Server {} is in list of exceptions and will not be updated.".format(args.server))
    if system_is_inactive():
        smt.fatal_error("Server {} is inactive for at least a day. Please check. System will not be updated.".format(args.server))
    highstate_done = False
    if args.updatescript:
        highstate_done = do_update_script("begin")
    if args.applyconfig and not highstate_done:
        if smt.system_getdetails().get('base_entitlement') == "salt_entitled":
            smt.system_scheduleapplyhighstate(xmlrpc.client.DateTime(datetime.datetime.now()))
    (do_spm, new_basechannel) = check_for_sp_migration()
    if do_spm:
        smt.log_info("Server {} will get a SupportPack Migration to {} ".format(args.server, new_basechannel))
        do_spmigrate(new_basechannel, args.noreboot)
    else:
        smt.log_info("Server {} will be upgraded with latest available patches".format(args.server))
        do_upgrade(args.noreboot, args.forcereboot)
    highstate_done = False
    if args.updatescript:
        highstate_done = do_update_script("end")
    if args.applyconfig and not highstate_done:
        if smt.system_getdetails().get('base_entitlement') == "salt_entitled":
            smt.system_scheduleapplyhighstate(xmlrpc.client.DateTime(datetime.datetime.now()))
    if args.post_script:
        smt.log_info("Executing script {}".format(args.post_script))
        if os.path.isfile(args.post_script.split(" ")[0]):
            if "/" in args.post_script:
                script = args.post_script.split(" ")[0]
            else:
                script = "./{}".format(args.post_script).split(" ")[0]
            if " " in args.post_script:
                param = args.post_script.lstrip(script)[1:]
                run_script = subprocess.Popen([script, param])
            else:
                run_script = subprocess.Popen(script)
            smt.log_info("Script executed with pid = {}".format(run_script.pid))
        else:
            smt.log_error("The given script does not exist")


def main():
    """
    Main function
    """
    try:
        global smt
        parser = argparse.ArgumentParser(description="Update the give system.")
        parser.add_argument('-s', '--server', help='name of the server to receive config update. Required')
        parser.add_argument("-n", "--noreboot", action="store_true", default=0,
                            help="Do not reboot server after patching or supportpack upgrade.")
        parser.add_argument("-f", "--forcereboot", action="store_true", default=0,
                            help="Force a reboot server after patching or supportpack upgrade.")
        parser.add_argument("-c", '--applyconfig', action="store_true", default=0,
                            help="Apply configuration after and before patching")
        parser.add_argument("-u", "--updatescript", action="store_true", default=0,
                            help="Execute the server specific _start and _end scripts")
        parser.add_argument("-p", "--post_script", help="Execute given script on the SUSE Manger Server when system_update has finished")
        parser.add_argument('--version', action='version', version='%(prog)s 2.0.0, June 29, 2020')
        args = parser.parse_args()
        if not args.server:
            smt = smtools.SMTools("system_update")
            smt.log_error("The option --server is mandatory. Exiting script")
            smt.exit_program(1)
        else:
            smt = smtools.SMTools("system_update", args.server, True)
        # login to suse manager
        smt.log_info("Start")
        smt.log_debug("The following arguments are set: ")
        smt.log_debug(args)
        smt.suman_login()
        smt.set_hostname(args.server)
        update_server(args)
        smt.close_program()
    except Exception as err:
        smt.log_debug("general error:")
        smt.log_debug(err)
        raise

if __name__ == "__main__":
    SystemExit(main())
