= OS Image helper tools for Uyuni/SUSE Manager

== osimage-import-export.py

Export and import OS image metadata from one server to another.

This script does not copy actual image files, only dumps metadata, including image pillars if present of one os image entry and then allows to import them to different server.
If pillar is present and data contains URL of source server, this URL is mangled and translated to the target server on import.

== set-os-image-activity.py

Set individual image as active or inactive.

Saltboot understands image flag `inactive`. If this file is set to `True`, then image is not considered for Saltboot deployment. By default it is set as `False`.
