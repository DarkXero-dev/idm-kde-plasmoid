import importlib.util
import os

import pytest

pytest.importorskip("PyQt5")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QLabel

ROOT = os.path.join(os.path.dirname(__file__), "..")


@pytest.fixture(scope="module")
def win():
    spec = importlib.util.spec_from_file_location("win_main", os.path.join(ROOT, "Win", "main.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def service(sid, kind="adsl", pct=42.5):
    return {"id": sid, "type": kind, "name": sid, "percent": pct, "remaining": "57.5 GB",
            "expiry": "x", "expiry_iso": "2099-10-12T23:59", "updated": "10:00", "error": None}


SERVICES = [service("a"), service("b", "lte", 78.0), service("c", "fiber", 93.4), service("d")]


@pytest.fixture
def window(app, win, monkeypatch, tmp_path):
    monkeypatch.setattr(win.backend, "SETTINGS_PATH", str(tmp_path / "settings.json"))
    monkeypatch.setattr(win.backend, "fetch_all", lambda: {"error": None, "services": SERVICES})
    w = win.MainWindow()
    w._thread.wait()
    app.processEvents()
    yield w
    w._timer.stop()


def tabs(win, w):
    return w.findChildren(win.ConnectionTab)


def test_default_shows_first_three_services(win, window):
    assert [t.hdr_lbl.text() for t in tabs(win, window)] == ["ADSL  a", "LTE  b", "FIBER  c"]


def test_two_services_get_the_logo_between(win, window):
    window.prefs.selected = ["a", "b"]
    window._render()
    assert len(tabs(win, window)) == 2
    assert any(isinstance(window.row.itemAt(i).widget(), QLabel)
               and window.row.itemAt(i).widget().width() == 200 for i in range(window.row.count()))


def test_one_service(win, window):
    window.prefs.selected = ["c"]
    window._render()
    assert [t.hdr_lbl.text() for t in tabs(win, window)] == ["FIBER  c"]


def test_gauge_style_follows_preference(win, window):
    window.prefs.gauge_style = "simple"
    window._render()
    assert all(t.gauge.size().height() == win.GaugeWidget.SIZES["simple"][1] for t in tabs(win, window))


def test_expiry_line_shows_date_and_time(win, window):
    assert tabs(win, window)[0].lbl_exp_line.text() == "12 Oct 2099 23:59"


def test_fetch_error_is_shown_instead_of_cards(win, window):
    window._on_error("Login failed: check username and password")
    assert tabs(win, window) == []
    assert window.status_lbl.text().startswith("Error: Login failed")


def test_settings_caps_selection_at_three(win, app, window):
    dlg = win.SettingsDialog(window.prefs)
    dlg._on_listed({"error": None, "services": SERVICES})
    checked = [c.isChecked() for c in dlg._checks]
    assert checked == [True, True, True, False]
    assert not dlg._checks[3].isEnabled()
    dlg._checks[0].setChecked(False)
    assert dlg._checks[3].isEnabled()


def test_settings_save_stores_selection_and_style(win, app, window, monkeypatch):
    monkeypatch.setattr(win, "set_startup", lambda enabled: None)
    dlg = win.SettingsDialog(window.prefs)
    dlg._on_listed({"error": None, "services": SERVICES})
    dlg._checks[1].setChecked(False)
    dlg.style_combo.setCurrentIndex(dlg.style_combo.findData("simple"))
    dlg._save()
    assert window.prefs.selected == ["a", "c"]
    assert window.prefs.gauge_style == "simple"


READING = {"phase": "download", "progress": 0.5, "ping": 12.5, "download": None, "upload": None,
           "server": "Beirut, Lebanon", "live": None, "error": None}


def test_speed_dialog_has_two_separate_idle_panels_and_does_not_autostart(win, app):
    dlg = win.SpeedTestDialog()
    dlg.show()
    app.processEvents()
    assert dlg._thread is None
    assert [p.button.text() for p in dlg.panels.values()] == ["Start", "Start"]
    assert dlg.panels["download"]._color != dlg.panels["upload"]._color


def test_progress_only_moves_the_active_panel(win, app):
    dlg = win.SpeedTestDialog()
    dlg._active = "upload"
    dlg._on_progress({**READING, "phase": "upload", "live": 42.3})
    upload, download = dlg.panels["upload"], dlg.panels["download"]
    assert upload.gauge._text == "42.3" and upload.caption.text() == "Testing upload"
    assert upload.gauge._anim.endValue() == pytest.approx(win.speed_core.scale_fraction(42.3))
    assert download.gauge._text == "-"
    assert dlg.info_lbl.text() == "Ping 12.5 ms   Server: Beirut, Lebanon"


def test_finished_step_shows_its_result_and_errors_show_in_red(win, app):
    dlg = win.SpeedTestDialog()
    dlg._active = "download"
    dlg._on_progress({**READING, "phase": "done", "progress": 1.0, "download": 80.0, "live": 80.0})
    assert dlg.panels["download"].gauge._text == "80.0"
    assert dlg.panels["download"].caption.text() == "Complete"
    dlg._active = "upload"
    dlg._on_progress({**READING, "phase": "error", "error": "boom"})
    assert dlg.panels["upload"].caption.text() == "boom"


def test_starting_one_test_runs_only_that_step_and_re_enables_buttons(win, app, monkeypatch):
    seen = []

    def fake_run(progress, test):
        seen.append(test)
        progress({**READING, "phase": "done", "progress": 1.0, test: 5.0, "live": 5.0})

    monkeypatch.setattr(win.speed_core, "run", fake_run)
    dlg = win.SpeedTestDialog()
    dlg._start("upload")
    assert not dlg.panels["download"].button.isEnabled()
    dlg._thread.wait()
    app.processEvents()
    assert seen == ["upload"]
    assert dlg.panels["upload"].gauge._text == "5.0"
    assert dlg.panels["download"].gauge._text == "-"
    assert [p.button.text() for p in dlg.panels.values()] == ["Start", "Run again"]
    assert all(p.button.isEnabled() for p in dlg.panels.values())


def test_corner_logo_only_for_three_services(win, window):
    assert window.corner_logo.isVisibleTo(window.body)
    window.prefs.selected = ["a", "b"]
    window._render()
    assert not window.corner_logo.isVisibleTo(window.body)


def test_alias_is_used_on_the_card_header(win, window):
    window.prefs.names = {"b": "My Phone"}
    window._render()
    assert [t.hdr_lbl.text() for t in tabs(win, window)] == ["ADSL  a", "My Phone", "FIBER  c"]


def test_settings_save_stores_aliases_and_drops_empty_ones(win, app, window, monkeypatch):
    monkeypatch.setattr(win, "set_startup", lambda enabled: None)
    dlg = win.SettingsDialog(window.prefs)
    dlg._on_listed({"error": None, "services": SERVICES})
    dlg._aliases["a"].setText("  Home  ")
    dlg._aliases["b"].setText("   ")
    dlg._save()
    assert window.prefs.names == {"a": "Home"}
