#!/usr/bin/env python3
#
# CVEReport
#
# (c) 2019 SUSE Linux GmbH, Germany.
# GNU Public License. No warranty. No support
# For question/suggestions/bugs mail: michael.brookhuis@suse.com
#
# Version: 2019-02-12
#
# Created by: SUSE Michael Brookhuis
#
# This script will generate an comma-delimited file with system effected.
#
# Releases:
# 2019-02-12 M.Brookhuis - initial release.
#
#
#
#
"""
CVE report.
"""

import os
import argparse
from argparse import RawTextHelpFormatter
import datetime
import smtools

__smt = None


def _create_cve(data, path, header):
    """
    Create CVE data.
    """
    with open(path, "w") as fhcve:
        if not data:
            fhcve.write("NO CVE\n")  # TODO: Should it be a broken data inside after all?
        else:
            fhcve.write("{}\n".format(header))
            for row in data:
                fhcve.write("{}\n".format(";".join(row)))


def create_file_cve(cve_data, fn):
    """
    Create CVE data.
    """
    _create_cve(data=cve_data, path=fn,
                header="System Name;CVE;Patch-Name;Patch available,channel containing patch;Packages included")


def create_file_cve_reverse(cve_data, fn):
    """
    Create (reverse?) CVE data.
    """
    _create_cve(data=cve_data, path=fn, header="System Name;CVE")


def logfile_present(path):
    """
    Check type for the existing file
    """
    if not os.path.isfile(path):
        raise argparse.ArgumentTypeError("Not a valid file: '{0}'.".format(path))
    return path


def get_cve_content(args):
    """
    Get CVE content.
    """
    smt.log_info("")
    smt.log_info("Start {}".format(datetime.datetime.utcnow()))
    smt.log_info("")
    smt.log_info("Given list of CVEs: {}".format(args.cve))
    smt.log_info("")
    smt.suman_login()
    cve_data = []
    for i in args.cve.split(','):
        cve_data.append(i)
    return cve_data


# noinspection PyPep8
def get_cve_data(args):
    """
    Get CVE data.
    """
    cve_data_collected = []
    for cve in get_cve_content(args):
        if not args.reverse:
            # noinspection PyPep8,PyBroadException
            try:
                cve_list = smt.client.audit.listSystemsByPatchStatus(smt.session, cve, ["AFFECTED_PATCH_INAPPLICABLE",
                                                                                        "AFFECTED_PATCH_APPLICABLE"])
            except:
                cve_list = []
            if not cve_list:
                smt.log_warning("Given CVE {} does not exist.".format(cve))
                break
            else:
                smt.log_info("Processing CVE {}.".format(cve))
            for cve_system in cve_list:
                cve_data = []
                # noinspection PyBroadException
                try:
                    cve_data.append(smt.client.system.getName(smt.session, cve_system.get("system_id")).get("name"))
                except:
                    smt.log_error('unable to get hostname for system with ID {}.'.format(cve_system.get("system_id")))
                    break
                cve_data.append(cve)
                adv_list = ""
                pack_list = ""
                for adv in cve_system.get('errata_advisories'):
                    if adv_list:
                        adv_list = adv_list + ", " + adv
                    else:
                        adv_list = adv
                    cve_packages = None
                    # noinspection PyPep8,PyBroadException
                    try:
                        cve_packages = smt.client.errata.listPackages(smt.session, adv)
                    except:
                        print("unable to find packages")
                    for package in cve_packages:
                        pack = package.get('name') + "-" + package.get('version') + "-" + package.get(
                            'release') + "-" + package.get('arch_label')
                        if pack_list:
                            pack_list = pack_list + ", " + pack
                        else:
                            pack_list = pack
                cve_data.append(adv_list)
                cve_data.append(cve_system.get('patch_status'))
                chan_list = ""
                for chan in cve_system.get("channel_labels"):
                    if chan_list:
                        chan_list = chan_list + ", " + chan
                    else:
                        chan_list = chan
                cve_data.append(chan_list)
                cve_data.append(pack_list)
                cve_data_collected.append(cve_data)
            smt.log_info("Completed.")
        else:
            # noinspection PyPep8,PyBroadException
            try:
                cve_list = smt.client.audit.listSystemsByPatchStatus(smt.session, cve, ["NOT_AFFECTED", "PATCHED"])
            except:
                cve_list = []
            if not cve_list:
                smt.log_warning("Given CVE {} does not exist.".format(cve))
                break
            else:
                smt.log_info("Processing CVE {}.".format(cve))
            for cve_system in cve_list:
                cve_data = []
                # noinspection PyPep8,PyBroadException
                try:
                    cve_data.append(smt.client.system.getName(smt.session, cve_system.get("system_id")).get("name"))
                except:
                    smt.log_error("unable to get hostname for system with ID %{}".format(cve_system.get("system_id")))
                    break
                cve_data.append(cve)
                cve_data_collected.append(cve_data)
            smt.log_info("Completed.")
    return cve_data_collected


def main():
    """
    Main function.
    """
    global smt
    smt = smtools.SMTools("cve_report")
    parser = argparse.ArgumentParser(formatter_class=RawTextHelpFormatter, description="CVE report tool")
    parser.add_argument("-c", "--cve", help="list of CVEs to be checked, comma delimeted, no spaces", required=True)
    parser.add_argument("-r", "--reverse", action="store_true", default=0,
                        help="list systems that have the CVE installed")
    parser.add_argument("-f", "--filename",
                        help="filename the data should be writen in. If no path is given it will be stored in directory where the script has been started.",
                        required=True)
                        #, type=logfile_present)
    parser.add_argument('--version', action='version', version='%(prog)s 0.0.1, October 20, 2017')
    args = parser.parse_args()
    if args.filename:
        cve_data = get_cve_data(args)
        if not args.reverse:
            create_file_cve(cve_data, args.filename)
        else:
            create_file_cve_reverse(cve_data, args.filename)
        smt.log_info("Result can be found in file: {}".format(args.filename))
        smt.suman_logout()
        smt.close_program()
    else:
        parser.print_help()


if __name__ == "__main__":
    SystemExit(main())
