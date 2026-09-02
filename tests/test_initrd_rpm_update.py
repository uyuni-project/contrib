import importlib.util
import shutil
import subprocess
import sys
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
install_and_register = initrd_rpm_update.install_and_register
install_generated_file = initrd_rpm_update.install_generated_file
next_output_name = initrd_rpm_update.next_output_name
_install_file_exclusive = initrd_rpm_update._install_file_exclusive
parse_args = initrd_rpm_update.parse_args
resolve_rpm_sources = initrd_rpm_update.resolve_rpm_sources
run_update = initrd_rpm_update.run_update
select_image = initrd_rpm_update.select_image
update_initrd_url = initrd_rpm_update.update_initrd_url
updated_pillar = initrd_rpm_update.updated_pillar
validate_pillar_for_update = initrd_rpm_update.validate_pillar_for_update
validate_organization = initrd_rpm_update.validate_organization
validate_overlay_member = initrd_rpm_update.validate_overlay_member


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


def test_parse_args_org_default_and_type():
    args = parse_args(
        [
            "--host",
            "manager.example.test",
            "--initrd",
            "/tmp/source-initrd",
            "--rpm",
            "/tmp/a.rpm",
            "name",
            "1.0",
            "2",
        ]
    )
    assert args.org_id == 1
    assert isinstance(args.org_id, int)


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


def test_validate_organization_passes_integer():
    client = DummyApiClient()
    client.get_responses["org/getDetails"] = {}

    validate_organization(client, 7)

    assert client.get_calls == [("org/getDetails", {"orgId": 7})]


def test_select_image_exact_match():
    client = DummyApiClient()
    client.get_responses["image/listImages"] = [
        {"id": 11, "name": "img", "version": "1", "revision": 2},
        {"id": 12, "name": "img", "version": "1", "revision": 3},
    ]

    assert select_image(client, "img", "1", 3) == 12


def test_select_image_rejects_zero_or_multiple():
    client = DummyApiClient()
    client.get_responses["image/listImages"] = []
    with pytest.raises(InitrdUpdateError, match="No image found"):
        select_image(client, "img", "1", 1)

    client.get_responses["image/listImages"] = [
        {"id": 10, "name": "img", "version": "1", "revision": 1},
        {"id": 20, "name": "img", "version": "1", "revision": 1},
    ]
    with pytest.raises(InitrdUpdateError, match="Multiple images found"):
        select_image(client, "img", "1", 1)


def test_get_image_context_validates_store_boundaries(tmp_path):
    store = tmp_path / "store"
    store.mkdir()

    client = DummyApiClient()
    client.get_responses["image/getDetails"] = {
        "files": [
            {"file": "initrd-a", "type": "initrd", "external": False},
            {
                "file": str((store / "kernel-a").resolve()),
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

    context = get_image_context(client, 42, store)
    assert context.image_id == 42
    assert context.store_dir == store
    assert len(context.initrd_files) == 2
    assert any(path.name == "initrd-a" for path in context.initrd_files)


def test_get_image_context_rejects_traversal(tmp_path):
    store = tmp_path / "store"
    store.mkdir()

    client = DummyApiClient()
    client.get_responses["image/getDetails"] = {
        "files": [{"file": "../../../etc/passwd", "type": "initrd", "external": False}]
    }

    with pytest.raises(InitrdUpdateError, match="escapes organization store directory"):
        get_image_context(client, 42, store)


def test_get_active_initrd_correlation_and_failures():
    files = [
        Path("/srv/www/os-images/1/initrd-A"),
        Path("/srv/www/os-images/1/initrd-B"),
    ]
    pillar = {"sync": {"initrd_url": "https://manager/os-images/1/initrd-B"}}
    assert get_active_initrd(pillar, files) == files[1]

    missing = {"sync": {"initrd_url": "https://manager/os-images/1/missing"}}
    with pytest.raises(InitrdUpdateError, match="Unable to correlate"):
        get_active_initrd(missing, files)

    ambiguous_files = [Path("/a/initrd-X"), Path("/b/initrd-X")]
    ambiguous = {"sync": {"initrd_url": "https://manager/os-images/1/initrd-X"}}
    with pytest.raises(InitrdUpdateError, match="matches multiple"):
        get_active_initrd(ambiguous, ambiguous_files)


def test_resolve_rpm_sources_ordering_and_sorting(tmp_path):
    rpm1 = tmp_path / "00-first.rpm"
    rpm1.write_bytes(b"1")
    rpm2 = tmp_path / "99-second.rpm"
    rpm2.write_bytes(b"2")

    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "b.rpm").write_bytes(b"b")
    (source_dir / "a.rpm").write_bytes(b"a")
    (source_dir / "note.txt").write_text("ignore")

    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()

    resolved = resolve_rpm_sources([rpm1, source_dir, empty_dir, rpm2])
    assert resolved == [
        rpm1.resolve(),
        (source_dir / "a.rpm").resolve(),
        (source_dir / "b.rpm").resolve(),
        rpm2.resolve(),
    ]


def test_resolve_rpm_sources_invalid_and_empty(tmp_path):
    invalid_file = tmp_path / "not-rpm.txt"
    invalid_file.write_text("x")
    with pytest.raises(InitrdUpdateError, match=r"must end with \.rpm"):
        resolve_rpm_sources([invalid_file])

    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    with pytest.raises(InitrdUpdateError, match="No RPM files found"):
        resolve_rpm_sources([empty_dir])

    with pytest.raises(InitrdUpdateError, match="does not exist"):
        resolve_rpm_sources([tmp_path / "missing.rpm"])


def _fake_process(returncode=0, stderr=b""):
    proc = MagicMock()
    proc.returncode = returncode
    proc.stderr = MagicMock()
    proc.stdout = MagicMock()
    proc.communicate.return_value = (b"", stderr)
    return proc


def test_extract_rpms_success_and_command_arguments(monkeypatch, tmp_path):
    rpm = tmp_path / "x.rpm"
    rpm.write_bytes(b"x")
    overlay = tmp_path / "overlay"
    overlay.mkdir()

    rpm2cpio_proc = _fake_process(returncode=0)
    cpio_proc = _fake_process(returncode=0)
    popen = MagicMock(side_effect=[rpm2cpio_proc, cpio_proc])
    monkeypatch.setattr(initrd_rpm_update.subprocess, "Popen", popen)

    extract_rpms([rpm], overlay)

    popen.assert_any_call(
        ["rpm2cpio", str(rpm)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    popen.assert_any_call(
        ["cpio", "-idm", "--unconditional", "--quiet"],
        stdin=rpm2cpio_proc.stdout,
        cwd=overlay,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def test_extract_rpms_propagates_pipeline_failures(monkeypatch, tmp_path):
    rpm = tmp_path / "x.rpm"
    rpm.write_bytes(b"x")
    overlay = tmp_path / "overlay"
    overlay.mkdir()

    popen = MagicMock(
        side_effect=[
            _fake_process(returncode=1, stderr=b"rpm fail"),
            _fake_process(returncode=0),
        ]
    )
    monkeypatch.setattr(initrd_rpm_update.subprocess, "Popen", popen)
    with pytest.raises(InitrdUpdateError, match="rpm2cpio failed"):
        extract_rpms([rpm], overlay)

    popen = MagicMock(
        side_effect=[
            _fake_process(returncode=0),
            _fake_process(returncode=2, stderr=b"cpio fail"),
        ]
    )
    monkeypatch.setattr(initrd_rpm_update.subprocess, "Popen", popen)
    with pytest.raises(InitrdUpdateError, match="cpio extraction failed"):
        extract_rpms([rpm], overlay)


def test_extract_rpms_later_rpm_overwrites_earlier(monkeypatch, tmp_path):
    overlay = tmp_path / "overlay"
    overlay.mkdir()
    rpm_a = tmp_path / "a.rpm"
    rpm_b = tmp_path / "b.rpm"
    rpm_a.write_bytes(b"a")
    rpm_b.write_bytes(b"b")

    state = {"active_rpm": None}

    def popen_side_effect(command, **kwargs):
        if command[0] == "rpm2cpio":
            proc = _fake_process(returncode=0)
            proc.stdout = MagicMock()
            state["active_rpm"] = Path(command[1]).name
            return proc

        if command[0] == "cpio":
            active = state["active_rpm"]
            proc = _fake_process(returncode=0)

            def communicate():
                target = overlay / "etc" / "config"
                target.parent.mkdir(parents=True, exist_ok=True)
                content = b"from-a" if active == "a.rpm" else b"from-b"
                target.write_bytes(content)
                return (b"", b"")

            proc.communicate.side_effect = communicate
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
        "_overlay_entries",
        lambda _overlay_dir: [".", "dir", "dir/file"],
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

    monkeypatch.setattr(initrd_rpm_update, "_overlay_entries", lambda _dir: ["."])

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

    monkeypatch.setattr(initrd_rpm_update, "_overlay_entries", lambda _dir: ["."])

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
        "initrd-a",
        "rpmupdate-1",
        "rpmupdate-x",
        "rpmupdate-3.old",
        "other-rpmupdate-4",
        "rpmupdate-999999999999999999999999",
    ]
    (tmp_path / "rpmupdate-7").touch()
    (tmp_path / "rpmupdate-8.old").touch()
    (tmp_path / "rpmupdate-1000000000000000000000000").touch()

    assert (
        next_output_name(api_files, tmp_path) == "rpmupdate-1000000000000000000000001"
    )
    assert next_output_name([], []) == "rpmupdate-1"


def test_install_generated_file_retries_on_collision(monkeypatch, tmp_path):
    source = tmp_path / "generated-initrd"
    source.write_bytes(b"new")

    store = tmp_path / "store"
    store.mkdir()
    (store / "rpmupdate-1").write_bytes(b"old")

    context = ImageContext(
        image_id=10,
        store_dir=store,
        files=[
            ImageFileRecord(
                file="rpmupdate-1",
                file_type="initrd",
                external=False,
                local_path=store / "rpmupdate-1",
            )
        ],
        initrd_files=[store / "rpmupdate-1"],
        api_file_values=["rpmupdate-1"],
        prefer_absolute_file_paths=False,
    )

    real_install = initrd_rpm_update._install_file_exclusive
    attempts = []

    def fake_install(src, dst):
        attempts.append(dst.name)
        if len(attempts) == 1:
            (store / "rpmupdate-2").write_bytes(b"concurrent")
            raise FileExistsError("race")
        real_install(src, dst)

    monkeypatch.setattr(initrd_rpm_update, "_install_file_exclusive", fake_install)
    installed = install_generated_file(source, context)

    assert attempts == ["rpmupdate-2", "rpmupdate-3"]
    assert installed.name == "rpmupdate-3"
    assert (store / "rpmupdate-2").read_bytes() == b"concurrent"
    assert installed.read_bytes() == b"new"


def test_install_file_exclusive_cleans_partial_destination(monkeypatch, tmp_path):
    source = tmp_path / "source"
    source.write_bytes(b"source")
    destination = tmp_path / "dest"

    original_copy = initrd_rpm_update.shutil.copyfileobj

    def broken_copy(src, dst, *_args, **_kwargs):
        dst.write(b"partial")
        raise OSError("copy failed")

    monkeypatch.setattr(initrd_rpm_update.shutil, "copyfileobj", broken_copy)

    with pytest.raises(InitrdUpdateError, match="Partial destination file was removed"):
        _install_file_exclusive(source, destination)

    assert not destination.exists()
    monkeypatch.setattr(initrd_rpm_update.shutil, "copyfileobj", original_copy)


def test_install_file_exclusive_reports_cleanup_failure(monkeypatch, tmp_path):
    source = tmp_path / "source"
    source.write_bytes(b"source")
    destination = tmp_path / "dest"

    def broken_copy(src, dst, *_args, **_kwargs):
        dst.write(b"partial")
        raise OSError("copy failed")

    monkeypatch.setattr(initrd_rpm_update.shutil, "copyfileobj", broken_copy)
    monkeypatch.setattr(
        initrd_rpm_update,
        "_remove_file",
        lambda _path: "cannot remove destination",
    )

    with pytest.raises(InitrdUpdateError, match="Rollback failed"):
        _install_file_exclusive(source, destination)


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

    installed = store / "rpmupdate-8"

    context = ImageContext(
        image_id=9,
        store_dir=store,
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
        skip_pillar=True,
    )

    assert result == installed
    assert client.post_calls == [
        (
            "image/addImageFile",
            {"imageId": 9, "file": "rpmupdate-8", "type": "initrd", "external": False},
        )
    ]


def test_install_and_register_rolls_back_when_add_fails(monkeypatch, tmp_path):
    store = tmp_path / "store"
    store.mkdir()
    generated = tmp_path / "new-initrd"
    generated.write_bytes(b"new")
    installed = store / "rpmupdate-1"
    installed.write_bytes(b"new")

    context = ImageContext(
        image_id=9,
        store_dir=store,
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
            skip_pillar=True,
        )
    assert not installed.exists()


def test_install_and_register_rolls_back_after_pillar_failure(monkeypatch, tmp_path):
    store = tmp_path / "store"
    store.mkdir()
    generated = tmp_path / "new-initrd"
    generated.write_bytes(b"new")
    installed = store / "rpmupdate-7"
    installed.write_bytes(b"new")

    context = ImageContext(
        image_id=9,
        store_dir=store,
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
    installed = store / "rpmupdate-7"
    installed.write_bytes(b"new")

    context = ImageContext(
        image_id=9,
        store_dir=store,
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
        initrd_rpm_update, "_remove_file", lambda _path: "cannot remove"
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
            skip_pillar=False,
        )


def test_run_update_skip_pillar_bypasses_pillar_calls(monkeypatch, tmp_path):
    source_initrd = tmp_path / "source"
    source_initrd.write_bytes(b"source")

    args = Namespace(
        initrd=str(source_initrd),
        rpm=[str(tmp_path / "one.rpm")],
        org_id=1,
        name="img",
        version="1",
        revision=1,
        skip_pillar=True,
    )

    context = ImageContext(
        image_id=9,
        store_dir=tmp_path,
        files=[],
        initrd_files=[tmp_path / "initrd"],
        api_file_values=["initrd"],
        prefer_absolute_file_paths=False,
    )

    client = DummyApiClient()
    client.get_responses["image/getPillar"] = InitrdUpdateError("must not be called")

    monkeypatch.setattr(
        initrd_rpm_update, "resolve_rpm_sources", lambda _paths: [tmp_path / "one.rpm"]
    )
    monkeypatch.setattr(initrd_rpm_update, "verify_required_tools", lambda: None)
    monkeypatch.setattr(initrd_rpm_update, "validate_organization", lambda *_args: None)
    monkeypatch.setattr(initrd_rpm_update, "select_image", lambda *_args: 9)
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
        lambda **kwargs: kwargs["image_context"].store_dir / "rpmupdate-1",
    )

    message = run_update(client, args)
    assert "--skip-pillar" in message
    assert "rpmupdate-1" in message
    assert all(call[0] != "image/getPillar" for call in client.get_calls)


def test_run_update_validates_pillar_before_install(monkeypatch, tmp_path):
    source_initrd = tmp_path / "source"
    source_initrd.write_bytes(b"source")

    args = Namespace(
        initrd=str(source_initrd),
        rpm=[str(tmp_path / "one.rpm")],
        org_id=1,
        name="img",
        version="1",
        revision=1,
        skip_pillar=False,
    )

    context = ImageContext(
        image_id=9,
        store_dir=tmp_path,
        files=[],
        initrd_files=[tmp_path / "initrd"],
        api_file_values=["initrd"],
        prefer_absolute_file_paths=False,
    )

    client = DummyApiClient()
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
    monkeypatch.setattr(initrd_rpm_update, "select_image", lambda *_args: 9)
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
