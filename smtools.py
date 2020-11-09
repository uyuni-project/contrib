#!/usr/bin/env python3
#
# Script: smtools.py
#
# (c) 2013 SUSE Linux GmbH, Germany.
# GNU Public License. No warranty. No Support (only from SUSE Consulting)
#
# Version: 2020-03-21
#
# Created by: SUSE Michael Brookhuis,
#
# Description: This script contains standard function that can be used in several other scripts
#
# Releases:
# 2017-10-14 M.Brookhuis - initial release.
# 2018-11-15 M.Brookhuis - Moved to python3.
#                        - Moved config to YAML
# 2020-03-21 M.Brookhuis - RC 1 if there has been an error
#
# coding: utf-8

"""
This library contains functions used in other modules
"""

from email.mime.text import MIMEText
import xmlrpc.client
import logging
import os
import sys
import datetime
import smtplib
import socket
import yaml
import time


def load_yaml(stream):
    """
    Load YAML data.
    """
    loader = yaml.Loader(stream)
    try:
        return loader.get_single_data()
    finally:
        loader.dispose()


if not os.path.isfile(os.path.dirname(__file__) + "/configsm.yaml"):
    print("ERROR: configsm.yaml doesn't exist. Please create file")
    sys.exit(1)
else:
    with open(os.path.dirname(__file__) + '/configsm.yaml') as h_cfg:
        CONFIGSM = load_yaml(h_cfg)


class SMTools:
    """
    Class to define needed tools.
    """
    error_text = ""
    error_found = False
    hostname = ""
    client = ""
    session = ""
    sid = ""
    program = "smtools"
    systemid = 0

    def __init__(self, program, hostname="", hostbased=False):
        """
        Constructor
        LOGLEVELS:
        DEBUG: info warning error debug
        INFO: info warning error
        WARNING: warning error
        ERROR: error
        """
        self.hostname = hostname
        self.hostbased = hostbased
        self.program = program
        log_dir = CONFIGSM['dirs']['log_dir']
        if self.hostbased:
            log_dir += "/" + self.program
            if not os.path.exists(log_dir):
                os.makedirs(log_dir)
            log_name = log_dir + "/" + self.hostname + ".log"
        else:
            if not os.path.exists(CONFIGSM['dirs']['log_dir']):
                os.makedirs(CONFIGSM['dirs']['log_dir'])
            log_name = os.path.join(log_dir, self.program + ".log")

        formatter = logging.Formatter('%(asctime)s |  {} | %(levelname)s | %(message)s'.format(self.hostname),
                                      '%d-%m-%Y %H:%M:%S')

        fh = logging.FileHandler(log_name, 'a')
        fh.setLevel(CONFIGSM['loglevel']['file'].upper())
        fh.setFormatter(formatter)

        console = logging.StreamHandler()
        console.setLevel(CONFIGSM['loglevel']['screen'].upper())
        console.setFormatter(formatter)

        if self.hostbased:
            self.log = logging.getLogger(self.hostname)
            self.log.setLevel(logging.DEBUG)
            self.log.addHandler(console)
            self.log.addHandler(fh)
        else:
            self.log = logging.getLogger('')
            self.log.setLevel(logging.DEBUG)
            self.log.addHandler(console)
            self.log.addHandler(fh)

    def minor_error(self, errtxt):
        """
        Print minor error.
        """
        self.error_text += errtxt
        self.error_text += "\n"
        self.error_found = True
        self.log_error(errtxt)

    def fatal_error(self, errtxt, return_code=1):
        """
        log fatal error and exit program
        """
        self.error_text += errtxt
        self.error_text += "\n"
        self.error_found = True
        self.log_error("{}".format(errtxt))
        self.close_program(return_code)

    def log_info(self, errtxt):
        """
        Log info text
        """
        self.log.info("{}".format(errtxt))

    def log_error(self, errtxt):
        """
        Log error text
        """
        self.log.error("{}".format(errtxt))

    def log_warning(self, errtxt):
        """
        Log error text
        """
        self.log.warning("{}".format(errtxt))

    def log_debug(self, errtxt):
        """
        Log debug text
        :param errtxt :
        :return:
        """
        self.log.debug("{}".format(errtxt))

    def send_mail(self):
        """
        Send Mail.
        """
        script = os.path.basename(sys.argv[0])
        try:
            smtp_connection = smtplib.SMTP(CONFIGSM['smtp']['server'])
        except Exception:
            self.fatal_error("error when sending mail")
        datenow = datetime.datetime.now()
        txt = ("Dear admin,\n\nThe job {} has run today at {}.".format(script, datenow))
        txt += "\n\nUnfortunately there have been some error\n\nPlease see the following list:\n"
        txt += self.error_text
        msg = MIMEText(txt)
        sender = CONFIGSM['smtp']['sender']
        recipients = CONFIGSM['smtp']['receivers']
        msg['Subject'] = ("[{}] on server {} from {} has errors".format(script, self.hostname, datenow))
        msg['From'] = sender
        msg['To'] = ", ".join(recipients)
        try:
            smtp_connection.sendmail(sender, recipients, msg.as_string())
        except Exception:
            self.log.error("sending mail failed")

    def set_hostname(self, host_name, fatal=True):
        """
        Set hostnam for global use.
        """
        self.hostname = host_name
        self.get_server_id(fatal)
        self.log_info("Hostname : {}".format(self.hostname))
        self.log_info("Systemid : {}".format(self.systemid))

    def set_hostname_only(self, host_name):
        """
        Set hostnam for global use.
        """
        self.hostname = host_name

    def close_program(self, return_code=0):
        """Close program and send mail if there is an error"""
        self.suman_logout()
        self.log_info("Finished")
        if self.error_found:
            if CONFIGSM['smtp']['sendmail']:
                self.send_mail()
            if return_code == 0:
                sys.exit(1)
        sys.exit(return_code)

    def exit_program(self, return_code=0):
        """Exit program and send mail if there is an error"""
        self.log_info("Finished")
        if self.error_found:
            if CONFIGSM['smtp']['sendmail']:
                self.send_mail()
            if return_code == 0:
                sys.exit(1)
        sys.exit(return_code)

    def suman_login(self):
        """
        Log in to SUSE Manager Server.
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.connect_ex((CONFIGSM['suman']['server'], 443))
        except:
            self.fatal_error("Unable to login to SUSE Manager server {}".format(CONFIGSM['suman']['server']))

        self.client = xmlrpc.client.Server("https://" + CONFIGSM['suman']['server'] + "/rpc/api")
        try:
            self.session = self.client.auth.login(CONFIGSM['suman']['user'], CONFIGSM['suman']['password'])
        except xmlrpc.client.Fault:
            self.fatal_error("Unable to login to SUSE Manager server {}".format(CONFIGSM['suman']['server']))

    def suman_logout(self):
        """
        Logout from SUSE Manager Server.
        """
        try:
            self.client.auth.logout(self.session)
        except xmlrpc.client.Fault:
            self.log_error("Unable to logout from SUSE Manager {}".format(CONFIGSM['suman']['server']))

    def get_server_id(self, fatal=True):
        """
        Get system Id from host
        """
        all_sid = ""
        try:
            all_sid = self.client.system.getId(self.session, self.hostname)
        except xmlrpc.client.Fault:
            self.fatal_error("Unable to get systemid from system {}. Is this system registered?".format(self.hostname))
        system_id = 0
        for x in all_sid:
            if system_id == 0:
                system_id = x.get('id')
            else:
                if fatal:
                    self.fatal_error("Duplicate system {}. Please fix and run again.".format(self.hostname))
                else:
                    self.log_error("Duplicate system {}. Please fix and run again.".format(self.hostname))
                    self.log_debug(
                        "The following system id have been found for system {}:\n{}".format(self.hostname, all_sid))
        if system_id == 0:
            if fatal:
                self.fatal_error(
                    "Unable to get systemid from system {}. Is this system registered?".format(self.hostname))
            else:
                self.log_error(
                    "Unable to get systemid from system {}. Is this system registered?".format(self.hostname))
        self.systemid = system_id
        return system_id

    def event_status(self, action_id):
        """
        Check status of event
        """
        for result in self.system_listsystemevents():
            if result.get('id') == action_id:
                return result.get('failed_count'), result.get('successful_count'), result.get('result_msg')
        self.fatal_error("System {} is not having a event ID. Aborting!".format(self.hostname))

    def check_progress(self, action_id, timeout, action):
        """
        Check progress of action
        """
        (failed_count, completed_count, result_message) = self.event_status(action_id)
        end_time = datetime.datetime.now() + datetime.timedelta(0, timeout)
        try:
            wait_time = CONFIGSM['maintenance']['wait_between_events_check']
        except:
            wait_time = 15
            self.minor_error("Please set value for maintenance | wait_between_events_check")
        while failed_count == 0 and completed_count == 0:
            if datetime.datetime.now() > end_time:
                message = "Action '{}' run in timeout. Please check server {}.".format(action, self.hostname)
                self.error_handling('timeout_passed', message)
                return 1, 0, message
            (failed_count, completed_count, result_message) = self.event_status(action_id)
            self.log_info("Still Running")
            time.sleep(wait_time)
        return failed_count, completed_count, result_message

    def error_handling(self, err_type, message):
        if CONFIGSM['error_handling'][err_type].lower() == "error":
            self.minor_error(message)
            return
        elif CONFIGSM['error_handling'][err_type].lower() == "warning":
            self.log_warning(message)
            return
        elif CONFIGSM['error_handling'][err_type].lower() == "fatal":
            self.fatal_error(message)
        else:
            message += "\nWrong option given {}. Should be fatal, error or warning. Assuming fatal"
            self.fatal_error(message)

    """
    API call related to system
    """

    def system_getdetails(self):
        try:
            return self.client.system.getDetails(self.session, self.systemid)
        except xmlrpc.client.Fault as err:
            self.log_debug('api-call: system.getDetails')
            self.log_debug('Value passed: ')
            self.log_debug('  system_id:  {}'.format(self.systemid))
            self.log_debug("Error: \n{}".format(err))
            self.fatal_error('Unable to get details for server {}.'.format(self.hostname))

    def system_getrelevanterrata(self):
        try:
            return self.client.system.getRelevantErrata(self.session, self.systemid)
        except xmlrpc.client.Fault as err:
            self.log_debug('api-call: system.getRelevantErrata')
            self.log_debug('Value passed: ')
            self.log_debug('  system_id:  {}'.format(self.systemid))
            self.log_debug("Error: \n{}".format(err))
            self.fatal_error('Unable to get list of errata for server {}.'.format(self.hostname))

    def system_getsubscribedbasechannel(self):
        try:
            return self.client.system.getSubscribedBaseChannel(self.session, self.systemid)
        except xmlrpc.client.Fault as err:
            self.log_debug('api-call: system.getSubscribedBaseChannel')
            self.log_debug('Value passed: ')
            self.log_debug('  system_id:  {}'.format(self.systemid))
            self.log_debug("Error: \n{}".format(err))
            self.fatal_error('Unable to get subscribed basechannel for server {}.'.format(self.hostname))

    def system_listinactivesystems(self):
        try:
            return self.client.system.listInactiveSystems(self.session, 1)
        except xmlrpc.client.Fault as err:
            self.log_debug('api-call: system.listInactiveSystems')
            self.log_debug('Value passed: ')
            self.log_debug('  parameter:      1')
            self.log_debug("Error: \n{}".format(err))
            self.fatal_error(("Unable to receive list of inactive systems. Error: \n{}".format(err)))

    def system_listmigrationtargets(self):
        try:
            return self.client.system.listMigrationTargets(self.session, self.systemid)
        except xmlrpc.client.Fault as err:
            self.log_debug('api-call: system.listMigrationTargets')
            self.log_debug('Value passed: ')
            self.log_debug('  system_id:      {}'.format(self.systemid))
            self.log_debug("Error: \n{}".format(err))
            self.fatal_error(("Unable to receive SP Migration targets. Error: \n{}".format(err)))

    def system_listlatestupgradablepackages(self):
        try:
            return self.client.system.listLatestUpgradablePackages(self.session, self.systemid)
        except xmlrpc.client.Fault as err:
            self.log_debug('api-call: system.listLatestUpgradablePackages')
            self.log_debug('Value passed: ')
            self.log_debug('  system_id:  {}'.format(self.systemid))
            self.log_debug("Error: \n{}".format(err))
            self.fatal_error('Unable to get list of updatable rpms for server {}.'.format(self.hostname))

    def system_listsubscribedchildchannels(self):
        try:
            return self.client.system.listSubscribedChildChannels(self.session, self.systemid)
        except xmlrpc.client.Fault as err:
            self.log_debug('api-call: system.listSubscribedChildChannels')
            self.log_debug('Value passed: ')
            self.log_debug('  system_id:  {}'.format(self.systemid))
            self.log_debug("Error: \n{}".format(err))
            self.fatal_error('Unable to get subscribed child channels for server {}.'.format(self.hostname))

    def system_listsystemevents(self):
        try:
            return self.client.system.listSystemEvents(self.session, self.systemid)
        except xmlrpc.client.Fault as err:
            self.log_debug('api-call: system.listSystemEvents')
            self.log_debug('Value passed: ')
            self.log_debug('  system_id:      {}'.format(self.systemid))
            self.log_debug("Error: \n{}".format(err))
            self.fatal_error('Unable to list events for server {}.'.format(self.hostname))

    def system_obtainreactivationkey(self):
        try:
            return self.client.system.obtainReactivationKey(self.session, self.systemid)
        except xmlrpc.client.Fault as err:
            self.log_debug('api-call: system.obtainReactivationKey')
            self.log_debug('Value passed: ')
            self.log_debug('  system_id:      {}'.format(self.systemid))
            self.log_debug("Error: \n{}".format(err))
            self.fatal_error('Unable to generate reactivation key for {}.'.format(self.hostname))

    def system_scheduleapplyerrate(self, patches, date, action, errlev="fatal"):
        """
        :param patches: list of patch-ids to be applied
        :param date: date when patch should be applied
        :param action: action that is performing errata update
        :param errlev: fatal, warning or minor
        :return: True if errata applied, False when Failed
        """
        self.log_info("Performing {}".format(action))
        try:
            schedule_id = self.client.system.scheduleApplyErrata(self.session, self.systemid, patches, date)[0]
        except xmlrpc.client.Fault as err:
            self.log_debug('api-call: system.scheduleApplyErrata')
            self.log_debug('Value passed: ')
            self.log_debug('  system_id:  {}'.format(self.systemid))
            self.log_debug('  patches:    {}'.format(patches))
            self.log_debug('  date:       {}'.format(date))
            self.log_debug("Error: \n{}".format(err))
            self.fatal_error('Unable to schedule update patches for server{}.'.format(self.hostname))
        timeout = CONFIGSM['suman']['timeout']
        (result_failed, result_completed, result_message) = self.check_progress(schedule_id, timeout, action)
        if result_completed == 1:
            self.log_info("{} completed successful.".format(action))
            return True
        else:
            message = "{} failed!!!!! Server {} will not be updated!\n\nThe error messages is:\n{}".format(action,
                                                                                                           self.hostname,
                                                                                                           result_message)
            if errlev.lower() == "minor":
                self.log_error(message)
            elif errlev.lower() == "warning":
                self.log_warning(message)
            else:
                self.error_handling('update', "Errata failed.")
            return False

    def system_scheduleapplyhighstate(self, date, test=False):
        self.log_info("Performing highstate")
        try:
            schedule_id = self.client.system.scheduleApplyHighstate(self.session, self.systemid, date, test)
        except xmlrpc.client.Fault as err:
            self.log_debug('api-call: system.scheduleApplyHighstate')
            self.log_debug('Value passed: ')
            self.log_debug('  system_id:      {}'.format(self.systemid))
            self.log_debug('  Time:           {}'.format(date))
            self.log_debug('  Test-mode:      {}'.format(test))
            self.log_debug("Error: \n{}".format(err))
            self.fatal_error(("Error to deploy configuration. Error: \n{}".format(err)))
        timeout = CONFIGSM['suman']['timeout']
        (result_failed, result_completed, result_message) = self.check_progress(schedule_id, timeout, "Apply highstate")
        if result_completed == 1:
            self.log_info("Apply highstate completed successful.")
            return True
        else:
            message = "Applyhighstate failed!!!!! Server {} will not be updated!\n\nThe error messages is:\n{}".format(
                self.hostname, result_message)
            self.error_handling('configupdate', message)
            return False

    def system_schedulehardwarerefresh(self, date, nowait=False):
        self.log_info("Running Hardware refresh")
        try:
            schedule_id = self.client.system.scheduleHardwareRefresh(self.session, self.systemid, date)
        except xmlrpc.client.Fault as err:
            self.log_debug('api-call: system.scheduleHardwareRefresh')
            self.log_debug('Value passed: ')
            self.log_debug('  system_id:  {}'.format(self.systemid))
            self.log_debug('  date:  {}'.format(date))
            self.log_debug("Error: \n{}".format(err))
            self.fatal_error('Unable to schedule hardware refresh for server {}.'.format(self.hostname))
        if nowait:
            return
        else:
            timeout = CONFIGSM['suman']['timeout']
            (result_failed, result_completed, result_message) = self.check_progress(schedule_id, timeout,
                                                                                    "Hardware Refresh")
            if result_completed == 1:
                self.log_info("Hardware refresh completed successful.")
            else:
                self.minor_error(
                    "Hardware refresh failed on server {}.\n\nThe error messages is:\n{}".format(self.hostname,
                                                                                                 result_message))

    def system_schedulepackageinstall(self, packages, date, action):
        self.log_info("Running {}".format(action))
        try:
            schedule_id = self.client.system.schedulePackageInstall(self.session, self.systemid, packages, date)
        except xmlrpc.client.Fault as err:
            self.log_debug('api-call: system.schedulePackageInstall')
            self.log_debug('Value passed: ')
            self.log_debug('  system_id:  {}'.format(self.systemid))
            self.log_debug('  packages:   {}'.format(packages))
            self.log_debug('  date:       {}'.format(date))
            self.log_debug("Error: \n{}".format(err))
            self.fatal_error('Unable to schedule update packages for server {}.'.format(self.hostname))
        timeout = CONFIGSM['suman']['timeout']
        (result_failed, result_completed, result_message) = self.check_progress(schedule_id, timeout, action)
        if result_completed == 1:
            self.log_info("{} completed successful.".format(action))
            return True
        else:
            message = "{} failed!!!!! Server {} will not be updated!\n\nThe error messages is:\n{}".format(action,
                                                                                                           self.hostname,
                                                                                                           result_message)
            self.error_handling('reboot', message)
            return False

    def system_schedulepackagerefresh(self, date):
        self.log_info("Running Package refresh")
        try:
            schedule_id = self.client.system.schedulePackageRefresh(self.session, self.systemid, date)
        except xmlrpc.client.Fault as err:
            self.log_debug('api-call: system.schedulePackageRefresh')
            self.log_debug('Value passed: ')
            self.log_debug('  system_id:  {}'.format(self.systemid))
            self.log_debug('  date:  {}'.format(date))
            self.log_debug("Error: \n{}".format(err))
            self.fatal_error('Unable to schedule package refresh for server {}.'.format(self.hostname))
        timeout = CONFIGSM['suman']['timeout']
        (result_failed, result_completed, result_message) = self.check_progress(schedule_id, timeout, "Package Refresh")
        if result_completed == 1:
            self.log_info("Package refresh completed successful.")
        else:
            self.minor_error(
                "Package refresh failed on server {}.\n\nThe error messages is:\n{}".format(self.hostname,
                                                                                            result_message))

    def system_schedulereboot(self, date):
        self.log_info("Rebooting server")
        try:
            schedule_id = self.client.system.scheduleReboot(self.session, self.systemid, date)
        except xmlrpc.client.Fault as err:
            self.log_debug('api-call: system.scheduleReboot')
            self.log_debug('Value passed: ')
            self.log_debug('  system_id:  {}'.format(self.systemid))
            self.log_debug('  date:       {}'.format(date))
            self.log_debug("Error: \n{}".format(err))
            self.fatal_error('Unable to schedule reboot for server {}.'.format(self.hostname))
        timeout = CONFIGSM['suman']['timeout']
        (result_failed, result_completed, result_message) = self.check_progress(schedule_id, timeout,
                                                                                "Hardware Refresh")
        if result_completed == 1:
            self.log_info("Reboot completed successful.")
        else:
            self.error_handling('reboot', "Reboot failed. Please reboot manually ASAP.")

    def system_schedulescriptrun(self, script, timeout, date):
        try:
            schedule_id = self.client.system.scheduleScriptRun(self.session, self.systemid, "root", "root", timeout,
                                                               script, date)
        except xmlrpc.client.Fault as err:
            self.log_debug('api-call: system.scheduleApplyHighstate')
            self.log_debug('Value passed: ')
            self.log_debug('  system_id:      {}'.format(self.systemid))
            self.log_debug('  User:           root')
            self.log_debug('  Group:          root')
            self.log_debug('  Timeout:        {}'.format(timeout))
            self.log_debug('  Script:         {}'.format(script))
            self.log_debug('  Date:           {}'.format(date))
            self.log_debug("Error: \n{}".format(err))
            self.fatal_error(("Error to run a script. Error: \n{}".format(err)))
        action = "Script run"
        timeout = CONFIGSM['suman']['timeout']
        (result_failed, result_completed, result_message) = self.check_progress(schedule_id, timeout, action)
        try:
            scriptresults = self.client.system.getScriptResults(self.session, schedule_id)
        except xmlrpc.client.Fault as err:
            scriptresults = []
        for scriptresult in scriptresults:
            result_message = scriptresult['output']
        if result_completed == 1:
            self.log_info("{} completed successful.".format(action))
            self.log_debug("Result: \n {}".format(result_message))
            return True
        else:
            message = "{} failed on server {}!!!!! \n\nThe error messages is:\n{}".format(action, self.hostname,
                                                                                          result_message)
            self.error_handling('script', message)
            return False

    def system_schedulespmigration(self, spident, basechannel, childchannels, dryrun, date, action):
        self.log_info("{} running for system {}".format(action, self.hostname))
        self.log_info("New basechannel will be: {}".format(basechannel))
        try:
            schedule_id = self.client.system.scheduleSPMigration(self.session, self.systemid, spident, basechannel,
                                                                 childchannels, dryrun, date)
        except xmlrpc.client.Fault as err:
            self.log_debug('api-call: system.scheduleSPMigration')
            self.log_debug('Value passed: ')
            self.log_debug('  system_id:       {}'.format(self.systemid))
            self.log_debug('  migration target {}'.format(spident))
            self.log_debug('  basechannels:    {}'.format(basechannel))
            self.log_debug('  childchannels:   {}'.format(childchannels))
            self.log_debug('  dryrun:          {}'.format(dryrun))
            self.log_debug('  date:            {}'.format(date))
            self.log_debug("Error: \n{}".format(err))
            self.fatal_error('Unable to schedule Support Pack migration for server {}.'.format(self.hostname))

        timeout = CONFIGSM['suman']['timeout'] - 30
        time.sleep(30)
        (result_failed, result_completed, result_message) = self.check_progress(schedule_id, timeout, action)
        if result_completed == 1:
            self.log_info("{} completed successful.".format(action))
            self.log_debug("Result: \n {}".format(result_message))
            return True
        else:
            message = "{} failed!!!!! Server {} will not be updated!\n\nThe error messages is:\n{}".format(action,
                                                                                                           self.hostname,
                                                                                                           result_message)
            self.error_handling('spmig', message)
            return False

    """
    API call related to channel.software
    """

    def channel_software_associaterepo(self, channel, repo):
        try:
            return self.client.channel.software.associateRepo(self.session, channel, repo)
        except xmlrpc.client.Fault as err:
            self.log_debug('api-call: channel.software.associateRepo')
            self.log_debug('Value passed: ')
            self.log_debug('  channel_label:   {}'.format(channel))
            self.log_debug('  repo_label:      {}'.format(repo))
            self.log_debug("Error: \n{}".format(err))
            self.fatal_error("Unable to associate repository {} with channel {}".format(repo, channel))

    def channel_software_clone(self, channel, clone_channel, original_state):
        try:
            return self.client.channel.software.clone(self.session, channel, clone_channel, original_state)
        except xmlrpc.client.Fault as err:
            self.log_debug('api-call: channel.software.clone')
            self.log_debug('Value passed: ')
            self.log_debug('  channel:        {}'.format(channel))
            self.log_debug('  clone_channel:  {}'.format(clone_channel))
            self.log_debug('  original_state: {}'.format(original_state))
            self.log_debug("Error: \n{}".format(err))
            self.fatal_error('Unable to clone channel {}. Please check logs'.format(clone_channel.get('label')))

    def channel_software_create(self, label, name, summary, archlabel, parentlabel):
        try:
            return self.client.channel.software.create(self.session, label, name, summary, archlabel, parentlabel)
        except xmlrpc.client.Fault as err:
            message = ('Unable to create software channel {}.'.format(label))
            self.log_debug('api-call: )channel.software.create')
            self.log_debug("Value passed: ")
            self.log_debug('  label:        {}'.format(label))
            self.log_debug('  channel:      {}'.format(name))
            self.log_debug('  summary:      {}'.format(summary))
            self.log_debug('  archlabel:    {}'.format(archlabel))
            self.log_debug('  parentlabel:  {}'.format(parentlabel))
            self.log_debug("Error: \n{}".format(err))
            self.fatal_error(message)

    def channel_software_createrepo_cert(self, channel, ch_type, ch_url, ch_ca, ch_cert, ch_key, no_fatal=False):
        try:
            return self.client.channel.software.getRepoDetail(self.session, channel, ch_type, ch_url, ch_ca, ch_cert,
                                                              ch_key)
        except xmlrpc.client.Fault as err:
            if no_fatal:
                return False
            else:
                message = ('Unable to create repository {}.'.format(channel))
                self.log_debug('api-call: )channel.software.createRepo')
                self.log_debug("Value passed: channel {}".format(channel))
                self.log_debug('  repository:   {}'.format(channel))
                self.log_debug('  type:         {}'.format(ch_type))
                self.log_debug('  url:          {}'.format(ch_url))
                self.log_debug('  ca:           {}'.format(ch_ca))
                self.log_debug('  certificate:  {}'.format(ch_cert))
                self.log_debug('  key:          {}'.format(ch_key))
                self.log_debug("Error: \n{}".format(err))
                self.fatal_error(message)
        return True

    def channel_software_createrepo(self, channel, ch_type, ch_url, no_fatal=False):
        try:
            return self.client.channel.software.getRepoDetail(self.session, channel, ch_type, ch_url)
        except xmlrpc.client.Fault as err:
            if no_fatal:
                return False
            else:
                message = ('Unable to create repository {}.'.format(channel))
                self.log_debug('api-call: )channel.software.createRepo')
                self.log_debug("Value passed: channel {}".format(channel))
                self.log_debug('  repository:   {}'.format(channel))
                self.log_debug('  type:         {}'.format(ch_type))
                self.log_debug('  url:          {}'.format(ch_url))
                self.log_debug("Error: \n{}".format(err))
                self.fatal_error(message)
        return True

    def channel_software_getdetails(self, channel, no_fatal=False):
        try:
            return self.client.channel.software.getDetails(self.session, channel)
        except xmlrpc.client.Fault as err:
            if no_fatal:
                return []
            else:
                message = ('Unable to get details of channel {}.'.format(channel))
                self.log_debug('api-call: )channel.software.getDetails')
                self.log_debug("Value passed: channel {}".format(channel))
                self.log_debug("Error: \n{}".format(err))
                self.fatal_error(message)

    def channel_software_listchildren(self, channel):
        try:
            return self.client.channel.software.listChildren(self.session, channel)
        except xmlrpc.client.Fault as err:
            self.log_debug('api-call: channel.software.listChildren ')
            self.log_debug('Value passed: channel {}'.format(channel))
            self.log_debug("Error: \n{}".format(err))
            self.fatal_error('Unable to get list child channels for base channel {}. Please check logs'.format(channel))

    def channel_software_mergeerrata(self, parent_channel, clone_channel):
        try:
            return self.client.channel.software.mergeErrata(self.session, parent_channel, clone_channel)
        except xmlrpc.client.Fault as err:
            self.log_debug('api-call: channel.software.mergeErrata')
            self.log_debug('Value passed: ')
            self.log_debug('  parent_channel: {}'.format(parent_channel))
            self.log_debug('  clone_channel:  {}'.format(clone_channel))
            self.log_debug("Error: \n{}".format(err))
            self.minor_error('Unable to get errata for channel {}.'.format(clone_channel))

    def channel_software_mergepackages(self, parent_channel, clone_channel):
        try:
            return self.client.channel.software.mergePackages(self.session, parent_channel, clone_channel)
        except xmlrpc.client.Fault as err:
            self.log_debug('api-call: channel.software.mergePackages')
            self.log_debug('Value passed: ')
            self.log_debug('  parent_channel: {}'.format(parent_channel))
            self.log_debug('  clone_channel:  {}'.format(clone_channel))
            self.log_debug("Error: \n{}".format(err))
            self.minor_error('Unable to get packages for channel {}.'.format(clone_channel))

    def channel_software_getrepodetails(self, channel, no_fatal=False):
        try:
            return self.client.channel.software.getRepoDetail(self.session, channel)
        except xmlrpc.client.Fault as err:
            if no_fatal:
                return []
            else:
                message = ('Unable to get details of channel {}.'.format(channel))
                self.log_debug('api-call: )channel.software.ggetRepoDetail')
                self.log_debug("Value passed: channel {}".format(channel))
                self.log_debug("Error: \n{}".format(err))
                self.fatal_error(message)

    def channel_software_syncrepo(self, repo, schedule):
        try:
            return self.client.channel.software.syncRepo(self.session, repo, schedule)
        except xmlrpc.client.Fault as err:
            self.log_debug('api-call: channel.software.syncRepo')
            self.log_debug('Value passed: ')
            self.log_debug('  channel: {}'.format(repo))
            self.log_debug('  cron:    {}'.format(schedule))
            self.log_debug("Error: \n{}".format(err))
            self.minor_error("Unable to set schedule \'{}\' for repository {}".format(schedule, repo))

    def get_labels_all_basechannels(self):
        all_channels = None
        try:
            all_channels = self.client.channel.listSoftwareChannels(self.session)
        except xmlrpc.client.Fault as err:
            self.log_debug('api-call: )channel.listSoftwareChannels')
            self.log_debug("Error: \n{}".format(err))
            self.fatal_error("Unable to connect SUSE Manager to login to get a list of all software channels")
        abcl = []
        for c in all_channels:
            if not c.get('parent_label'):
                abcl.append(c.get('label'))
        return abcl

    def get_labels_all_channels(self):
        all_channels = None
        try:
            all_channels = self.client.channel.listSoftwareChannels(self.session)
        except xmlrpc.client.Fault as err:
            self.log_debug('api-call: )channel.listSoftwareChannels')
            self.log_debug("Error: \n{}".format(err))
            self.fatal_error("Unable to connect SUSE Manager to login to get a list of all software channels")
        return [c.get('label') for c in all_channels]

    """
    API call related to contentmanagement
    """

    def contentmanagement_attachsource(self, project, channel, fatal=True):
        try:
            return self.client.contentmanagement.attachSource(self.session, project, "software", channel)
        except xmlrpc.client.Fault as err:
            self.log_debug('api-call: contentmanagement.attachSource')
            self.log_debug('Value passed: ')
            self.log_debug('  project: {}'.format(project))
            self.log_debug('  channel: {}'.format(channel))
            self.log_debug("Error: \n{}".format(err))
            message = ("unable to add channel '{}'. Skipping to project {}.".format(channel, project))
            if fatal:
                self.fatal_error(message)
            else:
                self.log_error(message)
                return []

    def contentmanagement_buildproject(self, project, build_message):
        try:
            return self.client.contentmanagement.buildProject(self.session, project, build_message)
        except xmlrpc.client.Fault as err:
            self.log_debug('api-call: contentmanagement.buildProject')
            self.log_debug('Value passed: ')
            self.log_debug('  project: {}'.format(project))
            self.log_debug('  build_message: {}'.format(build_message))
            self.log_debug("Error: \n{}".format(err))
            message = ('Unable to update first environment in the project {}.'.format(project))
            self.fatal_error(message)

    def contentmanagement_createproject(self, project, label, description):
        try:
            return self.client.contentmanagement.createProject(self.session, project, label, description)
        except xmlrpc.client.Fault as err:
            self.log_debug('api-call: contentmanagement.createProject')
            self.log_debug('Value passed: ')
            self.log_debug('  project:     {}'.format(project))
            self.log_debug('  label:       {}'.format(label))
            self.log_debug('  description: {}'.format(description))
            self.log_debug("Error: \n{}".format(err))
            message = ('Unable to create project {}. Please see logs for more details'.format(project))
            self.fatal_error(message)

    def contentmanagement_createenvironment(self, project, pre_label, label, name, description):
        try:
            return self.client.contentmanagement.createEnvironment(self.session, project, pre_label, label, name,
                                                                   description)
        except xmlrpc.client.Fault as err:
            self.log_debug('api-call: contentmanagement.createEnvironment')
            self.log_debug('Value passed: ')
            self.log_debug('  project:     {}'.format(project))
            self.log_debug('  pre-label:   {}'.format(pre_label))
            self.log_debug('  label:       {}'.format(label))
            self.log_debug('  name:        {}'.format(name))
            self.log_debug('  description: {}'.format(description))
            self.log_debug("Error: \n{}".format(err))
            message = ('Unable to create environment {}. Please see logs for more details'.format(label))
            self.fatal_error(message)

    def contentmanagement_detachsource(self, project, channel, fatal=True):
        try:
            return self.client.contentmanagement.detachSource(self.session, project, "software", channel)
        except xmlrpc.client.Fault as err:
            self.log_debug('api-call: contentmanagement.detachSource')
            self.log_debug('Value passed: ')
            self.log_debug('  project: {}'.format(project))
            self.log_debug('  channel: {}'.format(channel))
            self.log_debug("Error: \n{}".format(err))
            message = ("unable to delete channel '{}'. Skipping to project {}.".format(channel, project))
            if fatal:
                self.fatal_error(message)
            else:
                self.log_error(message)
                return []

    def contentmanagement_listprojectenvironment(self, project, no_fatal=False):
        try:
            return self.client.contentmanagement.listProjectEnvironments(self.session, project)
        except xmlrpc.client.Fault as err:
            if no_fatal:
                return []
            else:
                message = ('Unable to get details of given project {}.'.format(project))
                message += ' Does the project exist?'
                self.log_debug('api-call: contentmanagement.listProjectEnvironments')
                self.log_debug('Value passed: ')
                self.log_debug('  project: {}'.format(project))
                self.log_debug("Error: \n{}".format(err))
                self.fatal_error(message)

    def contentmanagement_listprojects(self):
        try:
            return self.client.contentmanagement.listProjects(self.session)
        except xmlrpc.client.Fault as err:
            self.log_debug('api-call: contentmanagement.listProjects')
            self.log_debug("Error: \n{}".format(err))
            message = 'Unable to receive a list of project.'
            self.fatal_error(message)

    def contentmanagement_lookupenvironment(self, project, env):
        try:
            return self.client.contentmanagement.lookupEnvironment(self.session, project, env)
        except xmlrpc.client.Fault as err:
            self.log_debug('api-call: contentmanagement.listProjects')
            self.log_debug('Value passed: ')
            self.log_debug('  project: {}'.format(project))
            self.log_debug('  environment: {}'.format(env))
            self.log_debug("Error: \n{}".format(err))
            message = ('Unable to lookup environment {} for project {}.'.format(env, project))
            self.fatal_error(message)

    def contentmanagement_lookupproject(self, project, fatal=False):
        try:
            return self.client.contentmanagement.lookupProject(self.session, project)
        except xmlrpc.client.Fault as err:
            self.log_debug('api-call: contentmanagement.lookupProject')
            self.log_debug('Value passed: ')
            self.log_debug('  project: {}'.format(project))
            self.log_debug("Error: \n{}".format(err))
            message = ('Unable to lookup project {}.'.format(project))
            if fatal:
                self.fatal_error(message)
            else:
                self.log_error(message)
                return []

    def contentmanagement_promoteproject(self, project, environment):
        try:
            return self.client.contentmanagement.promoteProject(self.session, project, environment)
        except xmlrpc.client.Fault as err:
            self.log_debug('api-call: contentmanagement.buildProject')
            self.log_debug('Value passed: ')
            self.log_debug('  project: {}'.format(project))
            self.log_debug('  environment: {}'.format(environment))
            self.log_debug("Error: \n{}".format(err))
            message = ('Unable to update environment {} in the project {}.'.format(environment, project))
            self.fatal_error(message)

    """
    API call related to configchannel
    """

    def configchannel_channelexists(self, state):
        try:
            return self.client.configchannel.channelExists(self.session, state)
        except xmlrpc.client.Fault as err:
            self.log_debug('api-call: configchannel.channelExists')
            self.log_debug('Value passed: ')
            self.log_debug('  state label: {}'.format(state))
            self.log_debug("Error: \n{}".format(err))
            message = 'Unable to get state channel information'
            self.log_error(message)

    """
    API call related to system.config
    """

    def system_config_addchannels(self, systems, channel, addtotop=False):
        try:
            return self.client.system.config.addChannels(self.session, systems, channel, addtotop)
        except xmlrpc.client.Fault as err:
            self.log_debug('api-call: system.config.addChannels')
            self.log_debug('Value passed: ')
            self.log_debug('  Systems:          {}'.format(systems))
            self.log_debug('  Channel:          {}'.format(channel))
            self.log_debug('  Add to top:       {}'.format(addtotop))
            self.log_debug("Error: \n{}".format(err))
            message = 'Unable to add channels'
            self.minor_error(message)

    def system_config_removechannels(self, systems, channel):
        try:
            return self.client.system.config.removeChannels(self.session, systems, channel)
        except xmlrpc.client.Fault as err:
            self.log_debug('api-call: system.config.removeChannels')
            self.log_debug('Value passed: ')
            self.log_debug('  Systems:          {}'.format(systems))
            self.log_debug('  Channel:          {}'.format(channel))
            self.log_debug("Error: \n{}".format(err))
            message = 'Unable to remove channels'
            self.minor_error(message)

    """
    API call related to systemgroup
    """

    def systemgroup_listsystemminimal(self, group):
        try:
            return self.client.systemgroup.listSystemsMinimal(self.session, group)
        except xmlrpc.client.Fault as err:
            self.log_debug('api-call: systemgroup.listSystemsMinimal')
            self.log_debug('Value passed: ')
            self.log_debug('  Group:          {}'.format(group))
            self.log_debug("Error: \n{}".format(err))
            message = ('Unable to get list of systems assgined to system group {}'.format(group))
            self.fatal_error(message)

    """
    API call related to kickstart.keys
    """

    def kickstart_keys_listallkeys(self):
        try:
            return self.client.kickstart.keys.listAllKeys(self.session)
        except xmlrpc.client.Fault as err:
            self.log_debug('api-call: kickstart.keys.listAllKeys')
            self.log_debug("Error: \n{}".format(err))
            message = 'Unable to get a list of keys.'
            self.fatal_error(message)
