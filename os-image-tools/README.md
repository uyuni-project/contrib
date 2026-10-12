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

It does **not** modify the source initrd in place, and it does **not** replace or unregister the original initrd. It appends a `newc` CPIO overlay, compressed like the source initrd (see below), to a copied initrd and registers the result as an additional initrd file.

### Scope and warnings

- Intended as an emergency Saltboot recovery/update tool.
- Run on a Uyuni/SUSE Manager server filesystem directly or from its container host.
- Uses only documented HTTP API calls for metadata operations.
- GRUB/PXE/bootloader file updates are intentionally out of scope.

### Prerequisites

- Python 3.11+
- Python package: `requests`
- Build host commands in `PATH`: `rpm2cpio`, `cpio`, plus the compressor matching the source initrd: `xz`, `zstd` or `gzip` (extraction and compression always happen locally on the script's execution machine)

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

### Overlay compression

The overlay is compressed with the same format as the source initrd (detected from magic bytes, skipping leading uncompressed early-microcode cpio archives), so the final file is a single-format stream that standard tools (`xz -dc`, `zstd -dc`, `3cpio`, `lsinitrd`) can read end to end. Mixing formats (for example an xz initrd with a zstd overlay) is not used because such tools fail on it and the boot kernel would additionally need the zstd initramfs decoder.

- Supported: `xz` (built with `--check=crc32`, which kernel decoders accept), `zstd`, `gzip`, and uncompressed.
- Use `--compression {auto,xz,zstd,gzip,none}` to override; the default `auto` detects. Unknown source formats (for example lz4 or bzip2) fail unless `--compression` is given explicitly.

### Updating `dracut-saltboot`

A `dracut-saltboot` RPM installs its module under `/usr/lib/dracut/modules.d/50saltboot/`, but dracut places the hook scripts elsewhere inside the initrd. The tool therefore detects RPMs containing `usr/lib/dracut/modules.d/*saltboot/module-setup.sh` and, instead of extracting them as-is, builds their overlay content from `module-setup.sh`:

- `inst_hook <hook> <prio> "$moddir/<file>"` lines: `<file>` is copied to `lib/dracut/hooks/<hook>/<prio>-<file>` (for example `saltboot.sh` becomes `lib/dracut/hooks/pre-mount/99-saltboot.sh`).
- `echo "<args>" > "${initdir}/etc/cmdline.d/<name>"` lines: the file `etc/cmdline.d/<name>` is regenerated with `<args>`.

Limitations:

- Only the two constructs above are handled; the rest of `install()` (binaries, salt minion payload, kernel modules, wicked configs) is ignored. Changes there require a proper initrd rebuild.
- Unsupported forms of `inst_hook` or `cmdline.d` lines (variables, subshells, other quoting) and a module without any `inst_hook` make the tool fail rather than guess.
- Paths use `lib/` (not `usr/lib/`), matching SLES initrds where `lib` is a real directory.
- Other files in the RPM (for example systemd units) are not added to the initrd.
- Regular RPMs given in the same run are extracted first; `dracut-saltboot` content is applied afterwards.

### Offline mode (`--no-register`)

`--no-register` only builds the updated initrd and talks to no server: no login, no API calls, no `mgrctl`, no registration, no pillar update. It requires `--initrd` (a local file) and does not need `--imageid`; `--skip-pillar` is rejected as meaningless.

The result is written next to the source initrd as `<original>-rpmupdate-N<suffix>` (next free `N` in that directory), and its md5 and size are printed. The operator is responsible for placing and registering the file and updating the pillar manually. The source directory must be writable.

```bash
python3 os-image-tools/initrd-rpm-update.py \
  --no-register \
  --initrd /root/my-image.initrd \
  --rpm /root/rpms/
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
