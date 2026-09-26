import json
import os
import stat

import pytest

import fetch_quota
import idm_core


@pytest.fixture
def cfg(tmp_path, monkeypatch):
    path = tmp_path / "IDMQuota" / "config.conf"
    monkeypatch.setattr(fetch_quota, "CONFIG_PATH", str(path))
    return path


def run_main(capsys, argv):
    code = fetch_quota.main(argv)
    return code, json.loads(capsys.readouterr().out)


def test_write_config_is_owner_only_and_round_trips(cfg):
    fetch_quota.write_config("alice", "s3cret")
    assert stat.S_IMODE(os.stat(cfg).st_mode) == 0o600
    assert "s3cret" not in cfg.read_text()
    assert fetch_quota.read_config() == {"username": "alice", "password": "s3cret"}


def test_write_config_tightens_existing_permissions(cfg):
    cfg.parent.mkdir()
    cfg.write_text("username=x\n")
    cfg.chmod(0o644)
    fetch_quota.write_config("alice", "pw")
    assert stat.S_IMODE(os.stat(cfg).st_mode) == 0o600


def test_main_write_config_takes_hex_args(cfg, capsys):
    code, out = run_main(capsys, ["--write-config", "alice".encode().hex(), "pw".encode().hex()])
    assert (code, out) == (0, {"ok": True})
    assert fetch_quota.read_config()["username"] == "alice"


def test_main_fetch_prints_core_result(cfg, capsys, monkeypatch):
    fetch_quota.write_config("alice", "pw")
    seen = {}
    monkeypatch.setattr(idm_core, "fetch", lambda u, p: seen.update(u=u, p=p) or {"error": None, "services": []})
    code, out = run_main(capsys, [])
    assert code == 0 and out == {"error": None, "services": []}
    assert seen == {"u": "alice", "p": "pw"}


def test_main_list_uses_list_services(cfg, capsys, monkeypatch):
    fetch_quota.write_config("alice", "pw")
    monkeypatch.setattr(idm_core, "list_services", lambda u, p: {"error": None, "services": [{"id": "a"}]})
    code, out = run_main(capsys, ["--list"])
    assert code == 0 and out["services"] == [{"id": "a"}]


def test_main_without_credentials_reports_error(cfg, capsys):
    code, out = run_main(capsys, [])
    assert code == 1
    assert out["services"] == [] and "credentials" in out["error"]


def test_main_reports_portal_errors(cfg, capsys, monkeypatch):
    fetch_quota.write_config("alice", "pw")

    def boom(u, p):
        raise RuntimeError("Login failed: check username and password")

    monkeypatch.setattr(idm_core, "fetch", boom)
    code, out = run_main(capsys, [])
    assert code == 1
    assert out == {"error": "Login failed: check username and password", "services": []}


def test_main_reports_missing_dependency(cfg, capsys, monkeypatch):
    fetch_quota.write_config("alice", "pw")

    def missing(u, p):
        raise ImportError("no module", name="requests")

    monkeypatch.setattr(idm_core, "fetch", missing)
    code, out = run_main(capsys, [])
    assert code == 1
    assert out["error"] == "Missing dependency: pip install requests"
