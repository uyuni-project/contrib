#!/usr/bin/env python3
#
# register_system.py
#
# (c) 2020 SUSE Linux GmbH, Germany.
# GNU Public License. No warranty. No Support
# For question/suggestions/bugs mail: michael.brookhuis@suse.com
#
# Version: 2020-04-01
#
# Created by: SUSE Michael Brookhuis.
#
# Releases:
# 2020-04-01 M.Brookhuis - initial release.
#
"""This program will add the give system to the software-, configurationchannels and systemgroups after migration"""
import sys
import argparse
from argparse import RawTextHelpFormatter
import os
import xmlrpc.client
import smtools
import datetime
import time

__smt = None

def main():
     """
     Main Function
     """
     global smt
     smt = smtools.SMTools("test", "test")
     smt.suman_login()
     smt.log_info("Start")
     
     configchannels = smt.client.configchannel.listGlobals(smt.session)
     #smt.log_info(configchannels)
     configfiles = smt.client.configchannel.listFiles(smt.session, "default")
     #print(configfiles)
     for x in configfiles:
         #fileinfo = smt.client.configchannel.getFileRevisions(smt.session, "default")
         fileinfo = smt.client.configchannel.getFileRevisions(smt.session, "default", x.get('path'))
         #print(fileinfo)
     
     for x in configfiles:
         fileinfo = smt.client.configchannel.lookupFileInfo(smt.session, "default", [x.get('path')])
         print(fileinfo)
         for y in fileinfo:
             print(y)
             print(y.get('contents'))
             if "/init.sls" != y.get('path'):
                  print(fileinfo)
                  print(y.get('contents'))
                  oo = y.get('contents')
                  inhoud = oo + "\nEn deze lijn is toegevoegd"
                  temp = smt.client.configchannel.createOrUpdatePath(smt.session, "default", y.get('path'), False, {'revision': 11, 'contents': inhoud, 'owner': 'root', 'group': 'root', 'permissions': '644', 'macro-start-delimiter': '{|', 'macro-end-delimiter': '|}', 'binary': False})
                  print(temp)



     smt.close_program()


if __name__ == "__main__":
     SystemExit(main())

