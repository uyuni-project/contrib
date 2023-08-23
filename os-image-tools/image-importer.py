#!/usr/bin/env python3

"""
Image analyzer and importer for SUSE Manager/Uyuni

Use in case of need to manually import kiwi os pxe images to the SUSE Manager/Uyuni

Workflow:
    1) copy content of /var/lib/Kiwi/buildXXXXX/images.build from the Kiwi build to the SUSE Manager/Uyuni server
    2) call this script specifying source directory, organization to import under, revision number if needed
"""

import argparse
import json
import requests

import os
import re

from hashlib import md5
from pprint import pprint
from shutil import move

# Kiwi version is always in format "MAJOR.MINOR.RELEASE" with numeric values
# Source https://osinside.github.io/kiwi/image_description/elements.html#preferences-version
KIWI_VERSION_REGEX=r'\d+\.\d+\.\d+'
# Taken from Kiwi sources https://github.com/OSInside/kiwi/blob/eb2b1a84bf7/kiwi/schema/kiwi.rng#L81
KIWI_ARCH_REGEX=r'(x86_64|i586|i686|ix86|aarch64|arm64|armv5el|armv5tel|armv6hl|armv6l|armv7hl|armv7l|ppc|ppc64|ppc64le|s390|s390x|riscv64)'
# Taken from Kiwi sources https://github.com/OSInside/kiwi/blob/eb2b1a84bf7/kiwi/schema/kiwi.rng#L26
KIWI_NAME_REGEX=r'[a-zA-Z0-9_\-\.]+'

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
    print(f"POST request {query} failed with error {res.text}")
    exit(1)
  elif not res.json()['success']:
    print(f"POST request {query} failed with error {res.json()}")
    exit(1)
  return res.json()['result']
### API

### SLE11/SLE12 image metadata parser
_compression_types = [
    { 'suffix': '.gz', 'compression': 'gzip' },
    { 'suffix': '.bz', 'compression': 'bzip' },
    { 'suffix': '.xz', 'compression': 'xz' },
    { 'suffix': '.install.iso', 'compression': None },
    { 'suffix': '.iso',         'compression': None },
    { 'suffix': '.qcow2',       'compression': None },
    { 'suffix': '.ova',         'compression': None },
    { 'suffix': '.vmdk',        'compression': None },
    { 'suffix': '.vmx',         'compression': None },
    { 'suffix': '.vhd',         'compression': None },
    { 'suffix': '.vhdx',        'compression': None },
    { 'suffix': '.vdi',         'compression': None },
    { 'suffix': '.raw',         'compression': None },
    { 'suffix': '',    'compression': None }
    ]

def guess_buildinfo(dest):
    ret = {'main': {}}

    pattern_basename = re.compile(r"^(?P<basename>.*)\.packages$")
    pattern_pxe_initrd = re.compile(r"^initrd-netboot.*")
    pattern_pxe_kiwi_ng_initrd = re.compile(r".*\.initrd\..*")
    pattern_pxe_kernel = re.compile(r".*\.kernel\..*")
    pattern_pxe_kiwi_ng_kernel = re.compile(r".*\.kernel$")
    have_kernel = False
    have_initrd = False

    for f in os.listdir(dest):
        match = pattern_basename.match(f)
        if match:
            ret['main']['image.basename'] = match.group('basename')

        match = pattern_pxe_initrd.match(f) or pattern_pxe_kiwi_ng_initrd.match(f)
        if match:
            have_initrd = True

        match = pattern_pxe_kernel.match(f) or pattern_pxe_kiwi_ng_kernel.match(f)
        if match:
            have_kernel = True

    if have_kernel and have_initrd:
        ret['main']['image.type'] = 'pxe'
    return ret

def parse_buildinfo(dest):
    ret = {}
    path = os.path.join(dest, 'kiwi.buildinfo')
    if os.path.isfile(path):
        pattern_group = re.compile(r"^\[(?P<name>.*)\]")
        pattern_val = re.compile(r"^(?P<name>.*?)=(?P<val>.*)")

        group = ret
        with open(path) as f:
            for line in f:
              match = pattern_group.match(line)
              if match:
                  group = {}
                  ret[match.group('name')] = group

              match = pattern_val.match(line)
              if match:
                  group[match.group('name')] = match.group('val')
    return ret

def get_md5(path):
    res = {}
    if not os.path.isfile(path):
        return res

    res['hash'] = md5(path).hexdigest()
    res['size'] = os.stat(path).get('size')
    return res

def parse_kiwi_md5(path, compressed = False):
    res = {}

    if not os.path.isfile(path):
        return res
    with open(path) as f:
        md5_str = f.read()

    if md5_str is not None:
        if compressed:
            pattern = re.compile(r"^(?P<md5>[0-9a-f]+)\s+(?P<size1>[0-9]+)\s+(?P<size2>[0-9]+)\s+(?P<csize1>[0-9]+)\s+(?P<csize2>[0-9]+)\s*$")
        else:
            pattern = re.compile(r"^(?P<md5>[0-9a-f]+)\s+(?P<size1>[0-9]+)\s+(?P<size2>[0-9]+)\s*$")
        match = pattern.match(md5_str)
        if match:
            res['hash'] = match.group('md5')
            res['size'] = int(match.group('size1')) * int(match.group('size2'))
            if compressed:
                res['compressed_size'] = int(match.group('csize1')) * int(match.group('csize2'))
    return res

def image_details(dest, bundle_dest = None):
    res = {}
    buildinfo = parse_buildinfo(dest) or guess_buildinfo(dest)
    kiwiresult = {}

    basename = buildinfo.get('main', {}).get('image.basename', '')
    image_type = buildinfo.get('main', {}).get('image.type', 'unknown')
    fstype = kiwiresult.get('filesystem')

    pattern = re.compile(r"^(?P<name>{})\.(?P<arch>{})-(?P<version>{})$".format(KIWI_NAME_REGEX, KIWI_ARCH_REGEX, KIWI_VERSION_REGEX))
    match = pattern.match(basename)

    if match:
        name = match.group('name')
        arch = match.group('arch')
        version = match.group('version')
    else:
        return None

    filename = None
    filepath = None
    compression = None
    for c in _compression_types:
        path = os.path.join(dest, basename + c['suffix'])
        if os.path.isfile(path):
            compression = c['compression']
            filename = basename + c['suffix']
            filepath = path
            break

    res['image'] = {
        'basename': basename,
        'name': name,
        'arch': arch,
        'type': image_type,
        'version': version,
        'filename': filename,
        'filepath': filepath,
        'fstype': fstype
    }
    if compression:
        res['image'].update({
            'compression': compression,
            'compressed_hash': get_md5(filepath).get('hash')
        })

    res['image'].update(parse_kiwi_md5(os.path.join(dest, basename + '.md5'), compression is not None))

    if bundle_dest is not None:
      res['bundles'] = inspect_bundles(bundle_dest, basename)

    return res

def inspect_image(dest, build_id, bundle_dest = None):
    res = image_details(dest, bundle_dest)
    if not res:
      return None

    res['image']['build_id'] = build_id

    basename = res['image']['basename']
    image_type = res['image']['type']

    for fstype in ['ext2', 'ext3', 'ext4', 'btrfs', 'xfs']:
        path = os.path.join(dest, basename + '.' + fstype)
        if os.path.isfile(path) or os.path.islink(path):
            res['image']['fstype'] = fstype
            break

    if image_type == 'pxe':
        res['boot_image'] = inspect_boot_image(dest)

    return res

def inspect_boot_image(dest):
    res = None

    pattern = re.compile(r"^(?P<name>{})\.(?P<arch>{})-(?P<version>{})\.kernel\.(?P<kernelversion>.*)\.md5$".format(KIWI_NAME_REGEX, KIWI_ARCH_REGEX, KIWI_VERSION_REGEX))
    pattern_kiwi_ng = re.compile(r"^(?P<name>{})\.(?P<arch>{})-(?P<version>{})-(?P<kernelversion>.*)\.kernel$".format(KIWI_NAME_REGEX, KIWI_ARCH_REGEX, KIWI_VERSION_REGEX))
    for f in os.listdir(dest):
        match = pattern.match(f)
        if match:
            basename = match.group('name') + '.' + match.group('arch') + '-' + match.group('version')
            res = {
                'name': match.group('name'),
                'arch': match.group('arch'),
                'basename': basename,
                'initrd': {
                    'version': match.group('version')
                    },
                'kernel': {
                    'version': match.group('kernelversion')
                    },
                'kiwi_ng': False
            }
            break
        match = pattern_kiwi_ng.match(f)
        if match:
            basename = match.group('name') + '.' + match.group('arch') + '-' + match.group('version')
            res = {
                'name': match.group('name'),
                'arch': match.group('arch'),
                'basename': basename,
                'initrd': {
                    'version': match.group('version')
                    },
                'kernel': {
                    'version': match.group('kernelversion')
                },
                'kiwi_ng': True
            }
            break

    if res is None:
        return None

    for c in _compression_types:
        if res['kiwi_ng']:
            file = basename + '.initrd' + c['suffix']
        else:
            file = basename + c['suffix']
        filepath = os.path.join(dest, file)
        if os.path.isfile(filepath):
            res['initrd']['filename'] = file
            res['initrd']['filepath'] = filepath
            if res['kiwi_ng']:
                res['initrd'].update(get_md5(filepath))
            else:
                res['initrd'].update(parse_kiwi_md5(os.path.join(dest, basename + '.md5')))
            break

    if res['kiwi_ng']:
        file = basename + '-' + res['kernel']['version'] + '.kernel'
        filepath = os.path.join(dest, file)
        if os.path.isfile(filepath):
            res['kernel']['filename'] = file
            res['kernel']['filepath'] = filepath
            res['kernel'].update(get_md5(filepath))
    else:
        file = basename + '.kernel.' + res['kernel']['version']
        filepath = os.path.join(dest, file)
        if os.path.isfile(filepath):
            res['kernel']['filename'] = file
            res['kernel']['filepath'] = filepath
            res['kernel'].update(parse_kiwi_md5(filepath + '.md5'))
    return res

def inspect_bundles(dest, basename):
    res = []
    files = os.path.isdir(dest)

    pattern = re.compile(r"^(?P<basename>" + re.escape(basename) + r")-(?P<id>[^.]*)\.(?P<suffix>.*)\.sha256$")
    for f in files:
        match = pattern.match(f)
        if match:
            res1 = match.groupdict()
            sha256_file = f
            with open(os.path.join(dest, f)) as sha256_file:
                sha256_str = sha256_file.read()
            pattern2 = re.compile(r"^(?P<hash>[0-9a-f]+)\s+(?P<filename>.*)\s*$")
            match = pattern2.match(sha256_str)
            if match:
                d = match.groupdict()
                d['hash'] = d['hash']
                res1.update(d)
                res1['filepath'] = os.path.join(dest, res1['filename'])
            else:
                # only hash without file name
                pattern2 = re.compile(r"^(?P<hash>[0-9a-f]+)$")
                match = pattern2.match(sha256_str)
                if match:
                    res1['hash'] = match.groupdict()['hash']
                    res1['filename'] = sha256_file[0:-len('.sha256')]
                    res1['filepath'] = os.path.join(dest, res1['filename'])
            res.append(res1)
    return res

def prepare_pillars(images_details, hostname, org, revision):
    revision = f'-{revision}'
    pillar_data = {}

    sync_details = {}
    image_data = images_details['image']
    boot_data = images_details['boot_image']
    file_name = image_data['filename']
    name_version = f"{image_data['name']}-{image_data['version']}{revision}"
    name_arch_version = f"{image_data['name']}.{image_data['arch']}-{image_data['version']}{revision}"
    local_path = os.path.join('image', name_arch_version)

    if images_details.get('bundles'):
        bundle_data = images_details['bundles']
        sync_details = {
          'bundle_hash': bundle_data['hash'],
          'bundle_url': f'https://{hostname}/os-images/{org}/{bundle_data["filepath"]}'
        }
    else:
        sync_details = {
          'hash': image_data['hash'],
          'url': f'https://{hostname}/os-images/{org}/{name_version}/{file_name}'
        }
    sync_details['local_path'] = local_path

    version_data = {}
    version_data[f"{image_data['version']}{revision}"] = {
       'url': f"https://ftp/saltboot/{local_path}/{file_name}",
       'arch': image_data['arch'],
       'boot_image': name_version,
       'filename': file_name,
       'fstype': image_data['fstype'],
       'hash': image_data['hash'],
       'size': image_data['size'],
       'inactive': False,
       'type': image_data['type'],
       'sync': sync_details,
    }

    pillar_data['images'] = {
        image_data['name']:  version_data,
    }

    if image_data['type'] == 'pxe':
      if images_details.get('bundles'):
         boot_sync = {}
      else:
         boot_sync = {
           'initrd_url': f'https://{hostname}/os-images/{org}/{name_version}/{boot_data["initrd"]["filename"]}',
           'kernel_url': f'https://{hostname}/os-images/{org}/{name_version}/{boot_data["kernel"]["filename"]}',
         }

      boot_sync['local_path'] = name_arch_version
      boot_image = {
        'arch': boot_data['arch'],
        'basename': boot_data['basename'],
        'name': boot_data['name'],
        'initrd': boot_data['initrd'],
        'kernel': boot_data['kernel'],
        'sync': boot_sync
      }
      pillar_data['boot_images'] = {
        f'{name_version}': boot_image,
      }

    return pillar_data

### Importer

def import_image(pillar_data, orgid, srcdir, nomove, dryrun):

    name = next(iter(pillar_data['images']))
    version = next(iter(pillar_data['images'][name]))

    image_data = pillar_data['images'][name][version]
    boot_image = pillar_data['boot_images'][f'{name}-{version}']

    arch = image_data['arch']
    if arch == 'x86_64':
        arch = 'x86_64-redhat-linux'
    else:
        arch = 'i386-redhat-linux'
        
    print(f'Importing image {name}-{version}')

    image = {
        'name': name,
        'version': version,
        'arch': arch
    }
    if dryrun:
      imageId = 1
    else:
      imageId = int(postQuery('image/importOSImage', image))
    if not imageId:
      print(f"Failed to get imageId for imported image, check if image already exists")
      exit(3)

    if dryrun:
      pprint(pillar_data)
    else:
      postQuery('image/setPillar', {'imageId': imageId, 'pillarData': pillar_data})

    image_path = f'{name}-{version}'
    dstdir = os.path.join('/srv/www/os-images', str(orgid), image_path)

    if image_data.get('bundles'):
        url_regex = re.compile(rf'^https://[^/]+/os-images/{orgid}/(?P<filename>.*)$')
        match = url_regex.match(file['url'])
        files = [{
            'file': match.group('filename'),
            'type': 'bundle'
        }]
    else:
        files = [{
            'file': boot_image['kernel']['filename'],
            'type': 'kernel'
            },{
            'file': boot_image['initrd']['filename'],
            'type': 'initrd'
            },{
            'file': image_data['filename'],
            'type': 'image'
            }]

    files_to_move = []
    for file in files:
      f = {
        'imageId': imageId,
        'file': os.path.join(image_path, file['file']),
        'type': file['type'],
        'external': False
      }
      if dryrun:
        pprint(f)
      else:
        postQuery('image/addImageFile', f)
        if (not nomove):
          move_image_file(file['file'], srcdir, dstdir)

def move_image_file(filename, srcdir, dstdir):
  try:
      os.mkdir(dstdir)
  except FileExistsError:
      pass
  
  src = os.path.join(srcdir, filename)
  dst = os.path.join(dstdir, filename)
  print(f'Moving image file {src} to the {dst}')
  try:
    move(src, dst)
  except:
    print(f'Failed to move file {src} to the destination {dst}. Please move them manually')

if __name__ == "__main__":
  parser = argparse.ArgumentParser(
    description='SUSE Manager OS images metadata import for Kiwi build OS images',
    epilog='Script should be run on SUSE Manager server and does not copy any image files!')

  parser.add_argument('--host', help='SUSE Manager server to connect to', required=True)
  parser.add_argument('--api-user', default='admin', help='API user')
  parser.add_argument('--api-pass', default='admin', help='API password')

  parser.add_argument('--dry-run', help='Do not move nor register images, print data to submit', action='store_true')
  parser.add_argument('--no-move', help='Do not automatically move image files', action='store_true')
  parser.add_argument('--revision', default=1, help='Revision of the image build')
  parser.add_argument('--org-id', default=1, help='Organization ID')
  parser.add_argument('directory', help='Directory with build image and metadata')
  parser.add_argument('build_id', help='Build ID for given image')

  args = parser.parse_args()

  MANAGER_URL=f"https://{args.host}/rhn/manager/api/"
  MANAGER_HOST=args.host
  cookies = login(args.api_user, args.api_pass)

  if args.dry_run:
      print("Running in DRY RUN mode. Assuming imageId = 1")

  image_data = inspect_image(args.directory, args.build_id)
  pillar_data = prepare_pillars(image_data, args.host, args.org_id, args.revision)
  import_image(pillar_data, args.org_id, args.directory, args.no_move, args.dry_run)
  print("All done")
