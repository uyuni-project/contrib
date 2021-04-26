#!/bin/bash
# Add missing components to the configsm.yaml

grep "loglevel" configsm.yaml 2>&1 /dev/null
rc=$?
if [ $rc -ne 0 ]; then
cat <<EOT >> configsm.yaml
loglevel:
   # LOGLEVELS:
   # DEBUG: info warning error debug
   # INFO: info warning error
   # WARNING: warning error
   # ERROR: error
   screen: INFO
   file: DEBUG

EOT
fi

grep "error_handling" configsm.yaml 2>&1 /dev/null
rc=$?
if [ $rc -ne 0 ]; then
cat <<EOT >> configsm.yaml
error_handling:
  # fatal: report error, exit script
  # error: report error, continue
  # warning: report warning, continue
   script: fatal
   update: error
   spmig: fatal
   configupdate: error
   reboot: fatal
   timeout_passed: error

EOT
fi

