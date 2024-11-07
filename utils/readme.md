# What is?

Tools that where moved away from the spacewalk-utils-extras package. That package had community support only. For that reason we moved most of tools toa supports scenario (spacewalk-utils) or to this project.

# How to install each tool?

## Install in a third party machine

It's advise to install the tools in a third party to avoid any interference with SUSE Manager server scripts and tools.

To install it copy the tool file into the directory `/usr/local/bin`. Some tools depend on exta packages tha needs to be installed.
The needed extra packages are available in client tools channels.

## Instalation on the server container

Is not advised to installed inside the container image, but it's possible for some of the tools.

To install it users should copy the tool file to inside the container into the directory `/root/bin`.
This will make the tool available inside the container and the files will be persistent.

# Tools


| Tool name                        | Description                                                                                                                                                                                                                    | Extra package                                                               |
|----------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| `delete-old-systems-interactive` | Delete systems that are inactive                                                                                                                                                                                               | --                                                                          |
| `migrate-system-profile`         | <b>Deprecated: use UI and API calls instead</b>.Migrate a system from one organization to another. Also needs to deploy the file `migrateSystemProfile.py` to `/usr/lib/python3.6/site-packages/utils/migrateSystemProfile.py` | `python3-rhnlib` <br/>`uyuni-base-common` <br/> `python3-uyuni-common-libs` |
| `spacewalk-api`                  | <b>Deprecated: use spacecmd instead</b>. Call uyuni API.                                                                                                                                                                       | --                                                                          |


