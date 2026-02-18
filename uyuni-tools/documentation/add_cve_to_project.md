# add_cve_to_project.py

This script is used to add a list of CVEs, advisories or packages to a project the first environment of the project. The addition is both the errata information and the involved packages. 
With the option --update it will add the CVEs to the other environments of the project. When using the option --promote it will promote the other environments of the project.
If no --update or --promote option is used the script will only add the CVEs to the first environment of the project.

Arguments:
* -h, --help → show this help message and exit
* -p PROJECT, --project PROJECT → name of the CLM project where the CVE, patch or package has to be added. Required
* -c CVE, --cve CVE → The CVE Number. This option can be used multiple times.
* -a ADVISORY, --advisory ADVISORY  → Add an advisory. This option can be used multiple times
* -g PACKAGE, --package PACKAGE → Add a package. This option can be used multiple times
* -u --update → Update all other environments of the project. The default is False.
* -r --promote → Promote all other environments of the project. The default is False.
* --version → show program's version number and exit

An example of the script usage:
> /opt/uyuni-tools/add_cve_to_project.py -p s157-sap -u -c CVE-2025-8058 -c CVE-2022-22967 -g cpio-2.13-150400.3.6.1.x86_64
