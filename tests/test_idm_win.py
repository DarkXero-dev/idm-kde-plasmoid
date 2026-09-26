import sys
from datetime import datetime

import pytest

import idm_core
import idm_win


@pytest.fixture
def cfg(tmp_path, monkeypatch):
    path = tmp_path / "IDMQuota" / "config.conf"
    monkeypatch.setattr(idm_win, "CONFIG_PATH", str(path))
    monkeypatch.setattr(idm_win, "_protect", lambda data: bytes(reversed(data)))
    monkeypatch.setattr(idm_win, "_unprotect", lambda data: bytes(reversed(data)))
    return path


def test_config_round_trip_does_not_store_plaintext(cfg):
    idm_win.write_config("alice", "s3cret")
    text = cfg.read_text()
    assert "alice" not in text and "s3cret" not in text
    assert text.count("dpapi:") == 2
    assert idm_win.read_config() == {"username": "alice", "password": "s3cret"}


def test_legacy_v2_tokens_are_dropped(cfg):
    cfg.parent.mkdir()
    cfg.write_text("username=v2:abc\npassword=v2:def\n")
    assert idm_win.read_config() == {"username": "", "password": ""}


def test_missing_config_is_empty(cfg):
    assert idm_win.read_config() == {}


def test_fetch_all_without_credentials_raises(cfg):
    with pytest.raises(RuntimeError, match="No credentials configured"):
        idm_win.fetch_all()


def test_fetch_all_and_list_use_core(cfg, monkeypatch):
    idm_win.write_config("alice", "pw")
    monkeypatch.setattr(idm_core, "fetch", lambda u, p: {"error": None, "services": [u, p]})
    monkeypatch.setattr(idm_core, "list_services", lambda u, p: {"error": None, "services": [p, u]})
    assert idm_win.fetch_all()["services"] == ["alice", "pw"]
    assert idm_win.list_services()["services"] == ["pw", "alice"]


NOW = datetime(2026, 9, 26, 10, 0)


@pytest.mark.parametrize("iso, text, line, level", [
    ("2026-10-12T23:59", "16 days", "12 Oct 2026 23:59", "ok"),
    ("2026-09-26T23:59", "Today 23:59", "26 Sep 2026 23:59", "soon"),
    ("2026-09-26T09:00", "Expired", "26 Sep 2026 09:00", "expired"),
    ("2026-09-27T00:30", "1 day", "27 Sep 2026 00:30", "soon"),
    ("2026-09-30", "4 days", "30 Sep 2026", "soon"),
    ("2026-09-26", "Today", "26 Sep 2026", "soon"),
    ("2026-09-25", "Expired", "25 Sep 2026", "expired"),
    (None, "-", "", "ok"),
    ("junk", "-", "", "ok"),
])
def test_expiry_state(iso, text, line, level):
    assert idm_win.expiry_state(iso, NOW) == {"text": text, "line": line, "level": level}


SERVICES = [{"id": "a", "type": "adsl"}, {"id": "b", "type": "lte"},
            {"id": "c", "type": "fiber"}, {"id": "d", "type": "adsl"}]


def test_shown_services_follow_portal_order_not_tick_order():
    assert [s["id"] for s in idm_win.shown_services(SERVICES, ["c", "a"])] == ["a", "c"]


def test_shown_services_default_to_first_three():
    assert [s["id"] for s in idm_win.shown_services(SERVICES, [])] == ["a", "b", "c"]


def test_shown_services_stale_selection_falls_back_to_default():
    assert [s["id"] for s in idm_win.shown_services(SERVICES, ["gone"])] == ["a", "b", "c"]


def test_shown_services_are_capped_at_three():
    assert len(idm_win.shown_services(SERVICES, ["a", "b", "c", "d"])) == 3


@pytest.mark.parametrize("kind, label", [("adsl", "ADSL"), ("lte", "LTE"), ("fiber", "FIBER"), ("other", "SERVICE")])
def test_type_label(kind, label):
    assert idm_win.type_label(kind) == label


def test_display_name_prefers_alias_and_falls_back_to_portal_name():
    svc = {"id": "adsl_home", "name": "adsl_home"}
    assert idm_win.display_name(svc, {"adsl_home": "Home line"}) == "Home line"
    assert idm_win.display_name(svc, {"adsl_home": ""}) == "adsl_home"
    assert idm_win.display_name(svc, {}) == "adsl_home"


@pytest.mark.skipif(sys.platform != "win32", reason="DPAPI exists only on Windows")
def test_real_dpapi_round_trip():
    secret = "pässwörd€".encode("utf-8")
    sealed = idm_win._protect(secret)
    assert sealed != secret
    assert idm_win._unprotect(sealed) == secret
