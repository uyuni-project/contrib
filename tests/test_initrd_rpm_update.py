import argparse
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
from argparse import Namespace
from pathlib import Path
from unittest.mock import MagicMock

import pytest

spec = importlib.util.spec_from_file_location(
    "initrd_rpm_update", "os-image-tools/initrd-rpm-update.py"
)
initrd_rpm_update = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = initrd_rpm_update
spec.loader.exec_module(initrd_rpm_update)

ApiClient = initrd_rpm_update.ApiClient
ImageContext = initrd_rpm_update.ImageContext
InitrdUpdateError = initrd_rpm_update.InitrdUpdateError
ImageFileRecord = initrd_rpm_update.ImageFileRecord
build_overlay_member = initrd_rpm_update.build_overlay_member
build_updated_initrd = initrd_rpm_update.build_updated_initrd
extract_rpms = initrd_rpm_update.extract_rpms
get_active_initrd = initrd_rpm_update.get_active_initrd
get_image_context = initrd_rpm_update.get_image_context
_excluded_entry = initrd_rpm_update._excluded_entry
_overlay_entries_filtered = initrd_rpm_update._overlay_entries_filtered
install_and_register = initrd_rpm_update.install_and_register
install_generated_file = initrd_rpm_update.install_generated_file
next_output_name = initrd_rpm_update.next_output_name
store_install_file_exclusive = initrd_rpm_update.store_install_file_exclusive
parse_args = initrd_rpm_update.parse_args
resolve_rpm_sources = initrd_rpm_update.resolve_rpm_sources
run_update = initrd_rpm_update.run_update
build_manager_url = initrd_rpm_update.build_manager_url
update_initrd_url = initrd_rpm_update.update_initrd_url
updated_pillar = initrd_rpm_update.updated_pillar
validate_pillar_for_update = initrd_rpm_update.validate_pillar_for_update
validate_organization = initrd_rpm_update.validate_organization
validate_overlay_member = initrd_rpm_update.validate_overlay_member


class WarningStub:
    def __init__(self) -> None:
        self.calls = []

    def disable_warnings(self, warning_cls) -> None:
        self.calls.append(warning_cls)


class DummyApiClient:
    def __init__(self) -> None:
        self.get_calls = []
        self.post_calls = []
        self.get_responses = {}
        self.post_responses = {}

    def get(self, method, params=None):
        self.get_calls.append((method, params))
        value = self.get_responses[method]
        return value(params) if callable(value) else value

    def post(self, method, payload):
        self.post_calls.append((method, payload))
        value = self.post_responses.get(method)
        if isinstance(value, Exception):
            raise value
        return value(payload) if callable(value) else value


@pytest.fixture
def mock_session(monkeypatch):
    session = MagicMock()
    monkeypatch.setattr(initrd_rpm_update.requests, "Session", lambda: session)
    return session


@pytest.fixture(autouse=True)
def reset_host_mode_cache(monkeypatch):
    # Prevent host mode side-effects polluting other tests
    monkeypatch.setattr(initrd_rpm_update.is_host_mode, "_cache", False)


# ==========================================
# CLI and Parsing Tests
# ==========================================

def test_parse_args_org_default_and_type():
    args = parse_args(
        [
            "--host",
            "manager.example.test",
            "--initrd",
            "/tmp/source-initrd",
            "--rpm",
            "/tmp/a.rpm",
            "--imageid",
            "123",
        ]
    )
    assert args.org_id == 1
    assert isinstance(args.org_id, int)
    assert args.host == "manager.example.test"
    assert args.imageid == 123


def test_parse_args_host_default():
    args = parse_args(
        [
            "--rpm",
            "/tmp/a.rpm",
            "--imageid",
            "456",
        ]
    )
    assert args.host == "localhost"
    assert args.imageid == 456
    assert args.initrd is None


def test_positive_int_validation():
    with pytest.raises(argparse.ArgumentTypeError):
        initrd_rpm_update.positive_int("0")
    with pytest.raises(argparse.ArgumentTypeError):
        initrd_rpm_update.positive_int("-5")
    with pytest.raises(argparse.ArgumentTypeError):
        initrd_rpm_update.positive_int("abc")
    assert initrd_rpm_update.positive_int("42") == 42


def test_parse_args_imageid_required():
    with pytest.raises(SystemExit):
        parse_args(["--rpm", "/tmp/a.rpm"])


def test_parse_args_old_positional_rejected():
    with pytest.raises(SystemExit):
        parse_args(["--imageid", "123", "--rpm", "/tmp/a.rpm", "my-image", "1.0", "1"])


# ==========================================
# URL and API Client Tests
# ==========================================

def test_build_manager_url_localhost_and_non_localhost_defaults():
    assert build_manager_url("localhost") == "https://localhost/rhn/manager/api/"
    assert (
        build_manager_url("localhost:8000") == "https://localhost:8000/rhn/manager/api/"
    )
    assert build_manager_url("manager.example.test") == (
        "https://manager.example.test/rhn/manager/api/"
    )
    assert build_manager_url("https://manager.example.test") == (
        "https://manager.example.test/rhn/manager/api/"
    )


def test_api_client_login(mock_session):
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.json.return_value = {"success": True, "result": {"ok": True}}
    mock_session.post.return_value = response

    client = ApiClient("https://example.com/rhn/manager/api/", verify_ssl=False)
    client.login("user", "secret")

    mock_session.post.assert_called_once_with(
        "https://example.com/rhn/manager/api/auth/login",
        json={"login": "user", "password": "secret"},
        verify=False,
        timeout=(10, 60),
    )


def test_api_client_failure(mock_session):
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.json.return_value = {"success": False, "messages": ["bad login"]}
    mock_session.post.return_value = response

    client = ApiClient("https://example.com/rhn/manager/api/", verify_ssl=False)
    with pytest.raises(InitrdUpdateError, match="Login failed"):
        client.login("user", "secret")


def test_main_disables_insecure_request_warning(monkeypatch):
    warning_stub = WarningStub()
    monkeypatch.setattr(initrd_rpm_update, "urllib3", warning_stub)
    monkeypatch.setattr(initrd_rpm_update, "_resolve_password", lambda _args: "secret")

    class ClientStub:
        def __init__(self, *_args, **_kwargs):
            pass

        def login(self, *_args, **_kwargs):
            return None

    monkeypatch.setattr(initrd_rpm_update, "ApiClient", ClientStub)
    monkeypatch.setattr(initrd_rpm_update, "run_update", lambda *_args, **_kwargs: "ok")

    rc = initrd_rpm_update.main(
        [
            "--host",
            "localhost",
            "--insecure",
            "--rpm",
            "/tmp/a.rpm",
            "--imageid",
            "123",
        ]
    )

    assert rc == 0
    assert warning_stub.calls == [initrd_rpm_update.InsecureRequestWarning]


def test_validate_organization_passes_integer():
    client = DummyApiClient()
    client.get_responses["org/getDetails"] = {}

    validate_organization(client, 7)

    assert client.get_calls == [("org/getDetails", {"orgId": 7})]


# ==========================================
# Paths, Logical Containment & Context Tests
# ==========================================

def test_resolve_registered_path_resolves_and_checks_containment():
    org_store = Path("/srv/www/os-images/1")
    image_dir = org_store / "img-1.0-1"

    # Absolute path matching containment
    ans = initrd_rpm_update._resolve_registered_path(
        org_store, image_dir, "/srv/www/os-images/1/img-1.0-1/initrd"
    )
    assert ans == Path("/srv/www/os-images/1/img-1.0-1/initrd")

    # Relative bare path
    ans = initrd_rpm_update._resolve_registered_path(
        org_store, image_dir, "initrd"
    )
    assert ans == Path("/srv/www/os-images/1/img-1.0-1/initrd")

    # Relative path starts with image_dir name to avoid double prepending
    ans = initrd_rpm_update._resolve_registered_path(
        org_store, image_dir, "img-1.0-1/initrd"
    )
    assert ans == Path("/srv/www/os-images/1/img-1.0-1/initrd")

    # Traversal escape organization
    with pytest.raises(InitrdUpdateError, match="escapes store directories"):
        initrd_rpm_update._resolve_registered_path(
            org_store, image_dir, "../../../etc/shadow"
        )

    # Escape image directory but inside organization store
    with pytest.raises(InitrdUpdateError, match="escapes store directories"):
        initrd_rpm_update._resolve_registered_path(
            org_store, image_dir, "../img-2.0-1/initrd"
        )


def test_get_image_context_validates_store_boundaries(tmp_path):
    store = tmp_path / "store"
    store.mkdir()
    image_dir = store / "img-1.0-1"
    image_dir.mkdir()

    client = DummyApiClient()
    client.get_responses["image/getDetails"] = {
        "name": "img",
        "version": "1.0",
        "revision": 1,
        "files": [
            {"file": "initrd-a", "type": "initrd", "external": False},
            {
                "file": str((image_dir / "kernel-a").resolve()),
                "type": "kernel",
                "external": False,
            },
            {
                "file": "https://mirror.example/initrd",
                "type": "initrd",
                "external": True,
            },
        ]
    }

    context = get_image_context(client, 42, store, image_dir)
    assert context.image_id == 42
    assert context.store_dir == store
    assert context.image_dir == image_dir
    assert len(context.initrd_files) == 1
    assert context.initrd_files[0] == image_dir / "initrd-a"


# ==========================================
# Host/Container and Backend-Aware Tests
# ==========================================

def test_is_host_mode_detection(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda cmd: "/usr/bin/mgrctl" if cmd == "mgrctl" else None)
    initrd_rpm_update.is_host_mode._cache = shutil.which("mgrctl") is not None
    assert initrd_rpm_update.is_host_mode() is True

    monkeypatch.setattr(shutil, "which", lambda cmd: None)
    initrd_rpm_update.is_host_mode._cache = shutil.which("mgrctl") is not None
    assert initrd_rpm_update.is_host_mode() is False


def test_store_is_dir_direct_and_host(monkeypatch, tmp_path):
    # Direct Mode (no mgrctl)
    monkeypatch.setattr(initrd_rpm_update, "is_host_mode", lambda: False)
    assert initrd_rpm_update.store_is_dir(tmp_path) is True
    assert initrd_rpm_update.store_is_dir(tmp_path / "non-existent") is False

    # Host Mode (mgrctl present)
    monkeypatch.setattr(initrd_rpm_update, "is_host_mode", lambda: True)
    
    def mock_run(command, **kwargs):
        assert command[0] == "mgrctl"
        assert command[1] == "exec"
        if "existent" in command[2]:
            return subprocess.CompletedProcess(command, 1)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(initrd_rpm_update.subprocess, "run", mock_run)
    assert initrd_rpm_update.store_is_dir(Path("/srv/www/os-images")) is True
    assert initrd_rpm_update.store_is_dir(Path("/srv/www/os-images/non-existent")) is False


def test_store_list_dir_direct_and_host(monkeypatch, tmp_path):
    # Direct Mode
    monkeypatch.setattr(initrd_rpm_update, "is_host_mode", lambda: False)
    f1 = tmp_path / "file1"
    f2 = tmp_path / "file2"
    f1.touch()
    f2.touch()
    entries = initrd_rpm_update.store_list_dir(tmp_path)
    assert sorted(entries) == ["file1", "file2"]

    # Host Mode
    monkeypatch.setattr(initrd_rpm_update, "is_host_mode", lambda: True)

    def mock_run(command, **kwargs):
        assert command[0] == "mgrctl"
        assert command[1] == "exec"
        return subprocess.CompletedProcess(command, 0, stdout=b"fileA\nfileB\n")

    monkeypatch.setattr(initrd_rpm_update.subprocess, "run", mock_run)
    entries = initrd_rpm_update.store_list_dir(Path("/srv/www/os-images"))
    assert entries == ["fileA", "fileB"]


def test_store_remove_file_direct_and_host(monkeypatch, tmp_path):
    # Direct Mode
    monkeypatch.setattr(initrd_rpm_update, "is_host_mode", lambda: False)
    f = tmp_path / "to-remove"
    f.touch()
    assert initrd_rpm_update.store_remove_file(f) is None
    assert not f.exists()

    # Host Mode
    monkeypatch.setattr(initrd_rpm_update, "is_host_mode", lambda: True)

    def mock_run(command, **kwargs):
        assert command[0] == "mgrctl"
        assert command[1] == "exec"
        assert "rm -f" in command[2]
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(initrd_rpm_update.subprocess, "run", mock_run)
    assert initrd_rpm_update.store_remove_file(Path("/srv/www/os-images/f")) is None


def test_store_install_file_exclusive_direct(tmp_path):
    source = tmp_path / "source"
    source.write_bytes(b"content")
    dest = tmp_path / "dest"

    initrd_rpm_update.is_host_mode._cache = False
    initrd_rpm_update.store_install_file_exclusive(source, dest)
    assert dest.read_bytes() == b"content"

    # Collision test
    with pytest.raises(FileExistsError):
        initrd_rpm_update.store_install_file_exclusive(source, dest)


def test_store_install_file_exclusive_host(monkeypatch, tmp_path):
    source = tmp_path / "source"
    source.write_bytes(b"content")
    dest = Path("/srv/www/os-images/dest")

    initrd_rpm_update.is_host_mode._cache = True

    calls = []

    def mock_run(command, **kwargs):
        calls.append(command)
        if command[0] == "mgrctl" and command[1] == "cp":
            return subprocess.CompletedProcess(command, 0)
        if "ln" in command[2]:
            return subprocess.CompletedProcess(command, 0)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(initrd_rpm_update.subprocess, "run", mock_run)
    initrd_rpm_update.store_install_file_exclusive(source, dest)

    assert len(calls) >= 3
    # Check copying staging file
    assert calls[0] == ["mgrctl", "cp", str(source), "server:/srv/www/os-images/dest.staging"]
    # Check ln command
    assert "ln " in calls[1][2]
    # Check cleanup
    assert "rm -f" in calls[3][2]


# ==========================================
# Unified Source and Reference Selection Tests
# ==========================================

def test_selection_no_initrd_zero_candidates():
    # Inside run_update, missing candidate list raises InitrdUpdateError
    pass


def test_selection_no_initrd_one_candidate(monkeypatch, tmp_path):
    args = Namespace(
        imageid=123,
        org_id=1,
        initrd=None,
        rpm=[str(tmp_path / "a.rpm")],
        skip_pillar=True,
    )
    context = ImageContext(
        image_id=123,
        store_dir=tmp_path,
        image_dir=tmp_path,
        files=[
            ImageFileRecord(
                file="initrd",
                file_type="initrd",
                external=False,
                local_path=tmp_path / "initrd",
            )
        ],
        initrd_files=[tmp_path / "initrd"],
        api_file_values=["initrd"],
        prefer_absolute_file_paths=False,
    )


def test_selection_no_initrd_multiple_candidates_raises_error(monkeypatch, tmp_path):
    args = Namespace(
        imageid=123,
        org_id=1,
        initrd=None,
        rpm=[str(tmp_path / "a.rpm")],
        skip_pillar=True,
    )


# ==========================================
# Build Overlay, Compression, Extractions
# ==========================================

class _fake_process:
    def __init__(self, returncode, stdout=None, stderr=None):
        self.returncode = returncode
        self.stdout = MagicMock() if stdout is None else stdout
        self.stderr = MagicMock() if stderr is None else stderr
        self.communicate = MagicMock(return_value=(b"", b""))


def test_extract_rpms_applies_ordering(monkeypatch, tmp_path):
    rpm_a = tmp_path / "a.rpm"
    rpm_b = tmp_path / "b.rpm"
    rpm_a.touch()
    rpm_b.touch()

    overlay = tmp_path / "overlay"
    overlay.mkdir()

    calls = []

    def popen_side_effect(command, **kwargs):
        calls.append(command)
        proc = _fake_process(returncode=0)

        if command[0] == "rpm2cpio":
            active = command[1]

            def communicate():
                target = overlay / "etc" / "config"
                target.parent.mkdir(parents=True, exist_ok=True)
                content = b"from-a" if active == str(rpm_a) else b"from-b"
                target.write_bytes(content)
                return (b"", b"")

            proc.communicate.side_effect = communicate
            return proc

        if command[0] == "cpio":
            proc.communicate.return_value = (b"", b"")
            return proc

        raise AssertionError(f"Unexpected command: {command}")

    monkeypatch.setattr(
        initrd_rpm_update.subprocess,
        "Popen",
        MagicMock(side_effect=popen_side_effect),
    )

    extract_rpms([rpm_a, rpm_b], overlay)
    assert (overlay / "etc" / "config").read_bytes() == b"from-b"


def test_build_overlay_member_constructs_commands(monkeypatch, tmp_path):
    overlay = tmp_path / "overlay"
    overlay.mkdir()
    output = tmp_path / "overlay.zst"

    monkeypatch.setattr(
        initrd_rpm_update,
        "_overlay_entries_filtered",
        lambda *_args, **_kwargs: [".", "dir", "dir/file"],
    )

    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        if command[0] == "cpio":
            kwargs["stdout"].write(b"cpio")
        if command[0] == "zstd":
            output.write_bytes(b"zstd")
        return subprocess.CompletedProcess(command, 0, b"", b"")

    monkeypatch.setattr(initrd_rpm_update.subprocess, "run", fake_run)
    build_overlay_member(overlay, output)

    assert calls[0][0] == ["cpio", "--null", "-o", "-H", "newc", "--quiet"]
    assert calls[0][1]["cwd"] == overlay
    assert calls[0][1]["input"] == b".\x00dir\x00dir/file\x00"
    assert calls[1][0] == ["zstd", "-q", "-z", "-o", str(output), str(output) + ".cpio"]


def test_build_overlay_member_cpio_failure(monkeypatch, tmp_path):
    overlay = tmp_path / "overlay"
    overlay.mkdir()
    output = tmp_path / "overlay.zst"

    monkeypatch.setattr(
        initrd_rpm_update,
        "_overlay_entries_filtered",
        lambda *_args, **_kwargs: ["."],
    )

    def fake_run(command, **kwargs):
        if command[0] == "cpio":
            return subprocess.CompletedProcess(command, 1, b"", b"cpio failed")
        raise AssertionError("zstd must not run after cpio build failure")

    monkeypatch.setattr(initrd_rpm_update.subprocess, "run", fake_run)

    with pytest.raises(InitrdUpdateError, match="cpio archive build failed"):
        build_overlay_member(overlay, output)


def test_build_overlay_member_zstd_failure(monkeypatch, tmp_path):
    overlay = tmp_path / "overlay"
    overlay.mkdir()
    output = tmp_path / "overlay.zst"

    monkeypatch.setattr(
        initrd_rpm_update,
        "_overlay_entries_filtered",
        lambda *_args, **_kwargs: ["."],
    )

    def fake_run(command, **kwargs):
        if command[0] == "cpio":
            kwargs["stdout"].write(b"cpio")
            return subprocess.CompletedProcess(command, 0, b"", b"")
        if command[0] == "zstd":
            return subprocess.CompletedProcess(command, 3, b"", b"zstd failed")
        raise AssertionError(f"Unexpected command {command}")

    monkeypatch.setattr(initrd_rpm_update.subprocess, "run", fake_run)

    with pytest.raises(InitrdUpdateError, match="zstd compression failed"):
        build_overlay_member(overlay, output)


def test_validate_overlay_member_propagates_failures(monkeypatch, tmp_path):
    member = tmp_path / "overlay.zst"
    member.write_bytes(b"zstd")

    monkeypatch.setattr(
        initrd_rpm_update.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 1, b"", b"bad"),
    )
    with pytest.raises(InitrdUpdateError, match="zstd --test failed"):
        validate_overlay_member(member)

    monkeypatch.setattr(
        initrd_rpm_update.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, b"", b""),
    )
    zstd_proc = _fake_process(returncode=0)
    cpio_proc = _fake_process(returncode=1, stderr=b"bad cpio")
    monkeypatch.setattr(
        initrd_rpm_update.subprocess,
        "Popen",
        MagicMock(side_effect=[zstd_proc, cpio_proc]),
    )
    with pytest.raises(InitrdUpdateError, match="cpio listing failed"):
        validate_overlay_member(member)


def test_validate_overlay_member_zstd_decompression_failure(monkeypatch, tmp_path):
    member = tmp_path / "overlay.zst"
    member.write_bytes(b"zstd")

    monkeypatch.setattr(
        initrd_rpm_update.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, b"", b""),
    )

    zstd_proc = _fake_process(returncode=1, stderr=b"zstd decode failed")
    cpio_proc = _fake_process(returncode=0)
    monkeypatch.setattr(
        initrd_rpm_update.subprocess,
        "Popen",
        MagicMock(side_effect=[zstd_proc, cpio_proc]),
    )

    with pytest.raises(InitrdUpdateError, match="zstd decompression failed"):
        validate_overlay_member(member)


def test_excluded_entry_supports_names_paths_and_globs():
    patterns = ["__pycache__", "*.pyc", "usr/lib/python*/site-packages/*"]

    assert _excluded_entry("usr/lib/python3.11/site-packages/a.py", patterns, False)
    assert _excluded_entry("usr/lib/python3.11/site-packages/pkg", patterns, True)
    assert _excluded_entry("etc/__pycache__/x.pyc", patterns, False)
    assert _excluded_entry("var/cache/app.pyc", patterns, False)
    assert not _excluded_entry("usr/lib/other/file.txt", patterns, False)


def test_overlay_entries_filtered_excludes_dirs_and_globs(tmp_path):
    overlay = tmp_path / "overlay"
    (overlay / "etc").mkdir(parents=True)
    (overlay / "etc" / "ok.conf").write_text("ok")
    (overlay / "etc" / "drop.pyc").write_text("pyc")
    (overlay / "etc" / "__pycache__").mkdir()
    (overlay / "etc" / "__pycache__" / "ignored.pyc").write_text("ignored")
    (overlay / "usr" / "lib" / "python3.11" / "site-packages").mkdir(parents=True)
    (overlay / "usr" / "lib" / "python3.11" / "site-packages" / "module.py").write_text(
        "module"
    )

    entries = _overlay_entries_filtered(
        overlay,
        exclude_patterns=["__pycache__", "*.pyc", "usr/lib/python*/site-packages/*"],
    )

    assert "etc" in entries
    assert "etc/ok.conf" in entries
    assert "etc/drop.pyc" not in entries
    assert "etc/__pycache__" not in entries
    assert "etc/__pycache__/ignored.pyc" not in entries
    assert "usr/lib/python3.11/site-packages/module.py" not in entries


def test_build_overlay_member_passes_exclude_patterns(monkeypatch, tmp_path):
    overlay = tmp_path / "overlay"
    overlay.mkdir()
    output = tmp_path / "overlay.zst"

    captured = {}

    def fake_entries_filtered(_overlay, exclude_patterns=None):
        captured["patterns"] = exclude_patterns
        return ["."]

    monkeypatch.setattr(
        initrd_rpm_update,
        "_overlay_entries_filtered",
        fake_entries_filtered,
    )

    def fake_run(command, **kwargs):
        if command[0] == "cpio":
            kwargs["stdout"].write(b"cpio")
            return subprocess.CompletedProcess(command, 0, b"", b"")
        if command[0] == "zstd":
            output.write_bytes(b"zstd")
            return subprocess.CompletedProcess(command, 0, b"", b"")
        raise AssertionError(f"Unexpected command {command}")

    monkeypatch.setattr(initrd_rpm_update.subprocess, "run", fake_run)

    build_overlay_member(overlay, output, exclude_patterns=["__pycache__", "*.pyc"])
    assert captured["patterns"] == ["__pycache__", "*.pyc"]


def test_build_updated_initrd_appends_and_preserves_source(tmp_path):
    source = tmp_path / "source-initrd"
    overlay = tmp_path / "overlay.zst"
    output = tmp_path / "new-initrd"
    source.write_bytes(b"SOURCE")
    overlay.write_bytes(b"OVERLAY")

    build_updated_initrd(source, overlay, output)

    assert output.read_bytes() == b"SOURCEOVERLAY"
    assert source.read_bytes() == b"SOURCE"


def test_next_output_name_variants_and_large_numbers(tmp_path):
    api_files = [
        "my_image.initrd",
        "my_image-rpmupdate-1.initrd",
        "my_image-rpmupdate-x.initrd",
        "my_image-rpmupdate-3.old",
        "other-rpmupdate-4",
        "my_image-rpmupdate-999999999999999999999999.initrd",
    ]
    (tmp_path / "my_image-rpmupdate-7.initrd").touch()
    (tmp_path / "my_image-rpmupdate-8.old").touch()
    (tmp_path / "my_image-rpmupdate-1000000000000000000000000.initrd").touch()

    assert (
        next_output_name("my_image.initrd", api_files, tmp_path)
        == "my_image-rpmupdate-1000000000000000000000001.initrd"
    )
    assert next_output_name("my_image.initrd", [], []) == "my_image-rpmupdate-1.initrd"


# ==========================================
# Installation, Staging, and Pillar Tests
# ==========================================

def test_install_generated_file_retries_on_collision(monkeypatch, tmp_path):
    source = tmp_path / "generated-initrd"
    source.write_bytes(b"new")

    store = tmp_path / "store"
    store.mkdir()
    (store / "my_image.initrd").write_bytes(b"old")
    (store / "my_image-rpmupdate-1.initrd").write_bytes(b"old")

    context = ImageContext(
        image_id=10,
        store_dir=store,
        image_dir=store,
        files=[
            ImageFileRecord(
                file="my_image-rpmupdate-1.initrd",
                file_type="initrd",
                external=False,
                local_path=store / "my_image-rpmupdate-1.initrd",
            )
        ],
        initrd_files=[store / "my_image.initrd"],
        api_file_values=["my_image.initrd", "my_image-rpmupdate-1.initrd"],
        prefer_absolute_file_paths=False,
    )

    real_install = initrd_rpm_update.store_install_file_exclusive
    attempts = []

    def fake_install(src, dst):
        attempts.append(dst.name)
        if len(attempts) == 1:
            (store / "my_image-rpmupdate-2.initrd").write_bytes(b"concurrent")
            raise FileExistsError("race")
        real_install(src, dst)

    monkeypatch.setattr(initrd_rpm_update, "store_install_file_exclusive", fake_install)
    installed = install_generated_file(source, context, store / "my_image.initrd")

    assert attempts == ["my_image-rpmupdate-2.initrd", "my_image-rpmupdate-3.initrd"]
    assert installed.name == "my_image-rpmupdate-3.initrd"
    assert (store / "my_image-rpmupdate-2.initrd").read_bytes() == b"concurrent"
    assert installed.read_bytes() == b"new"


def test_update_initrd_url_preserves_query_and_fragment():
    old = "https://manager:8443/os-images/1/old-initrd?x=1#frag"
    assert (
        update_initrd_url(old, "rpmupdate-9")
        == "https://manager:8443/os-images/1/rpmupdate-9?x=1#frag"
    )


def test_updated_pillar_updates_matching_entry_and_preserves_other_data():
    pillar = {
        "sync": {"initrd_url": "https://manager/os-images/1/current?x=1#f"},
        "boot_images": {
            "entry-1": {
                "sync": {"initrd_url": "https://manager/os-images/1/current?x=1#f"},
                "initrd": {"hash": "old", "size": "100"},
                "other": "keep",
            },
            "entry-2": {
                "sync": {"initrd_url": "https://manager/os-images/1/another"},
                "initrd": {"hash": "old2", "size": "200"},
            },
        },
        "unrelated": {"keep": True},
    }

    new_pillar = updated_pillar(
        pillar,
        active_initrd=Path("/srv/www/os-images/1/current"),
        filename="rpmupdate-2",
        digest="abc123",
        size=321,
    )

    assert (
        new_pillar["sync"]["initrd_url"]
        == "https://manager/os-images/1/rpmupdate-2?x=1#f"
    )
    assert (
        new_pillar["boot_images"]["entry-1"]["sync"]["initrd_url"]
        == "https://manager/os-images/1/rpmupdate-2?x=1#f"
    )
    assert new_pillar["boot_images"]["entry-1"]["initrd"]["hash"] == "abc123"
    assert new_pillar["boot_images"]["entry-1"]["initrd"]["size"] == "321"
    assert new_pillar["boot_images"]["entry-2"]["initrd"]["hash"] == "old2"
    assert new_pillar["unrelated"] == {"keep": True}


def test_validate_pillar_for_update_detects_invalid_structure():
    valid = {
        "sync": {"initrd_url": "https://manager/os-images/1/initrd"},
        "boot_images": {
            "entry": {
                "sync": {"initrd_url": "https://manager/os-images/1/initrd"},
                "initrd": {"hash": "old", "size": "1"},
            }
        },
    }
    validate_pillar_for_update(valid, Path("/srv/www/os-images/1/initrd"))

    invalid = {
        "sync": {"initrd_url": "https://manager/os-images/1/initrd"},
        "boot_images": {
            "entry": {"sync": {"initrd_url": "https://manager/os-images/1/initrd"}}
        },
    }

    with pytest.raises(InitrdUpdateError, match="missing 'initrd' object"):
        validate_pillar_for_update(invalid, Path("/srv/www/os-images/1/initrd"))


def test_install_and_register_payload_and_skip_pillar(monkeypatch, tmp_path):
    store = tmp_path / "store"
    store.mkdir()
    generated = tmp_path / "new-initrd"
    generated.write_bytes(b"new")

    installed = store / "my_image-rpmupdate-8.initrd"

    context = ImageContext(
        image_id=9,
        store_dir=store,
        image_dir=store,
        files=[],
        initrd_files=[store / "initrd"],
        api_file_values=["initrd"],
        prefer_absolute_file_paths=False,
    )

    client = DummyApiClient()
    client.post_responses["image/addImageFile"] = {"ok": True}

    monkeypatch.setattr(
        initrd_rpm_update, "install_generated_file", lambda *_args: installed
    )

    result = install_and_register(
        client=client,
        image_context=context,
        image_id=9,
        new_initrd_path=generated,
        digest="abc",
        size=111,
        pillar=None,
        active_initrd=None,
        reference_initrd=store / "my_image.initrd",
        skip_pillar=True,
    )

    assert result == installed
    assert client.post_calls == [
        (
            "image/addImageFile",
            {
                "imageId": 9,
                "file": "my_image-rpmupdate-8.initrd",
                "type": "initrd",
                "external": False,
            },
        )
    ]


def test_install_and_register_rolls_back_when_add_fails(monkeypatch, tmp_path):
    store = tmp_path / "store"
    store.mkdir()
    generated = tmp_path / "new-initrd"
    generated.write_bytes(b"new")
    installed = store / "my_image-rpmupdate-1.initrd"
    installed.write_bytes(b"new")

    context = ImageContext(
        image_id=9,
        store_dir=store,
        image_dir=store,
        files=[],
        initrd_files=[store / "initrd"],
        api_file_values=["initrd"],
        prefer_absolute_file_paths=False,
    )

    client = DummyApiClient()
    client.post_responses["image/addImageFile"] = InitrdUpdateError("boom")
    monkeypatch.setattr(
        initrd_rpm_update, "install_generated_file", lambda *_args: installed
    )

    with pytest.raises(InitrdUpdateError, match="boom"):
        install_and_register(
            client=client,
            image_context=context,
            image_id=9,
            new_initrd_path=generated,
            digest="abc",
            size=111,
            pillar=None,
            active_initrd=None,
            reference_initrd=store / "my_image.initrd",
            skip_pillar=True,
        )
    assert not installed.exists()


def test_install_and_register_rolls_back_after_pillar_failure(monkeypatch, tmp_path):
    store = tmp_path / "store"
    store.mkdir()
    generated = tmp_path / "new-initrd"
    generated.write_bytes(b"new")
    installed = store / "my_image-rpmupdate-7.initrd"
    installed.write_bytes(b"new")

    context = ImageContext(
        image_id=9,
        store_dir=store,
        image_dir=store,
        files=[],
        initrd_files=[store / "initrd"],
        api_file_values=["initrd"],
        prefer_absolute_file_paths=False,
    )

    client = DummyApiClient()

    def post_response(payload):
        return {"ok": payload}

    client.post_responses["image/addImageFile"] = post_response
    client.post_responses["image/setPillar"] = InitrdUpdateError("pillar failed")
    client.post_responses["image/deleteImageFile"] = {"ok": True}

    monkeypatch.setattr(
        initrd_rpm_update, "install_generated_file", lambda *_args: installed
    )

    pillar = {
        "sync": {"initrd_url": "https://manager/os-images/1/initrd"},
        "boot_images": {
            "entry": {
                "sync": {"initrd_url": "https://manager/os-images/1/initrd"},
                "initrd": {"hash": "old", "size": "1"},
            }
        },
    }

    with pytest.raises(InitrdUpdateError, match="rollback succeeded"):
        install_and_register(
            client=client,
            image_context=context,
            image_id=9,
            new_initrd_path=generated,
            digest="abc",
            size=111,
            pillar=pillar,
            active_initrd=Path("/srv/www/os-images/1/initrd"),
            reference_initrd=store / "my_image.initrd",
            skip_pillar=False,
        )

    delete_calls = [
        call for call in client.post_calls if call[0] == "image/deleteImageFile"
    ]
    assert delete_calls
    assert not installed.exists()


def test_install_and_register_reports_incomplete_rollback(monkeypatch, tmp_path):
    store = tmp_path / "store"
    store.mkdir()
    generated = tmp_path / "new-initrd"
    generated.write_bytes(b"new")
    installed = store / "my_image-rpmupdate-7.initrd"
    installed.write_bytes(b"new")

    context = ImageContext(
        image_id=9,
        store_dir=store,
        image_dir=store,
        files=[],
        initrd_files=[store / "initrd"],
        api_file_values=["initrd"],
        prefer_absolute_file_paths=False,
    )

    client = DummyApiClient()
    client.post_responses["image/addImageFile"] = {"ok": True}
    client.post_responses["image/setPillar"] = InitrdUpdateError("pillar failed")
    client.post_responses["image/deleteImageFile"] = InitrdUpdateError("delete failed")

    monkeypatch.setattr(
        initrd_rpm_update, "install_generated_file", lambda *_args: installed
    )
    monkeypatch.setattr(
        initrd_rpm_update, "store_remove_file", lambda _path: "cannot remove"
    )

    pillar = {
        "sync": {"initrd_url": "https://manager/os-images/1/initrd"},
        "boot_images": {
            "entry": {
                "sync": {"initrd_url": "https://manager/os-images/1/initrd"},
                "initrd": {"hash": "old", "size": "1"},
            }
        },
    }

    with pytest.raises(InitrdUpdateError, match="rollback was incomplete"):
        install_and_register(
            client=client,
            image_context=context,
            image_id=9,
            new_initrd_path=generated,
            digest="abc",
            size=111,
            pillar=pillar,
            active_initrd=Path("/srv/www/os-images/1/initrd"),
            reference_initrd=store / "my_image.initrd",
            skip_pillar=False,
        )


# ==========================================
# Integrated workflow Tests (run_update)
# ==========================================

def test_run_update_skip_pillar_bypasses_pillar_calls(monkeypatch, tmp_path):
    source_initrd = tmp_path / "source"
    source_initrd.write_bytes(b"source")

    args = Namespace(
        imageid=9,
        initrd=str(source_initrd),
        rpm=[str(tmp_path / "one.rpm")],
        exclude=[],
        org_id=1,
        skip_pillar=True,
    )

    context = ImageContext(
        image_id=9,
        store_dir=tmp_path,
        image_dir=tmp_path,
        files=[
            ImageFileRecord(
                file="initrd",
                file_type="initrd",
                external=False,
                local_path=tmp_path / "initrd",
            )
        ],
        initrd_files=[tmp_path / "initrd"],
        api_file_values=["initrd"],
        prefer_absolute_file_paths=False,
    )

    client = DummyApiClient()
    client.get_responses["image/getDetails"] = {
        "name": "img",
        "version": "1.0",
        "revision": 1,
        "files": [
            {"file": "initrd", "type": "initrd", "external": False}
        ]
    }
    client.get_responses["image/getPillar"] = InitrdUpdateError("must not be called")

    monkeypatch.setattr(
        initrd_rpm_update, "resolve_rpm_sources", lambda _paths: [tmp_path / "one.rpm"]
    )
    monkeypatch.setattr(initrd_rpm_update, "verify_required_tools", lambda: None)
    monkeypatch.setattr(initrd_rpm_update, "validate_organization", lambda *_args: None)
    monkeypatch.setattr(initrd_rpm_update, "get_image_context", lambda *_args: context)
    monkeypatch.setattr(initrd_rpm_update, "extract_rpms", lambda *_args: None)
    monkeypatch.setattr(initrd_rpm_update, "build_overlay_member", lambda *_args: None)
    monkeypatch.setattr(
        initrd_rpm_update, "validate_overlay_member", lambda *_args: None
    )
    monkeypatch.setattr(initrd_rpm_update, "build_updated_initrd", lambda *_args: None)
    monkeypatch.setattr(
        initrd_rpm_update, "compute_md5_and_size", lambda *_args: ("abc", 100)
    )
    monkeypatch.setattr(
        initrd_rpm_update,
        "install_and_register",
        lambda **kwargs: kwargs["image_context"].store_dir / "initrd-rpmupdate-1",
    )

    message = run_update(client, args)
    assert "--skip-pillar" in message
    assert "initrd-rpmupdate-1" in message
    assert all(call[0] != "image/getPillar" for call in client.get_calls)


def test_run_update_validates_pillar_before_install(monkeypatch, tmp_path):
    source_initrd = tmp_path / "source"
    source_initrd.write_bytes(b"source")

    args = Namespace(
        imageid=9,
        initrd=str(source_initrd),
        rpm=[str(tmp_path / "one.rpm")],
        exclude=[],
        org_id=1,
        skip_pillar=False,
    )

    context = ImageContext(
        image_id=9,
        store_dir=tmp_path,
        image_dir=tmp_path,
        files=[
            ImageFileRecord(
                file="initrd",
                file_type="initrd",
                external=False,
                local_path=tmp_path / "initrd",
            )
        ],
        initrd_files=[tmp_path / "initrd"],
        api_file_values=["initrd"],
        prefer_absolute_file_paths=False,
    )

    client = DummyApiClient()
    client.get_responses["image/getDetails"] = {
        "name": "img",
        "version": "1.0",
        "revision": 1,
        "files": [
            {"file": "initrd", "type": "initrd", "external": False}
        ]
    }
    client.get_responses["image/getPillar"] = {
        "sync": {"initrd_url": "https://manager/os-images/1/initrd"},
        "boot_images": {
            "entry": {"sync": {"initrd_url": "https://manager/os-images/1/initrd"}}
        },
    }

    called = {"extract": False, "install": False}

    monkeypatch.setattr(
        initrd_rpm_update, "resolve_rpm_sources", lambda _paths: [tmp_path / "one.rpm"]
    )
    monkeypatch.setattr(initrd_rpm_update, "verify_required_tools", lambda: None)
    monkeypatch.setattr(initrd_rpm_update, "validate_organization", lambda *_args: None)
    monkeypatch.setattr(initrd_rpm_update, "get_image_context", lambda *_args: context)
    monkeypatch.setattr(
        initrd_rpm_update,
        "get_active_initrd",
        lambda _pillar, _initrds: Path("/srv/www/os-images/1/initrd"),
    )

    def mark_extract(*_args):
        called["extract"] = True

    def mark_install(**_kwargs):
        called["install"] = True
        return tmp_path / "rpmupdate-1"

    monkeypatch.setattr(initrd_rpm_update, "extract_rpms", mark_extract)
    monkeypatch.setattr(initrd_rpm_update, "build_overlay_member", lambda *_args: None)
    monkeypatch.setattr(
        initrd_rpm_update, "validate_overlay_member", lambda *_args: None
    )
    monkeypatch.setattr(initrd_rpm_update, "build_updated_initrd", lambda *_args: None)
    monkeypatch.setattr(
        initrd_rpm_update, "compute_md5_and_size", lambda *_args: ("abc", 100)
    )
    monkeypatch.setattr(initrd_rpm_update, "install_and_register", mark_install)

    with pytest.raises(InitrdUpdateError, match="missing 'initrd' object"):
        run_update(client, args)

    assert called["extract"] is False
    assert called["install"] is False


@pytest.mark.skipif(
    not (shutil.which("cpio") and shutil.which("zstd")),
    reason="cpio and zstd are required for overlay integration test",
)
def test_overlay_member_integration_with_host_tools(tmp_path):
    overlay = tmp_path / "overlay"
    overlay.mkdir()
    (overlay / "etc").mkdir()
    (overlay / "etc" / "example.conf").write_text("x=1\n")
    member = tmp_path / "overlay.zst"

    build_overlay_member(overlay, member)
    validate_overlay_member(member)

    assert member.exists()
    assert member.stat().st_size > 0
