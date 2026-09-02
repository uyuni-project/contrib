# OS Image helper tools for Uyuni/SUSE Manager

## osimage-import-export.py

Export and import OS image metadata from one server to another.

This script does not copy actual image files! Script only dumps metadata, including image pillars if present, of one OS image entry and then allows to import them to different server.
If pillar is present and data contains URL of source server, like in case of Saltboot PXE images, this URL is mangled and translated to the target server on import.

## set-os-image-activity.py

Set individual image as active or inactive.

Saltboot understands image flag `inactive`. If this flag is set to `True`, then image is not considered for Saltboot deployment. By default it is set to `False`.

## initrd-rpm-update.py

Emergency-only helper for Saltboot images.

This tool creates a new initrd file from:

1. A manually downloaded source initrd provided via `--initrd`
2. One or more local RPM sources provided via repeatable `--rpm PATH`

It does **not** modify the source initrd in place, and it does **not** replace or unregister the original initrd. It appends a Zstandard-compressed `newc` CPIO overlay to a copied initrd and registers the result as an additional initrd file.

### Scope and warnings

- Intended as an emergency Saltboot recovery/update tool.
- Run on a Uyuni/SUSE Manager server.
- Uses only documented HTTP API calls for metadata operations.
- GRUB/PXE/bootloader file updates are intentionally out of scope.

### Prerequisites

- Python 3.11+
- Python package: `requests`
- Host commands in `PATH`: `rpm2cpio`, `cpio`, `zstd`
- Read/write access to `/srv/www/os-images/<org-id>/`

### Local RPM behavior and ordering

- `--rpm` may point to an RPM file or a directory.
- Directory sources include direct `*.rpm` children only, sorted lexicographically.
- Repeated `--rpm` arguments are processed in the order provided.
- Extraction is deterministic; later RPMs overwrite earlier files in the overlay.
- Empty RPM directories are ignored, but the final resolved RPM list must not be empty.

### Organization and image selection

- `--org-id` defaults to `1` and is validated with `org.getDetails`.
- Image is selected by exact `name`, `version`, and integer `revision` from `image.listImages`.
- Zero or multiple matches fail with an explicit error.
- Registered non-external image files are validated to remain inside `/srv/www/os-images/<org-id>/`.

### Output naming and cache-busting

- New files are named `rpmupdate-N` where `N` is the next integer after scanning:
  - image file records from `image.getDetails`
  - files present in `/srv/www/os-images/<org-id>/`
- The tool uses exclusive create/retry behavior to avoid overwrite on races.
- This new filename helps avoid stale downstream proxy cache use of the original initrd path.

### Pillar updates

By default, the tool updates the existing matching boot image pillar entry and calls `image.setPillar`:

- `initrd.hash`: MD5 digest of the generated initrd
- `initrd.size`: final size as a string
- `sync.initrd_url`: basename replaced with `rpmupdate-N`, preserving scheme/host/port/path parent/query/fragment

Use `--skip-pillar` to skip pillar calls entirely (`image.getPillar` and `image.setPillar` are not called). In this mode, the new initrd is still registered, and the operator must perform separate pillar/boot configuration updates.

### Failure and rollback behavior

- Temporary build artifacts are cleaned up automatically.
- If `image.addImageFile` fails, the newly installed file is removed.
- If `image.setPillar` fails after registration, the tool attempts to:
  1. unregister the new image file (`image.deleteImageFile`)
  2. remove the new physical file
- On rollback problems, the error includes explicit manual cleanup steps.
- The original initrd file and registration are never deleted, renamed, overwritten, or unregistered.

### Example

```bash
python3 os-image-tools/initrd-rpm-update.py \
  --host manager.example.com \
  --api-user admin \
  --org-id 1 \
  --initrd /root/downloaded/initrd \
  --rpm /root/rpms/ \
  --rpm /root/ptf/saltboot-fix.rpm \
  sle-micro 5.5 2
```
