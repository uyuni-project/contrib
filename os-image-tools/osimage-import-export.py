#!/usr/bin/env python3

"""
This script helps with transfering images between two SUSE Manager/Uyuni servers.

Script does not copy or move any files, only helps with exporting and importing image metadata.

Workflow:

1) Call script with `export` option to export metadata of the image
2) Transfer image files from one server to another, see `files` section of the exported metadata
3) Call script with `import` option on the target server to import image metadata

Script takes care of URL mandling between different servers if required (for example for PXE images)
"""

import argparse
import json
from pprint import pprint
import requests

SSLVERIFY = "/srv/www/htdocs/pub/RHN-ORG-TRUSTED-SSL-CERT"

### API
def login(user, password):
  data = {"login": user, "password": password}
  res = requests.post(MANAGER_URL + 'auth/login', json=data, verify=SSLVERIFY)
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
  res = requests.get(MANAGER_URL + query + queryParams, cookies=cookies, verify=SSLVERIFY)
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
  res = requests.post(MANAGER_URL + query, json=queryData, cookies=cookies, verify=SSLVERIFY)
  if res.status_code != 200:
    print(f"POST request {query} failed with error {res}")
    exit(1)
  elif not res.json()['success']:
    print(f"POST request {query} failed with error {res.json()}")
    exit(1)
  return res.json()['result']
### API

def mangle_pillar_data(pillar, what, to):
  for _, image in pillar['images'].items():
    for _, version in image.items():
      sync = version['sync']
      if sync.get('url'):
        sync.update({'url': sync['url'].replace(what, to)})
      if sync.get('bundle_url'):
        sync.update({'bundle_url': sync['bundle_url'].replace(what, to)})
  for _, image in pillar['boot_images'].items():
    sync = image['sync']
    if sync.get('initrd_url'):
      sync.update({'initrd_url': sync['initrd_url'].replace(what, to)})
    if sync.get('kernel_url'):
      sync.update({'kernel_url': sync['kernel_url'].replace(what, to)})
  return pillar

### EXPORT
def filter_files_data(files):
  res = []
  for file in files:
    filtered = {k:v for k, v in file.items() if k != 'url'}
    res.append(filtered)
  return res

def filter_image_data(image):
  return {k:v for k, v in image.items() if k == 'name' or k == 'version' or k == 'arch'}

def exportImage(name, version, revision, output):
  images = getQuery('image/listImages')
  print(f"Exporting image {name}, version {version}, revision {revision}")
  images = list(filter(lambda image: (image['name'] == name and image['version'] == version and image['revision'] == int(revision)), images))
  if len(images) == 0:
    print(f"Unable to find image with name {name}, version {version} and revision {revision}")
    exit(2)
  elif len(images) == 1:
    image_data = images[0]
  else:
    pass
  pillar_data = getQuery('image/getPillar', {'imageId': image_data['id']}, False)
  if pillar_data:
    pillar_data = mangle_pillar_data(pillar_data, MANAGER_HOST, '{{HOST}}')

  files_data = getQuery('image/getDetails', {'imageId': image_data['id']}).get('files', {})
  files_data = filter_files_data(files_data)

  result = {
    'image': filter_image_data(image_data),
    'files': files_data,
    'pillar': pillar_data
  }
  if output:
    with open(output, 'w') as out_fh:
      json.dump(result, out_fh, indent=2)
  else:
    pprint(result)
### EXPORT

### IMPORT
def importImage(file):
    print(f"Importing image data from {file}")
    image_data = None
    with open(file, 'r') as fh:
      image_data = json.load(fh)

    imageId = int(postQuery('image/importOSImage', image_data['image']))
    if not imageId:
      print(f"Failed to get imageId for imported image from file {file}")
      exit(3)
    new_pillar = mangle_pillar_data(image_data['pillar'], '{{HOST}}', MANAGER_HOST)
    postQuery('image/setPillar', {'imageId': imageId, 'pillarData': new_pillar})
    for f in image_data['files']:
      f['imageId'] = imageId
      postQuery('image/addImageFile', f)

### IMPORT

if __name__ == "__main__":
  parser = argparse.ArgumentParser(
    description='Uyuni/SUSE Manager OS images metadata import/export tool',
    epilog='Script should be run on SUSE Manager server and does not copy any image files!')

  parser.add_argument('--host', help='SUSE Manager/Uyuni server to connect to', required=True)
  parser.add_argument('--api-user', default='admin', help='API user')
  parser.add_argument('--api-pass', default='admin', help='API password')

  subparsers = parser.add_subparsers()
  export_parser = subparsers.add_parser('export', help='Image export mode')
  export_parser.add_argument('name', help='Name of the image to export')
  export_parser.add_argument('version', help='Version of the image to export without revision.')
  export_parser.add_argument('revision', help='Revision of the image to export.')
  export_parser.add_argument('--outfile', help='Store result to file instead of using standard output', required=False)
  export_parser.set_defaults(mode='export')

  import_parser = subparsers.add_parser('import', help='Image import mode')
  import_parser.add_argument('filename', help='Filename with image data to be imported')
  import_parser.set_defaults(mode='import')

  args = parser.parse_args()

  MANAGER_URL=f"https://{args.host}/rhn/manager/api/"
  MANAGER_HOST=args.host
  cookies = login(args.api_user, args.api_pass)

  if args.mode == 'export':
    exportImage(args.name, args.version, args.revision, args.outfile)
  elif args.mode == 'import':
    importImage(args.filename)


  print("All done")
