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

1. A source initrd. If `--initrd` is omitted, the script automatically discovers the sole registered non-external initrd candidate for the image from its registered files list (metadata-only discovery). If multiple candidates are registered (e.g. after a repeated update), omitting `--initrd` fails with an ambiguity error, and explicit path selection is required.
2. One or more local RPM sources provided via repeatable `--rpm PATH`.

It does **not** modify the source initrd in place, and it does **not** replace or unregister the original initrd. It appends a Zstandard-compressed `newc` CPIO overlay to a copied initrd and registers the result as an additional initrd file.

### Scope and warnings

- Intended as an emergency Saltboot recovery/update tool.
- Run on a Uyuni/SUSE Manager server filesystem directly or from its container host.
- Uses only documented HTTP API calls for metadata operations.
- GRUB/PXE/bootloader file updates are intentionally out of scope.

### Prerequisites

- Python 3.11+
- Python package: `requests`
- Build host commands in `PATH`: `rpm2cpio`, `cpio`, `zstd` (extraction and compression always happen locally on the script's execution machine)

### Local RPM behavior and ordering

- `--rpm` may point to an RPM file or a directory.
- Directory sources include direct `*.rpm` children only, sorted lexicographically.
- Repeated `--rpm` arguments are processed in the order provided.
- Extraction is deterministic; later RPMs overwrite earlier files in the overlay.
- Empty RPM directories are ignored, but the final resolved RPM list must not be empty.

### Excluding files from overlay

- Use repeatable `--exclude PATTERN` to exclude files/directories from the extracted RPM overlay.
- Patterns support plain names and globs.
- Name patterns (for example `__pycache__`) match path components recursively.
- Glob patterns (for example `*.pyc`) match both basename and full relative path.
- Example:

```bash
python3 os-image-tools/initrd-rpm-update.py \
  --host localhost \
  --insecure \
  --imageid 123 \
  --rpm /root/rpms \
  --exclude __pycache__ \
  --exclude '*.pyc'
```

### Organization and image selection

- Selected by required positive integer `--imageid` using the direct `image/getDetails` API. Image list enumeration is avoided.
- `--org-id` defaults to `1` and is validated with `org.getDetails`. It is the user's responsibility to align the `--org-id` with the image's real organization.
- Registered non-external image files are validated to reside inside the per-image directory: `/srv/www/os-images/<org-id>/<name>-<version>-<revision>/`.
- Registered paths attempting directory traversal or escaping this per-image store directory are strictly rejected.

### Direct Execution vs. Container Host Mode (mgrctl)

- The script automatically detects `mgrctl` in `PATH`.
- **Direct Mode (no mgrctl):** Authoritative image store operations and file installations happen directly on the local filesystem.
- **Host Mode (mgrctl present):** Assumes execution on a container host. File listings, absolute path staging, installations, permissions, and rollback/cleanup are performed inside the server container via `mgrctl cp` and safely quoted `mgrctl exec` commands.
- **Local-First Lookup:** In either mode, the selected source initrd is searched on the local machine first. If missing and `mgrctl` is available, the absolute container path is safely downloaded to a local temporary workspace using `mgrctl cp`.
- **Relative/Absolute Fallback:** Explicit relative initrd paths are resolved locally. If a relative explicit path is missing locally, execution fails with a clear instruction to provide an absolute path for container-side fallback.
- **Atomic Linking:** Staging is uploaded to a unique container temporary filename first, and linked atomically to its final path inside the container via `ln` to guarantee no overwrites or races in concurrent writer situations.
- **Service Readability:** The script ensures correct permissions (`chmod 644`) and ownership (attempting `chown :susemanager`) are applied to the final image files inside the container before registration.

### Output Naming and Cache-Busting

- New files are created in the same directory as the currently registered source initrd.
- New files are named `<original>-rpmupdate-N<suffix>` (for example `my_image-rpmupdate-1.initrd`) where `N` is the next integer after scanning:
  - image file records from `image.getDetails`
  - files present in the target initrd directory (via backend-aware listings)
- This new filename helps avoid stale downstream proxy cache use of the original initrd path.

### Pillar updates

By default, the tool updates the existing matching boot image pillar entry and calls `image.setPillar`:

- `initrd.hash`: MD5 digest of the generated initrd
- `initrd.size`: final size as a string
- `sync.initrd_url`: basename replaced with `rpmupdate-N`, preserving scheme/host/port/path parent/query/fragment

Use `--skip-pillar` to skip pillar calls entirely (`image.getPillar` and `image.setPillar` are not called). In this mode, the new initrd is still registered, and the operator must perform separate pillar/boot configuration updates.

### Failure and rollback behavior

- Temporary build and staging artifacts are cleaned up automatically on both success and failure.
- If `image.addImageFile` fails, the newly installed file is removed from the store (using direct filesystem commands or container operations).
- If `image.setPillar` fails after registration, the tool attempts to:
  1. unregister the new image file (`image.deleteImageFile`)
  2. remove the new file from the store
- On rollback problems or ambiguous network failures, the error report includes detailed manual cleanup instructions.
- The original initrd file and registration are never deleted, renamed, overwritten, or unregistered.

### TLS & CA Certificate Retrieval

- Default CA certificate path is `/srv/www/htdocs/pub/RHN-ORG-TRUSTED-SSL-CERT`.
- In container host mode, if the default CA path is missing locally, the script retrieves it from the container using `mgrctl cp` before constructing the API client and retains it for the entire API session.
- Explicit `--ca-cert PATH` takes precedence and fails clearly if missing.
- Use `--insecure` to bypass TLS verification entirely.
- **Alignment:** The API `--host` endpoint and `mgrctl` container target must refer to the same Uyuni instance.

### Examples

**Automatic Candidate Discovery (omitting `--initrd`):**
```bash
python3 os-image-tools/initrd-rpm-update.py \
  --imageid 123 \
  --org-id 1 \
  --rpm /root/rpms/
```

**Explicit Source/Reference Selection:**
```bash
python3 os-image-tools/initrd-rpm-update.py \
  --imageid 123 \
  --org-id 1 \
  --initrd /srv/www/os-images/1/my-image-1.0-1/my-image.initrd \
  --rpm /root/ptf/saltboot-fix.rpm
```
