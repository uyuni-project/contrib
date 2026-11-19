# create_software_project.py

A script for managing content lifecycle software projects.

This script provides an interface to create new content lifecycle software projects,
manage their environments, and attach or detach software channels. It is capable of
updating project environments and creating activation keys for software projects. The
main goal is to facilitate automating lifecycle management processes.

Arguments:
* -h, --help --> show this help message and exit
* -p PROJECT, --project PROJECT --> name of the project to be created. Required
* -e ENVIRONMENT, --environment ENV1,ENV2,ENV3 --> Comma delimited list without spaces of the environments to be created. Required
* -b BASECHANNEL, --basechannel BASECHANNEL -->  The base channel on which the project should be based.
* -a ADDCHANNEL, --addchannel CHANNEL1,CHANNEL2,CHANNELn   -->  Comma delimited list without spaces of the channels to be added. Can be used together with --basechannel
* -d DELETECHANNEL, --deletechannel CHANNEL1,CHANNEL2,CHANNELn   -->  Comma delimited list without spaces of the channels to be removed from the project.
* -m DESCRIPTION, --description   -->  DESCRIPTION Description of the project to be created.
* -n, --nobuild    -->   Don't perform a build or promote
* -k, --activationkey    -->   create activationkeys for each environment. Will not work with --no-build
* --version    -->   show program's version number and exit

The script will first check if the project already exists. If it does, only the options --addchannel and --deletechannel will be considered.
If the option --addchannel is not used, all channels present in the basechannel will be attached to the project. 
By default, the environments will be build or promoted. Unless the option --nobuild is used. When this option is used, the option --activationkey will not work.
The option --activationkey will create activation keys for each environment. The same channels will be attached to the activation keys as used in the project. 

An example of the script usage:
> <installation directory>/create_software_project.py -p s157 -e dev,test,prod -b sle-product-sles15-sp7-pool-ppc64le -a custom1,custom2 -d sle15-sp7-installer-updates-ppc64le -m "SLES15 SP7 PPC"
