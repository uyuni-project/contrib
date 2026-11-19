# sync_stage.py

A script for build or promote an environment in a content lifecycle software project.

This script will build or promote an environment in a content lifecycle software project from its defined sources. 

Arguments:
* -h, --help --> show this help message and exit
* -c CHANNEL, --channel CHANNEL --> name of the cloned parent channel to be updated
* -b, --backup --> creates a backup of the stage first.
* -w, --wait --> wait until the sync of the previous environment is completed or present.
* -p PROJECT, --project PROJECT --> name of the project to be updated. --environment is also mandatory
* -e ENVIRONMENT, --environment ENVIRONMENT --> the project to be updated. Mandatory with --project
* -m MESSAGE, --message MESSAGE --> Message to be displayed when in description of build
* --version --> show program's version number and exit

The script will build the first environment or promote any following environment. It will check if the previous environment has been built. <br>
With the --wait option, the script will wait until the environment is built or present or when the previous is being built, it will wait until the previous environment is built.

An example of the script usage:
> <installation directory>/sync_stage.py -p s157 -e test -w -m "Build for quarter 4 - 2025"
