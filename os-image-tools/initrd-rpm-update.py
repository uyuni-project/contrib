#!/usr/bin/env python3.11
# SPDX-FileCopyrightText: 2026 SUSE LLC
#
# SPDX-License-Identifier: GPL-2.0-only

from __future__ import annotations

import argparse
import copy
import fnmatch
import getpass
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import requests
import urllib3
from urllib3.exceptions import InsecureRequestWarning

DEFAULT_CERT_PATH = "/srv/www/htdocs/pub/RHN-ORG-TRUSTED-SSL-CERT"
DEFAULT_TIMEOUT = (10, 60)


class InitrdUpdateError(RuntimeError):
    """Recoverable failure while preparing or updating the generated initrd."""


@dataclass(frozen=True)
class ImageFileRecord:
    file: str
    file_type: str
    external: bool
    local_path: Path | None

    @property
    def basename(self) -> str:
        return Path(self.file).name


@dataclass(frozen=True)
class ImageContext:
    image_id: int
    store_dir: Path
    image_dir: Path
    files: list[ImageFileRecord]
    initrd_files: list[Path]
    api_file_values: list[str]
    prefer_absolute_file_paths: bool


import shlex

def is_host_mode() -> bool:
    return getattr(is_host_mode, "_cache", False)

is_host_mode._cache = shutil.which("mgrctl") is not None


def store_is_dir(path: Path) -> bool:
    if is_host_mode():
        cmd_str = f"[ -d {shlex.quote(str(path))} ]"
        res = subprocess.run(["mgrctl", "exec", cmd_str], capture_output=True, check=False)
        return res.returncode == 0
    else:
        return path.is_dir()


def store_list_dir(path: Path) -> list[str]:
    if is_host_mode():
        cmd_str = f"ls -1 {shlex.quote(str(path))}"
        res = subprocess.run(["mgrctl", "exec", cmd_str], capture_output=True, check=False)
        if res.returncode != 0:
            return []
        output = res.stdout.decode("utf-8", errors="replace").strip()
        return [line.strip() for line in output.splitlines() if line.strip()]
    else:
        if path.is_dir():
            return [entry.name for entry in path.iterdir()]
        return []


def store_remove_file(path: Path) -> str | None:
    if is_host_mode():
        cmd_str = f"rm -f {shlex.quote(str(path))}"
        res = subprocess.run(["mgrctl", "exec", cmd_str], capture_output=True, check=False)
        if res.returncode != 0:
            return f"failed to remove container file {path}: {res.stderr.decode('utf-8', errors='replace').strip()}"
        return None
    else:
        try:
            path.unlink()
            return None
        except OSError as exc:
            return f"failed to remove local file {path}: {exc}"


def store_install_file_exclusive(local_source: Path, destination_path: Path) -> None:
    """Installs local_source into destination_path on the store.

    Raises FileExistsError if destination_path already exists.
    Raises InitrdUpdateError on other errors.
    """
    if is_host_mode():
        staging_path = destination_path.with_name(destination_path.name + ".staging")
        cmd_cp = ["mgrctl", "cp", str(local_source), f"server:{staging_path}"]
        res_cp = subprocess.run(cmd_cp, capture_output=True, check=False)
        if res_cp.returncode != 0:
            err = res_cp.stderr.decode("utf-8", errors="replace").strip()
            raise InitrdUpdateError(f"Failed to copy staging file to container: {err}")

        try:
            cmd_ln = f"ln {shlex.quote(str(staging_path))} {shlex.quote(str(destination_path))}"
            res_ln = subprocess.run(["mgrctl", "exec", cmd_ln], capture_output=True, check=False)

            if res_ln.returncode != 0:
                cmd_exists = f"[ -f {shlex.quote(str(destination_path))} ]"
                res_exists = subprocess.run(["mgrctl", "exec", cmd_exists], capture_output=True, check=False)
                if res_exists.returncode == 0:
                    raise FileExistsError(f"Destination {destination_path} already exists in container")
                else:
                    err_ln = res_ln.stderr.decode("utf-8", errors="replace").strip()
                    raise InitrdUpdateError(f"Failed to create hard link inside container: {err_ln}")

            cmd_chmod = f"chmod 644 {shlex.quote(str(destination_path))} && (chown :susemanager {shlex.quote(str(destination_path))} || true)"
            subprocess.run(["mgrctl", "exec", cmd_chmod], capture_output=True, check=False)

        finally:
            cmd_rm = f"rm -f {shlex.quote(str(staging_path))}"
            subprocess.run(["mgrctl", "exec", cmd_rm], capture_output=True, check=False)

    else:
        source_stat = local_source.stat()
        try:
            fd = os.open(
                destination_path,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                source_stat.st_mode & 0o777,
            )
        except FileExistsError:
            raise
        except OSError as exc:
            raise InitrdUpdateError(
                f"Failed to create destination file {destination_path}: {exc}"
            ) from exc

        try:
            with os.fdopen(fd, "wb") as destination, local_source.open("rb") as source:
                shutil.copyfileobj(source, destination)
            os.utime(destination_path, (source_stat.st_atime, source_stat.st_mtime))
            destination_path.chmod(0o644)
            try:
                shutil.chown(destination_path, group="susemanager")
            except Exception:
                pass
        except Exception as exc:
            cleanup_error = store_remove_file(destination_path)
            if cleanup_error is not None:
                raise InitrdUpdateError(
                    f"Exclusive install failed for {destination_path}: {exc}. "
                    f"Rollback failed: {cleanup_error}. Manual cleanup required."
                ) from exc
            raise InitrdUpdateError(
                f"Exclusive install failed for {destination_path}: {exc}. "
                "Partial destination file was removed."
            ) from exc


def _format_api_messages(messages: Any) -> str:
    if isinstance(messages, str):
        return messages
    if isinstance(messages, list):
        return "; ".join(str(message) for message in messages)
    return str(messages)


def _stderr_text(data: bytes | None) -> str:
    if not data:
        return ""
    text = data.decode("utf-8", errors="replace").strip()
    return text[:4000]


class ApiClient:
    def __init__(
        self,
        base_url: str,
        verify_ssl: str | bool = DEFAULT_CERT_PATH,
        timeout: tuple[int, int] = DEFAULT_TIMEOUT,
        debug: bool = False,
        session: requests.Session | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/") + "/"
        self.verify_ssl = verify_ssl
        self.timeout = timeout
        self.debug = debug
        self.session = session if session is not None else requests.Session()

    def login(self, username: str, password: str) -> None:
        try:
            self.post(
                "auth/login",
                {"login": username, "password": password},
                expect_result=False,
            )
        except InitrdUpdateError as exc:
            raise InitrdUpdateError(f"Login failed: {exc}") from exc

    def get(self, method: str, params: dict[str, Any] | None = None) -> Any:
        return self._request("GET", method, params=params)

    def post(
        self,
        method: str,
        payload: dict[str, Any],
        expect_result: bool = True,
    ) -> Any:
        return self._request(
            "POST", method, payload=payload, expect_result=expect_result
        )

    def _debug_log(self, message: str) -> None:
        if self.debug:
            print(f"DEBUG: {message}", file=os.sys.stderr)

    def _sanitize_for_debug(self, value: Any) -> Any:
        if isinstance(value, dict):
            sanitized: dict[str, Any] = {}
            for key, item in value.items():
                if any(
                    secret in key.lower()
                    for secret in ("pass", "password", "token", "secret")
                ):
                    sanitized[key] = "***"
                else:
                    sanitized[key] = self._sanitize_for_debug(item)
            return sanitized
        if isinstance(value, list):
            return [self._sanitize_for_debug(item) for item in value]
        return value

    def _json_for_debug(self, value: Any) -> str:
        try:
            rendered = json.dumps(self._sanitize_for_debug(value), sort_keys=True)
        except TypeError:
            rendered = repr(value)
        if len(rendered) > 2000:
            return rendered[:2000] + "..."
        return rendered

    def _request(
        self,
        verb: str,
        method: str,
        params: dict[str, Any] | None = None,
        payload: dict[str, Any] | None = None,
        expect_result: bool = True,
    ) -> Any:
        url = self.base_url + method
        request_kwargs: dict[str, Any] = {
            "verify": self.verify_ssl,
            "timeout": self.timeout,
        }
        if params is not None:
            request_kwargs["params"] = params
        if payload is not None:
            request_kwargs["json"] = payload

        self._debug_log(
            f"HTTP {verb} {method} request params={self._json_for_debug(params)} "
            f"payload={self._json_for_debug(payload)}"
        )

        try:
            if verb == "GET":
                response = self.session.get(url, **request_kwargs)
            elif verb == "POST":
                response = self.session.post(url, **request_kwargs)
            else:
                raise InitrdUpdateError(f"Unsupported HTTP verb: {verb}")
            response.raise_for_status()
            self._debug_log(
                f"HTTP {verb} {method} response status={response.status_code}"
            )
        except requests.RequestException as exc:
            raise InitrdUpdateError(f"HTTP {verb} {method} failed: {exc}") from exc

        response_text = response.text.strip()
        if response_text:
            truncated = response_text[:2000]
            suffix = "..." if len(response_text) > 2000 else ""
            self._debug_log(f"HTTP {verb} {method} raw body={truncated}{suffix}")

        try:
            body = response.json()
        except ValueError as exc:
            snippet = response.text.strip().replace("\n", " ")
            if len(snippet) > 300:
                snippet = snippet[:300] + "..."
            raise InitrdUpdateError(
                f"HTTP {verb} {method} returned malformed JSON. "
                f"Response snippet: {snippet!r}"
            ) from exc

        if not isinstance(body, dict):
            raise InitrdUpdateError(
                f"HTTP {verb} {method} returned JSON that is not an object"
            )

        if "success" not in body:
            raise InitrdUpdateError(
                f"HTTP {verb} {method} response did not include 'success'"
            )

        if body["success"] is not True:
            message = _format_api_messages(
                body.get("messages", body.get("message", "unknown API failure"))
            )
            raise InitrdUpdateError(f"API {method} failed: {message}")

        if not expect_result:
            return body.get("result")

        if "result" not in body:
            keys = ", ".join(sorted(body.keys()))
            raise InitrdUpdateError(
                f"HTTP {verb} {method} response did not include 'result'. "
                f"Response keys: {keys}"
            )

        return body["result"]


def build_manager_url(host: str) -> str:
    normalized = host.strip()
    if not normalized:
        raise InitrdUpdateError("Manager host cannot be empty")

    if not normalized.startswith(("http://", "https://")):
        normalized = f"https://{normalized}"

    return normalized.rstrip("/") + "/rhn/manager/api/"


def validate_organization(client: ApiClient, org_id: int) -> None:
    client.get("org/getDetails", params={"orgId": int(org_id)})


def _resolve_registered_path(org_store: Path, image_dir: Path, registered_file: str) -> Path:
    raw_path = Path(registered_file)
    if ".." in raw_path.parts:
        raise InitrdUpdateError(
            f"Registered file path {registered_file!r} escapes store directories"
        )

    if raw_path.is_absolute():
        candidate = raw_path
    else:
        # Avoid prepending the image directory twice
        parts = raw_path.parts
        if parts and parts[0] == image_dir.name:
            candidate = org_store / raw_path
        else:
            candidate = image_dir / raw_path

    # Logical validation of containment
    try:
        norm_org = Path(os.path.normpath(org_store.absolute()))
        norm_image = Path(os.path.normpath(image_dir.absolute()))
        norm_candidate = Path(os.path.normpath(candidate.absolute()))
        norm_candidate.relative_to(norm_org)
        norm_candidate.relative_to(norm_image)
    except ValueError as exc:
        raise InitrdUpdateError(
            f"Registered file path {registered_file!r} escapes store directory or expected image directory"
        ) from exc

    return norm_candidate


def get_image_context(
    client: ApiClient, image_id: int, org_store: Path, image_dir: Path
) -> ImageContext:
    if not store_is_dir(org_store):
        raise InitrdUpdateError(f"Organization store directory not found: {org_store}")

    details = client.get("image/getDetails", params={"imageId": image_id})
    if not isinstance(details, dict):
        raise InitrdUpdateError("image/getDetails returned an unexpected payload")

    raw_files = details.get("files")
    if not isinstance(raw_files, list):
        raise InitrdUpdateError("image/getDetails did not include a valid files list")

    records: list[ImageFileRecord] = []
    initrd_files: list[Path] = []
    prefer_absolute: bool | None = None

    for entry in raw_files:
        if not isinstance(entry, dict):
            raise InitrdUpdateError(
                "image/getDetails files list contains invalid entries"
            )
        file_value = entry.get("file")
        file_type = entry.get("type")
        if not isinstance(file_value, str) or not file_value:
            raise InitrdUpdateError(
                "image/getDetails file entry has an invalid 'file' value"
            )
        if not isinstance(file_type, str) or not file_type:
            raise InitrdUpdateError(
                "image/getDetails file entry has an invalid 'type' value"
            )

        external = bool(entry.get("external", False))
        local_path: Path | None = None

        if not external:
            local_path = _resolve_registered_path(org_store, image_dir, file_value)
            if prefer_absolute is None:
                prefer_absolute = Path(file_value).is_absolute()

        record = ImageFileRecord(
            file=file_value,
            file_type=file_type,
            external=external,
            local_path=local_path,
        )
        records.append(record)

        if file_type == "initrd":
            if not external and local_path is not None:
                initrd_files.append(local_path)

    if not initrd_files:
        raise InitrdUpdateError(
            "No registered non-external initrd image files were found on the image"
        )

    return ImageContext(
        image_id=image_id,
        store_dir=org_store,
        image_dir=image_dir,
        files=records,
        initrd_files=initrd_files,
        api_file_values=[record.file for record in records],
        prefer_absolute_file_paths=bool(prefer_absolute),
    )


def _url_basename(url: str) -> str:
    parsed = urlsplit(url)
    basename = Path(parsed.path).name
    if not basename:
        raise InitrdUpdateError(f"Invalid initrd URL without basename: {url!r}")
    return basename


def get_active_initrd(pillar: dict[str, Any], initrd_files: Sequence[Path]) -> Path:
    sync = pillar.get("sync")
    if not isinstance(sync, dict):
        raise InitrdUpdateError("Pillar is missing 'sync' object")

    initrd_url = sync.get("initrd_url")
    if not isinstance(initrd_url, str) or not initrd_url:
        raise InitrdUpdateError("Pillar is missing 'sync.initrd_url'")

    active_basename = _url_basename(initrd_url)
    matches = [path for path in initrd_files if path.name == active_basename]

    if not matches:
        raise InitrdUpdateError(
            "Unable to correlate pillar sync.initrd_url with registered initrd files"
        )
    if len(matches) > 1:
        raise InitrdUpdateError(
            "Pillar sync.initrd_url matches multiple registered initrd files"
        )
    return matches[0]


def _matching_boot_image_key(pillar: dict[str, Any], active_basename: str) -> str:
    boot_images = pillar.get("boot_images")
    if not isinstance(boot_images, dict):
        raise InitrdUpdateError("Pillar is missing 'boot_images' object")

    matches: list[str] = []
    for key, value in boot_images.items():
        if not isinstance(value, dict):
            continue
        sync = value.get("sync")
        if not isinstance(sync, dict):
            continue
        initrd_url = sync.get("initrd_url")
        if not isinstance(initrd_url, str) or not initrd_url:
            continue
        if _url_basename(initrd_url) == active_basename:
            matches.append(key)

    if not matches:
        raise InitrdUpdateError(
            "No boot_images pillar entry matches the active initrd URL/file relationship"
        )
    if len(matches) > 1:
        raise InitrdUpdateError(
            "Multiple boot_images pillar entries match the active initrd URL/file relationship"
        )
    return matches[0]


def resolve_rpm_sources(paths: Sequence[str | Path]) -> list[Path]:
    rpms: list[Path] = []

    for source in paths:
        source_path = Path(source).expanduser()
        if source_path.is_file():
            if source_path.suffix.lower() != ".rpm":
                raise InitrdUpdateError(
                    f"RPM source file must end with .rpm: {source_path}"
                )
            rpms.append(source_path.resolve())
            continue

        if source_path.is_dir():
            children = sorted(
                (
                    child.resolve()
                    for child in source_path.iterdir()
                    if child.is_file() and child.suffix.lower() == ".rpm"
                ),
                key=lambda child: child.name,
            )
            rpms.extend(children)
            continue

        raise InitrdUpdateError(f"RPM source path does not exist: {source_path}")

    if not rpms:
        raise InitrdUpdateError("No RPM files found after resolving all --rpm sources")
    return rpms


def verify_required_tools() -> None:
    missing = [
        tool for tool in ("rpm2cpio", "cpio", "zstd") if shutil.which(tool) is None
    ]
    if missing:
        raise InitrdUpdateError(
            "Missing required external command(s): " + ", ".join(missing)
        )


def extract_rpms(rpms: Sequence[Path], overlay_dir: Path) -> None:
    for rpm in rpms:
        rpm2cpio_proc = subprocess.Popen(
            ["rpm2cpio", str(rpm)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        cpio_proc = subprocess.Popen(
            ["cpio", "-idm", "--unconditional", "--quiet"],
            stdin=rpm2cpio_proc.stdout,
            cwd=overlay_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        if rpm2cpio_proc.stdout is not None:
            rpm2cpio_proc.stdout.close()

        _, cpio_stderr = cpio_proc.communicate()
        _, rpm2cpio_stderr = rpm2cpio_proc.communicate()

        if rpm2cpio_proc.returncode != 0:
            raise InitrdUpdateError(
                f"rpm2cpio failed for {rpm}: {_stderr_text(rpm2cpio_stderr)}"
            )
        if cpio_proc.returncode != 0:
            raise InitrdUpdateError(
                f"cpio extraction failed for {rpm}: {_stderr_text(cpio_stderr)}"
            )


def _is_glob_pattern(value: str) -> bool:
    return any(symbol in value for symbol in "*?[")


def _excluded_entry(
    rel_path: str, exclude_patterns: Sequence[str], is_dir: bool
) -> bool:
    normalized_rel_path = rel_path.strip("/")
    path_obj = Path(normalized_rel_path)
    basename = path_obj.name
    components = path_obj.parts

    for raw_pattern in exclude_patterns:
        pattern = raw_pattern.strip()
        if not pattern:
            continue
        normalized_pattern = pattern.strip("/")

        if _is_glob_pattern(normalized_pattern):
            if fnmatch.fnmatch(normalized_rel_path, normalized_pattern):
                return True
            if fnmatch.fnmatch(basename, normalized_pattern):
                return True
            continue

        if "/" in normalized_pattern:
            if normalized_rel_path == normalized_pattern:
                return True
            if is_dir and normalized_rel_path.startswith(normalized_pattern + "/"):
                return True
            continue

        if normalized_pattern in components:
            return True

    return False


def _overlay_entries_filtered(
    overlay_dir: Path,
    exclude_patterns: Sequence[str] | None = None,
) -> list[str]:
    patterns = list(exclude_patterns or [])

    seen: set[str] = {"."}
    entries = ["."]

    for root, dirnames, filenames in os.walk(overlay_dir):
        dirnames.sort()
        filenames.sort()

        root_rel = Path(root).relative_to(overlay_dir)
        if root_rel != Path(".") and _excluded_entry(
            root_rel.as_posix(), patterns, True
        ):
            dirnames[:] = []
            continue

        kept_dirnames: list[str] = []
        for dirname in dirnames:
            rel_dir = (
                root_rel / dirname if root_rel != Path(".") else Path(dirname)
            ).as_posix()
            if not _excluded_entry(rel_dir, patterns, True):
                kept_dirnames.append(dirname)
        dirnames[:] = kept_dirnames

        if root_rel != Path("."):
            rel_value = root_rel.as_posix()
            if rel_value not in seen:
                entries.append(rel_value)
                seen.add(rel_value)

        for dirname in dirnames:
            rel_path = (
                root_rel / dirname if root_rel != Path(".") else Path(dirname)
            ).as_posix()
            if rel_path not in seen:
                entries.append(rel_path)
                seen.add(rel_path)

        for filename in filenames:
            rel_path = (
                root_rel / filename if root_rel != Path(".") else Path(filename)
            ).as_posix()
            if _excluded_entry(rel_path, patterns, False):
                continue
            if rel_path not in seen:
                entries.append(rel_path)
                seen.add(rel_path)

    return entries


def build_overlay_member(
    overlay_dir: Path,
    output_path: Path,
    exclude_patterns: Sequence[str] | None = None,
) -> None:
    if exclude_patterns:
        entries = _overlay_entries_filtered(overlay_dir, exclude_patterns)
    else:
        entries = _overlay_entries_filtered(overlay_dir)
    archive_input = "\0".join(entries).encode("utf-8") + b"\0"

    temp_cpio = output_path.with_suffix(output_path.suffix + ".cpio")
    try:
        with temp_cpio.open("wb") as cpio_archive:
            cpio_result = subprocess.run(
                ["cpio", "--null", "-o", "-H", "newc", "--quiet"],
                cwd=overlay_dir,
                input=archive_input,
                stdout=cpio_archive,
                stderr=subprocess.PIPE,
                check=False,
            )
        if cpio_result.returncode != 0:
            raise InitrdUpdateError(
                f"cpio archive build failed: {_stderr_text(cpio_result.stderr)}"
            )

        zstd_result = subprocess.run(
            ["zstd", "-q", "-z", "-o", str(output_path), str(temp_cpio)],
            capture_output=True,
            check=False,
        )
        if zstd_result.returncode != 0:
            raise InitrdUpdateError(
                f"zstd compression failed: {_stderr_text(zstd_result.stderr)}"
            )
    finally:
        if temp_cpio.exists():
            temp_cpio.unlink()


def validate_overlay_member(output_path: Path) -> None:
    zstd_test = subprocess.run(
        ["zstd", "--test", str(output_path)],
        capture_output=True,
        check=False,
    )
    if zstd_test.returncode != 0:
        raise InitrdUpdateError(
            f"zstd --test failed for overlay member: {_stderr_text(zstd_test.stderr)}"
        )

    zstd_proc = subprocess.Popen(
        ["zstd", "-d", "-c", str(output_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    cpio_proc = subprocess.Popen(
        ["cpio", "-t", "--quiet"],
        stdin=zstd_proc.stdout,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    if zstd_proc.stdout is not None:
        zstd_proc.stdout.close()

    _, cpio_stderr = cpio_proc.communicate()
    _, zstd_stderr = zstd_proc.communicate()

    if zstd_proc.returncode != 0:
        raise InitrdUpdateError(
            f"zstd decompression failed for overlay member: {_stderr_text(zstd_stderr)}"
        )
    if cpio_proc.returncode != 0:
        raise InitrdUpdateError(
            f"cpio listing failed for overlay member: {_stderr_text(cpio_stderr)}"
        )


def build_updated_initrd(
    source_initrd: Path, overlay_member: Path, output_path: Path
) -> None:
    shutil.copy2(source_initrd, output_path)
    with output_path.open("ab") as destination, overlay_member.open("rb") as source:
        shutil.copyfileobj(source, destination)


def compute_md5_and_size(path: Path) -> tuple[str, int]:
    with path.open("rb") as source:
        digest = hashlib.file_digest(source, "md5").hexdigest()
    return digest, path.stat().st_size


def next_output_name(
    original_name: str,
    api_files: Iterable[str | Path],
    store_entries: Iterable[str | Path] | Path,
) -> str:
    numbers: list[int] = []

    original_path = Path(original_name)
    suffix = "".join(original_path.suffixes)
    prefix = original_name[: -len(suffix)] if suffix else original_name
    pattern = re.compile(
        r"^" + re.escape(prefix) + r"-rpmupdate-(\d+)" + re.escape(suffix) + r"$"
    )

    names: list[str] = [Path(str(value)).name for value in api_files]
    if isinstance(store_entries, Path):
        names.extend(entry.name for entry in store_entries.iterdir())
    else:
        names.extend(Path(str(value)).name for value in store_entries)

    for name in names:
        match = pattern.fullmatch(name)
        if match:
            numbers.append(int(match.group(1)))

    next_number = (max(numbers) + 1) if numbers else 1
    return f"{prefix}-rpmupdate-{next_number}{suffix}"


def update_initrd_url(url: str, filename: str) -> str:
    parsed = urlsplit(url)
    path = parsed.path
    if not path:
        raise InitrdUpdateError(f"Cannot update basename in URL without path: {url!r}")

    parent, separator, basename = path.rpartition("/")
    if not basename:
        raise InitrdUpdateError(f"Cannot update basename in URL path: {url!r}")

    if separator:
        new_path = f"{parent}/{filename}"
    else:
        new_path = filename

    return urlunsplit(parsed._replace(path=new_path))


def updated_pillar(
    pillar: dict[str, Any],
    active_initrd: Path,
    filename: str,
    digest: str,
    size: int,
) -> dict[str, Any]:
    new_pillar = copy.deepcopy(pillar)

    sync = new_pillar.get("sync")
    if not isinstance(sync, dict):
        raise InitrdUpdateError("Pillar is missing 'sync' object")

    current_sync_url = sync.get("initrd_url")
    if not isinstance(current_sync_url, str) or not current_sync_url:
        raise InitrdUpdateError("Pillar is missing 'sync.initrd_url'")

    boot_image_key = _matching_boot_image_key(new_pillar, active_initrd.name)
    boot_image_entry = new_pillar["boot_images"].get(boot_image_key)
    if not isinstance(boot_image_entry, dict):
        raise InitrdUpdateError("Matching boot_images pillar entry is invalid")

    initrd_data = boot_image_entry.get("initrd")
    if not isinstance(initrd_data, dict):
        raise InitrdUpdateError(
            "Matching boot_images pillar entry is missing 'initrd' object"
        )

    boot_sync = boot_image_entry.get("sync")
    if not isinstance(boot_sync, dict):
        raise InitrdUpdateError(
            "Matching boot_images pillar entry is missing 'sync' object"
        )

    boot_sync_url = boot_sync.get("initrd_url")
    if not isinstance(boot_sync_url, str) or not boot_sync_url:
        raise InitrdUpdateError(
            "Matching boot_images pillar entry is missing 'sync.initrd_url'"
        )

    initrd_data["hash"] = digest
    initrd_data["size"] = str(size)
    sync["initrd_url"] = update_initrd_url(current_sync_url, filename)
    boot_sync["initrd_url"] = update_initrd_url(boot_sync_url, filename)
    return new_pillar


def validate_pillar_for_update(pillar: dict[str, Any], active_initrd: Path) -> None:
    updated_pillar(
        pillar,
        active_initrd=active_initrd,
        filename=active_initrd.name,
        digest="0" * 32,
        size=0,
    )


def _api_file_value_for_path(image_context: ImageContext, path: Path) -> str:
    if image_context.prefer_absolute_file_paths:
        return str(path)
    return path.relative_to(image_context.store_dir).as_posix()


def install_generated_file(
    new_initrd_path: Path,
    image_context: ImageContext,
    reference_initrd: Path,
) -> Path:
    target_dir = reference_initrd.parent
    existing_api_basenames = {
        Path(value).name for value in image_context.api_file_values
    }

    for _ in range(2048):
        store_entries = store_list_dir(target_dir)
        output_name = next_output_name(
            reference_initrd.name,
            image_context.api_file_values,
            store_entries,
        )
        if output_name in existing_api_basenames:
            raise InitrdUpdateError(
                "Generated output name unexpectedly matches an existing image file"
            )

        destination_path = target_dir / output_name
        try:
            store_install_file_exclusive(new_initrd_path, destination_path)
            return destination_path
        except FileExistsError:
            continue

    raise InitrdUpdateError(
        "Unable to install generated initrd because rpmupdate-N names keep colliding"
    )


def install_and_register(
    client: ApiClient,
    image_context: ImageContext,
    image_id: int,
    new_initrd_path: Path,
    digest: str,
    size: int,
    pillar: dict[str, Any] | None,
    active_initrd: Path | None,
    reference_initrd: Path,
    skip_pillar: bool,
) -> Path:
    installed_path = install_generated_file(
        new_initrd_path,
        image_context,
        reference_initrd,
    )
    api_file_value = _api_file_value_for_path(image_context, installed_path)
    add_payload = {
        "imageId": image_id,
        "file": api_file_value,
        "type": "initrd",
        "external": False,
    }

    try:
        client.post("image/addImageFile", add_payload)
    except InitrdUpdateError as add_error:
        removal_error = store_remove_file(installed_path)
        if removal_error is not None:
            raise InitrdUpdateError(
                "image.addImageFile failed and rollback could not remove the new file. "
                f"Original error: {add_error}. Rollback error: {removal_error}. "
                f"Manual cleanup: remove {installed_path} in the store filesystem"
            ) from add_error
        raise

    if skip_pillar:
        return installed_path

    if pillar is None or active_initrd is None:
        raise InitrdUpdateError(
            "Internal error: pillar update requested without pillar context"
        )

    pillar_payload = {
        "imageId": image_id,
        "pillarData": updated_pillar(
            pillar,
            active_initrd=active_initrd,
            filename=installed_path.name,
            digest=digest,
            size=size,
        ),
    }

    try:
        client.post("image/setPillar", pillar_payload)
    except InitrdUpdateError as pillar_error:
        rollback_errors: list[str] = []
        try:
            client.post(
                "image/deleteImageFile",
                {"imageId": image_id, "file": api_file_value},
            )
        except InitrdUpdateError as cleanup_error:
            rollback_errors.append(f"failed to unregister image file: {cleanup_error}")

        remove_error = store_remove_file(installed_path)
        if remove_error is not None:
            rollback_errors.append(remove_error)

        if rollback_errors:
            raise InitrdUpdateError(
                "image.setPillar failed and rollback was incomplete. "
                f"Original error: {pillar_error}. Rollback errors: {'; '.join(rollback_errors)}. "
                "Manual cleanup: unregister the new initrd with image.deleteImageFile "
                f"(imageId={image_id}, file={api_file_value!r}) and remove {installed_path} in the store filesystem"
            ) from pillar_error

        raise InitrdUpdateError(
            "image.setPillar failed after registering the new initrd; rollback succeeded and "
            "removed the new registration and file"
        ) from pillar_error

    return installed_path


def run_update(client: ApiClient, args: argparse.Namespace) -> str:
    rpm_sources = resolve_rpm_sources(args.rpm)
    verify_required_tools()

    validate_organization(client, args.org_id)
    image_id = args.imageid

    # Retrieve image details
    details = client.get("image/getDetails", params={"imageId": image_id})
    if not isinstance(details, dict):
        raise InitrdUpdateError("image/getDetails returned an unexpected payload")

    name = details.get("name")
    version = details.get("version")
    revision = details.get("revision")

    # Validate metadata to prevent traversal, separators, malformed values
    if not isinstance(name, str) or not name or "/" in name or "\\" in name or ".." in name:
        raise InitrdUpdateError(f"image/getDetails returned an invalid or unsafe image name: {name!r}")
    if not isinstance(version, str) or not version or "/" in version or "\\" in version or ".." in version:
        raise InitrdUpdateError(f"image/getDetails returned an invalid or unsafe image version: {version!r}")
    if revision is None or not str(revision).isdigit() or "/" in str(revision) or "\\" in str(revision) or ".." in str(revision):
        raise InitrdUpdateError(f"image/getDetails returned an invalid or unsafe image revision: {revision!r}")

    org_store = Path("/srv/www/os-images") / str(args.org_id)
    image_dir = org_store / f"{name}-{version}-{revision}"
    image_context = get_image_context(client, image_id, org_store, image_dir)

    pillar: dict[str, Any] | None = None
    active_initrd: Path | None = None

    if not args.skip_pillar:
        pillar_result = client.get("image/getPillar", params={"imageId": image_id})
        if not isinstance(pillar_result, dict):
            raise InitrdUpdateError("image/getPillar did not return pillar data")
        pillar = pillar_result
        active_initrd = get_active_initrd(pillar, image_context.initrd_files)
        validate_pillar_for_update(pillar, active_initrd)

    # Candidate selection
    candidates = [r for r in image_context.files if r.file_type == "initrd" and not r.external]

    if not args.initrd:
        # No explicit --initrd
        if not candidates:
            raise InitrdUpdateError(
                f"No non-external registered initrd files found for image ID {image_id}"
            )
        elif len(candidates) == 1:
            reference_record = candidates[0]
            source_server_path = reference_record.local_path
        else:
            cand_paths = "\n".join(f"  - {cand.local_path}" for cand in candidates)
            raise InitrdUpdateError(
                f"Multiple registered initrd files found for image ID {image_id}. "
                "Omit --initrd only when exactly one candidate exists. Candidates:\n"
                f"{cand_paths}\n"
                "Please re-run specifying one of these paths using --initrd PATH"
            )
    else:
        # Explicit --initrd
        explicit_path = Path(args.initrd).expanduser()

        if not candidates:
            raise InitrdUpdateError(
                f"No non-external registered initrd files found for image ID {image_id}"
            )

        exact_match = None
        normalized_explicit = Path(os.path.normpath(explicit_path.absolute()))
        for cand in candidates:
            if cand.local_path:
                norm_cand = Path(os.path.normpath(cand.local_path.absolute()))
                if norm_cand == normalized_explicit:
                    exact_match = cand
                    break

        if exact_match:
            reference_record = exact_match
        else:
            basename_matches = [cand for cand in candidates if cand.basename == explicit_path.name]
            if len(basename_matches) == 1:
                reference_record = basename_matches[0]
            elif len(basename_matches) > 1:
                cand_paths = ", ".join(str(c.local_path) for c in basename_matches)
                raise InitrdUpdateError(
                    f"Explicit initrd basename {explicit_path.name!r} matches multiple registered initrds: {cand_paths}"
                )
            else:
                if len(candidates) == 1:
                    reference_record = candidates[0]
                else:
                    cand_paths = ", ".join(str(c.local_path) for c in candidates)
                    raise InitrdUpdateError(
                        f"Unable to resolve registered naming reference for explicit initrd {args.initrd!r}. "
                        f"Candidates are: {cand_paths}"
                    )

        source_server_path = explicit_path

    # Local-first lookup of the source initrd bytes
    local_source_initrd: Path | None = None
    try:
        if source_server_path.exists() and source_server_path.is_file():
            with source_server_path.open("rb"):
                pass
            local_source_initrd = source_server_path
    except PermissionError as exc:
        raise InitrdUpdateError(f"Permission denied reading local file {source_server_path}: {exc}")
    except Exception:
        pass

    if local_source_initrd is None:
        if not source_server_path.is_absolute():
            raise InitrdUpdateError(
                f"Explicit relative initrd path {source_server_path} was not found locally. "
                "Please provide a readable local file or specify an absolute server path for container retrieval."
            )
        if not is_host_mode():
            raise InitrdUpdateError(
                f"Source initrd file not found on local filesystem: {source_server_path}"
            )

    debug_log = getattr(client, "_debug_log", None)
    if callable(debug_log):
        debug_log(
            f"Reference initrd for target directory and naming: {reference_record.local_path}"
        )

    with tempfile.TemporaryDirectory(prefix="initrd-rpm-update-") as temp_dir_name:
        temp_dir = Path(temp_dir_name)

        if local_source_initrd is None:
            downloaded_source = temp_dir / "downloaded-source-initrd"
            cmd_cp = ["mgrctl", "cp", f"server:{source_server_path}", str(downloaded_source)]
            res_cp = subprocess.run(cmd_cp, capture_output=True, check=False)
            if res_cp.returncode != 0:
                err = res_cp.stderr.decode("utf-8", errors="replace").strip()
                raise InitrdUpdateError(
                    f"Source initrd was not found locally, and retrieving it from container "
                    f"path {source_server_path} failed: {err}"
                )
            if not downloaded_source.is_file():
                raise InitrdUpdateError(
                    f"Fetched container file {source_server_path} is not a regular file or is empty."
                )
            local_source_initrd = downloaded_source

        overlay_dir = temp_dir / "overlay"
        overlay_dir.mkdir(parents=True, exist_ok=True)

        overlay_member = temp_dir / "overlay-newc.zst"
        new_initrd = temp_dir / "updated-initrd"

        extract_rpms(rpm_sources, overlay_dir)
        build_overlay_member(
            overlay_dir,
            overlay_member,
            getattr(args, "exclude", []),
        )
        validate_overlay_member(overlay_member)
        build_updated_initrd(local_source_initrd, overlay_member, new_initrd)
        digest, size = compute_md5_and_size(new_initrd)

        installed_path = install_and_register(
            client=client,
            image_context=image_context,
            image_id=image_id,
            new_initrd_path=new_initrd,
            digest=digest,
            size=size,
            pillar=pillar,
            active_initrd=active_initrd,
            reference_initrd=reference_record.local_path,
            skip_pillar=args.skip_pillar,
        )

    if args.skip_pillar:
        return (
            "Completed: new initrd registered as "
            f"{installed_path.name}, but pillar metadata and URL were intentionally not "
            "updated because --skip-pillar was used"
        )

    return (
        f"Completed: new initrd registered as {installed_path.name} with md5={digest} "
        f"and size={size}"
    )


def positive_int(value: str) -> int:
    try:
        val = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{value!r} is not a valid integer")
    if val <= 0:
        raise argparse.ArgumentTypeError(f"{val} must be a positive integer (> 0)")
    return val


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Emergency Saltboot initrd updater. Creates a new initrd by appending a "
            "zstd-compressed newc CPIO overlay built from local RPMs."
        ),
        epilog="Run this tool on a Uyuni/SUSE Manager server.",
    )
    parser.add_argument(
        "--host",
        default="localhost",
        help=(
            "Uyuni/SUSE Manager server host (default: localhost). "
            "When no scheme is provided, https is used"
        ),
    )
    parser.add_argument("--api-user", default="admin", help="API username")
    parser.add_argument(
        "--api-pass",
        help="API password (or provide UYUNI_API_PASSWORD, otherwise prompt)",
    )
    parser.add_argument(
        "--org-id",
        type=int,
        default=1,
        help="Uyuni organization id (default: 1)",
    )
    parser.add_argument(
        "--imageid",
        type=positive_int,
        required=True,
        help="Numeric ID of the image to select and update",
    )
    parser.add_argument(
        "--initrd",
        help="Path to a manually downloaded source initrd (optional)",
    )
    parser.add_argument(
        "--rpm",
        action="append",
        required=True,
        metavar="PATH",
        help="RPM file or directory with direct .rpm children (repeatable, ordered)",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="PATTERN",
        help=(
            "Exclude files/directories from overlay by name or glob. Repeatable. "
            "Examples: __pycache__, *.pyc, usr/lib/python*/site-packages/*"
        ),
    )
    parser.add_argument(
        "--skip-pillar",
        action="store_true",
        help="Register the new initrd file but do not call image.getPillar/image.setPillar",
    )
    parser.add_argument(
        "--ca-cert",
        default=DEFAULT_CERT_PATH,
        help=f"CA bundle for API TLS verification (default: {DEFAULT_CERT_PATH})",
    )
    parser.add_argument(
        "--insecure",
        action="store_true",
        help=(
            "Disable API TLS certificate verification (emergency use only). "
            "Also suppresses urllib3 InsecureRequestWarning"
        ),
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Print debug logs for API requests/responses and workflow decisions",
    )
    return parser


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = build_parser()
    return parser.parse_args(argv)


def _resolve_password(args: argparse.Namespace) -> str:
    if args.api_pass:
        return args.api_pass
    env_password = os.environ.get("UYUNI_API_PASSWORD")
    if env_password:
        return env_password
    return getpass.getpass("API password: ")


def main(argv: Sequence[str] | None = None) -> int:
    temp_ca_file: Path | None = None
    try:
        args = parse_args(argv)
        password = _resolve_password(args)

        # Detect host mode early
        is_host_mode._cache = shutil.which("mgrctl") is not None

        verify_ssl: str | bool = False if args.insecure else args.ca_cert

        if not args.insecure:
            ca_path = Path(args.ca_cert)
            if not ca_path.is_file():
                if is_host_mode():
                    fd, path_str = tempfile.mkstemp(prefix="ca-cert-", suffix=".crt")
                    os.close(fd)
                    temp_ca_file = Path(path_str)

                    cmd_cp = ["mgrctl", "cp", f"server:{args.ca_cert}", str(temp_ca_file)]
                    res_cp = subprocess.run(cmd_cp, capture_output=True, check=False)
                    if res_cp.returncode != 0:
                        err_msg = res_cp.stderr.decode("utf-8", errors="replace").strip()
                        raise InitrdUpdateError(
                            f"CA certificate {args.ca_cert} is not present locally, and "
                            f"retrieving it from the container failed: {err_msg}"
                        )
                    verify_ssl = str(temp_ca_file)
                else:
                    raise InitrdUpdateError(
                        f"CA certificate file not found: {args.ca_cert}"
                    )

        if args.insecure:
            urllib3.disable_warnings(InsecureRequestWarning)

        client = ApiClient(
            build_manager_url(args.host),
            verify_ssl=verify_ssl,
            debug=args.debug,
        )
        client.login(args.api_user, password)
        print(run_update(client, args))
        return 0
    except InitrdUpdateError as exc:
        print(f"Error: {exc}")
        return 1
    finally:
        if temp_ca_file and temp_ca_file.exists():
            try:
                temp_ca_file.unlink()
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
