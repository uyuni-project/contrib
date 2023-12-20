#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2023 SUSE LLC
#
# SPDX-License-Identifier: GPL-2.0-only

"""
Naive emergency tool to update existing initrd from RPM or multiple RPMs.
Primary usecase is a PTF update of existing saltboot initrd

Script backups original initrd and link this backup to the original image.
Once initrd is updates, script automatically updates checksum and size in the image pillar.
"""

from argparse import ArgumentParser
from glob import glob
from hashlib import md5
from pprint import pprint
from shutil import copy2
from os import path, stat, rename, remove
from random import randint
from requests import get, post
from subprocess import call
from tempfile import mkdtemp

OSIMAGEDIR = "/srv/www/os-images/1"
SSLVERIFY = "/srv/www/htdocs/pub/RHN-ORG-TRUSTED-SSL-CERT"

### API
def login(user, password):
  data = {"login": user, "password": password}
  res = post(MANAGER_URL + 'auth/login', json=data, verify=SSLVERIFY)
  if res.status_code != 200 or not res.json()['success']:
    print(f"Failed to login with message: {res.json()['messages']}")
    exit(1)
  return res.cookies

def getQuery(query, queryData=None, fatal=True):
  queryParams = ""
  if queryData:
    queryParams = "?"
    for key, value in queryData.items():
      queryParams += f"{key}={value}&"
  res = get(MANAGER_URL + query + queryParams, cookies=cookies, verify=SSLVERIFY)
  if res.status_code != 200:
    if fatal:
      print(f"GET request {query} failed with error {res}")
      exit(1)
    else:
      return None
  elif not res.json()['success']:
    if fatal:
      print(f"GET request {query} failed with error {res.json()}")
      exit(1)
    else:
      return None
  return res.json()['result']

def postQuery(query, queryData):
  res = post(MANAGER_URL + query, json=queryData, cookies=cookies, verify=SSLVERIFY)
  if res.status_code != 200:
    print(f"POST request {query} failed with error {res}")
    exit(1)
  elif not res.json()['success']:
    print(f"POST request {query} failed with error {res.json()}")
    exit(1)
  return res.json()['result']
### API

def getImageDetails(name, version, revision):
  images = getQuery('image/listImages')
  images = list(filter(lambda image: (image['name'] == name and image['version'] == version and image['revision'] == int(revision)), images))
  if len(images) == 0:
    print(f"Unable to find image with name {name}, version {version} and revision {revision}")
    exit(2)
  else:
    image_data = images[0]

  pillar_data = getQuery('image/getPillar', {'imageId': image_data['id']}, False)

  files_data = getQuery('image/getDetails', {'imageId': image_data['id']}).get('files', {})
  initrd = None
  backup_initrd = []
  for f in files_data:
    if f['type'] == 'initrd':
      initrd = path.join(OSIMAGEDIR, f['file'])
    elif f['type'] == 'initrd_backup':
      backup_initrd.append(path.join(OSIMAGEDIR, f['file']))
  if initrd is None:
    print("No 'initrd' file type found!")
    exit(3)

  return (image_data['id'], initrd, backup_initrd, pillar_data)

def sanityCheck(initrd_path, rpm_path):
  if not path.isfile(initrd_path):
    print(f"Expected initrd file '{initrd_path}' does not exists")
    exit(4)
  
  if not (path.isfile(rpm_path) or path.isdir(rpm_path)):
    print(f"Provided rpm path does not exists")
    exit(4)

def backupInitrd(initrd_path, imageId):
  r_suffix = str(randint(0, 9999))
  backup_name = f"{initrd_path}.{r_suffix}"
  rename(initrd_path, backup_name)
  copy2(backup_name, initrd_path)
  
  query = {
    'imageId':  imageId,
    'file':     backup_name,
    'type':     'initrd_backup',
    'external': False
  }
  postQuery('image/addImageFile', query)
  print(f"Old initrd backed up as {backup_name}")
  return backup_name

def restoreBackup(backup_path, initrd, imageId):
  try:
    remove(initrd)
  except:
    pass

  rename(backup_path, initrd)
  query = {
    'imageId': imageId,
    'file': backup_path
  }
  postQuery('image/deleteImageFile', query)
  print(f"Original initrd restored, backup deleted")


def modifyInitrd(initrd, rpm, image_id):
  backup_name = backupInitrd(initrd, image_id)

  todo = []
  if path.isfile(rpm):
    todo.append(rpm)
  elif path.isdir(rpm):
    todo = glob(path.join(rpm, "*.rpm"))

  # extract all rpms to the work dir
  workdir = mkdtemp()
  failed = False
  for f in todo:
    print(f"Extracting RPM {f}")
    try:
      res = call(f"rpm2cpio {f} | cpio -idm", cwd=workdir, shell=True)
      if res != 0:
        failed = True
        break
    except:
      failed = True

  if failed:
    print("Failed to extract rpm content, reverting to original")
    restoreBackup(backup_name, initrd_path, image_id)
    exit(5)
    
  print("Updating initrd with RPM files")
  with open(initrd, "a") as initrd_fh:
    res = call(f"find . | cpio -H newc -o | zstd", shell=True, cwd=workdir, stdout=initrd_fh)
    if res != 0:
      failed = True
      
  if failed:
    print("Failed to append updated initrd, reverting to original")
    restoreBackup(backup_name, initrd_path, image_id)
    exit(5)
  
  print("Initrd updated")
  
def get_md5(initrd):
  if not path.isfile(initrd):
    return res

  h = None
  s = None
  with open(initrd, 'rb') as src:
    hash_obj = md5()
    # read the file in parts, not the entire file
    for chunk in iter(lambda: src.read(65536), b""):
      hash_obj.update(chunk)
      h = hash_obj.hexdigest()
      s = stat(initrd).st_size
  return (h, s)

def updateChecksums(initrd, pillar_data, imageId, imagename):
  md5_hash, size = get_md5(initrd)
  pillar_data['boot_images'][imagename]['initrd']['hash'] = md5_hash
  pillar_data['boot_images'][imagename]['initrd']['size'] = size
  postQuery('image/setPillar', {'imageId': imageId, 'pillarData': pillar_data})

def findBackupFile(backup, backup_initrds):
  backup_name = path.basename(backup)
  found = {v for v in backup_initrds if path.basename(v) == backup_name}
  if len(found) == 1:
    return found.pop()
  return None

def removeAllBackups(backup_initrds, imageId):
  for b in backup_initrds:
    query = {
      'imageId': imageId,
      'file': b
    }
    postQuery('image/deleteImageFile', query)
    try:
      remove(b)
    except:
      pass
    print(f"Removed backup {b}")

### MAIN
if __name__ == "__main__":
  parser = ArgumentParser(
    description='Uyuni/SUSE Manager initrd updater',
    epilog='Script must be run on SUSE Manager server'
  )

  parser.add_argument('--host', help='SUSE Manager/Uyuni server to connect to', required=True)
  parser.add_argument('--api-user', default='admin', help='API user')
  parser.add_argument('--api-pass', default='admin', help='API password')

  parser.add_argument('--rpm', help='Path the the RPM or directory with RPMs to source changes from.')
  parser.add_argument('--revert', default=None, help='Revert to backup initrd. Argument specify backup filename or path to the backup file')
  parser.add_argument('--clear', default=False, help='Clear all backups', action='store_true')

  parser.add_argument('name', help='Name of the image to modify.')
  parser.add_argument('version', help='Version of the image to modify.')
  parser.add_argument('revision', help='Revision of the image to modify.')

  args = parser.parse_args()
  
  if not (args.revert is not None or args.clear) and args.rpm is None:
    print("Missing path to the RPM or directory with RPM files")
    exit(1)

  MANAGER_URL=f"https://{args.host}/rhn/manager/api/"
  MANAGER_HOST=args.host
  cookies = login(args.api_user, args.api_pass)

  image_id, initrd_path, backup_initrds, pillar_data = getImageDetails(args.name, args.version, args.revision)

  if args.revert:
    backup_file = findBackupFile(args.revert, backup_initrds)
    if backup_file is None:
      print(f"Failed to find backup file {args.revert}")
      exit(5)
    restoreBackup(backup_file, initrd_path, image_id)
  elif args.clear:
    removeAllBackups(backup_initrds, image_id)
  elif args.rpm:
    sanityCheck(initrd_path, args.rpm)
    modifyInitrd(initrd_path, args.rpm, image_id)
  else:
    print("No action specified [--rpm|--revert|--clear]")
    exit(1)
  
  updateChecksums(initrd_path, pillar_data, image_id, f"{args.name}-{args.version}-{args.revision}")
  print("All done")
