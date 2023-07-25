#!/usr/bin/env python3
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

if __name__ == "__main__":
  parser = argparse.ArgumentParser(
    description='Uyuni/SUSE Manager OS images active/inactive helper',
    epilog='Script should be run on SUSE Manager server')

  parser.add_argument('--host', help='SUSE Manager/Uyuni server to connect to', required=True)
  parser.add_argument('--api-user', default='admin', help='API user')
  parser.add_argument('--api-pass', default='admin', help='API password')

  parser.add_argument('mode', choices=['set-active', 'set-inactive'], help='Set image active or inactive')

  parser.add_argument('name', help='Name of the image to change')
  parser.add_argument('version', help='Version of the image to change without revision')
  parser.add_argument('revision', help='Revision of the image to change')

  args = parser.parse_args()

  MANAGER_URL=f"https://{args.host}/rhn/manager/api/"
  MANAGER_HOST=args.host
  cookies = login(args.api_user, args.api_pass)

  inactivity = True
  if args.mode == 'set-active':
    inactivity = False


  images = getQuery('image/listImages')
  print(f"Modifying image {args.name}, version {args.version}, revision {args.revision}")
  images = list(filter(lambda image: (image['name'] == args.name and image['version'] == args.version and image['revision'] == int(args.revision)), images))
  if len(images) == 0:
    print(f"Unable to find image with name {name}, version {version} and revision {revision}")
    exit(2)
  elif len(images) == 1:
    image_data = images[0]
  else:
    # TODO
    pass

  pillar_data = getQuery('image/getPillar', {'imageId': image_data['id']}, False)
  [(name, version_dict)] = pillar_data['images'].items()
  [(version, image_details)] = version_dict.items()
  image_details['inactive'] = inactivity

  postQuery('image/setPillar', {'imageId': image_data['id'], 'pillarData': pillar_data}) 

  print("All done")
