#! /usr/bin/python3

import os
import subprocess
import datetime
from xmlrpc.client import ServerProxy
import ssl
import socket

SUMA_FQDN = socket.getfqdn()
MANAGER_LOGIN = "admin"
MANAGER_PASSWORD = "<change_me>"

MANAGER_URL = "https://" + SUMA_FQDN + "/rpc/api"

context = ssl.create_default_context()
client = ServerProxy(MANAGER_URL, context=context)
key = client.auth.login(MANAGER_LOGIN, MANAGER_PASSWORD)

today = datetime.date.today()
yesterday = today - datetime.timedelta(days=1)
log_file_path = f"/mnt/logs/{today}-daily_export.log"
output_dir = "/mnt/export/updates"

subprocess.run(f"rm -rf {output_dir}/*", shell=True, check=True)

channel_list = client.channel.listVendorChannels(key)

for channel in channel_list:
  build_date, channel_label = client.channel.software.getChannelLastBuildById(key, channel["id"]).split()[0], channel["label"]
  build_date = datetime.datetime.strptime(build_date, "%Y-%m-%d").date()

  if build_date in [today, yesterday]:
    channel_output_dir = os.path.join(output_dir, channel_label)
    os.makedirs(channel_output_dir, exist_ok=True)
    options = f"--outputDir='{channel_output_dir}' --orgLimit=2 --packagesOnlyAfter={yesterday}"
    command = f"inter-server-sync export --channels='{channel_label}' {options}"
    with open(log_file_path, "a") as log_file:
      subprocess.run(command, shell=True, stdout=log_file, stderr=subprocess.STDOUT)
      current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
      completion_message = f"{current_time} Export for channel {channel_label} completed.\n"
      log_file.write(completion_message)
