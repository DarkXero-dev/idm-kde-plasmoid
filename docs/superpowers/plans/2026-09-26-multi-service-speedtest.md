# Multi-service, gauge styles, speed test, expiry: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One IDM login, many services: detect, pick up to 3, show with two gauge styles and full expiry date/time, plus an embedded speed test, on Linux (QML) and Windows (PyQt5), with all review defects fixed.

**Architecture:** Shared pure-Python `idm_core.py` (portal login/scrape) and `speed_core.py` (speedtest-cli wrapper) live in the plasmoid dir; Linux `fetch_quota.py` and `Win/fetch_quota.py` are thin wrappers adding config and crypto. QML runs scripts through the `P5Support` executable engine; Windows imports the modules directly.

**Tech Stack:** Python 3 (`requests`, `cryptography`, `speedtest-cli` 2.1.3, `pytest`), QML/Kirigami (Plasma 6), PyQt5 5.15.

**Spec:** `docs/superpowers/specs/2026-09-26-multi-service-speedtest-design.md`

## Progress (session recovery)

Tick the task line when done. After every task: update this file and the memory note `project_progress`. Resume = first unticked task.

- [x] Task 1: `idm_core.py` + tests
- [x] Task 2: Linux `fetch_quota.py` rewrite + tests
- [x] Task 3: `speed_core.py`, `speed_run.py` + tests
- [x] Task 4: config schema and settings pages (QML)
- [x] Task 5: `main.qml`, `ConnectionTab.qml`, `SpeedTestPage.qml`
- [x] Task 6: cleanup, `install.sh`, `.gitignore`, README
- [x] Task 7: Windows fetcher (DPAPI) and app
- [x] Task 8: full verification (pyflakes: drop unused `tray` var in Win/main.py and unused `base64` import in tests/test_idm_win.py)
- [x] Task 9: user revisions (mid-build), do in order:
  - [x] 9a: style values `speedometer` | `simple` (labels "Speedometer" / "Simple"; was `arc`/"Semicircle") in QML, Win, tests, README
  - [x] 9b: 3 cards: logo tiny, top-left corner (overlay); 2 cards: logo between; 1 card: no logo
  - [x] 9c: rename services: kcfg `serviceNames` JSON map id -> alias; text field next to each checkbox in settings (Linux + Windows); alias falls back to portal name everywhere (cards, tooltip, tray); `display_name` helper + tests
  - [x] 9d: speed test in a separate sized window (Linux `SpeedTestWindow.qml`, QtQuick Window; popup collapses on open) with animated speedometer needle; `speed_core` emits `live` Mbps estimate (completed request bytes / elapsed); scale marks 0,5,10,25,50,100,250,500,1000; Windows SpeedTestDialog gets the same needle gauge
  - [x] 9e: tests must not leave settings behind: clear QSettings + tmp dirs in fixture teardown; remove any plasmoidviewer/QML cache my runs left

## Global Constraints

- Never `git commit` or `git push`; hand the user the commands at the end.
- No em-dashes anywhere (code, comments, docs, chat).
- Comments only where the WHY is non-obvious; no dead code, no orphan files.
- Wayland first; nothing X11-specific.
- Terms: "login" = the one portal credential; "service" = one MyAccounts grid row. Never call a service an "account".
- Max 3 services shown at once (hard cap, 4th checkbox disabled).
- Type map: `adsl`,`vdsl` -> `adsl`; `3g`,`4g`,`lte` -> `lte`; `fiber` -> `fiber`; anything else -> `other`.
- `gaugeStyle` values: `speedometer` | `arc`. kcfg keys: `username`, `password`, `selectedServices` (JSON array string of ids), `activeService`, `gaugeStyle`.
- Fetch JSON: `{"error": str|null, "services": [{id,type,name,percent,remaining,expiry,expiry_iso,updated,error}]}`. `--list` JSON: `{"error": ..., "services": [{id,type,name,raw_type}]}`.
- Linux config file `~/.config/IDMQuota/config.conf` must be created mode 0600.
- Speed test: `speedtest.Speedtest(secure=True)`; progress callback `(i, total, start=False, end=False)`; no jitter (library does not provide it).

---

### Task 1: `idm_core.py` + tests

**Files:**
- Create: `idm-quota-monitor/idm_core.py`
- Create: `tests/test_idm_core.py`, `tests/conftest.py`

**Interfaces:**
- Produces:
  - `TYPE_MAP: dict[str,str]`
  - `extract_hidden_fields(html: str) -> dict`
  - `parse_expiry(s: str) -> tuple[datetime|None, bool]` (datetime, has_time)
  - `expiry_iso(dt: datetime, has_time: bool) -> str` (`YYYY-MM-DDTHH:MM` or `YYYY-MM-DD`)
  - `parse_services(html: str) -> list[dict]` items `{ctrl, id, type, raw_type, name}`; `id` unique (duplicate names get `#ctlNN` suffix)
  - `scrape_page(html: str) -> dict` (percent, remaining, expiry, expiry_iso, updated, error)
  - `login(session, username, password) -> None` raises `RuntimeError("Login failed: check username and password")`
  - `discover(session) -> tuple[list[dict], str]` (services, accounts page html)
  - `fetch(username, password) -> dict` (fetch JSON shape), `list_services(username, password) -> dict`
- `conftest.py` puts `idm-quota-monitor/` on `sys.path`.

- [ ] **Step 1:** Write failing tests: `parse_expiry` for `"10/16/2026 23:59"` (m/d), `"16/10/2026 23:59"` (d/m), `"2026-10-16 23:59:00"`, `"10/16/2026 11:59 PM"` (-> hour 23), date-only, garbage -> `(None, False)`; `expiry_iso`; `parse_services` on synthetic grid HTML with two ADSL rows, one LTE, one `Fiber`, one `Satellite` (-> `other`) and duplicate name; `scrape_page` on LTE-table layout, ADSL label layout, missing quota elements -> `ValueError`.
- [ ] **Step 2:** `pytest tests/test_idm_core.py -v` fails (module missing).
- [ ] **Step 3:** Implement `idm_core.py`: regexes copied from current `fetch_quota.py` (hidden fields, grid rows, pct/remaining, expiry patterns 1-4) as a list of compiled patterns; time part accepts optional `AM|PM` with `%I:%M %p` formats added; name from `id="..._ResidentialAccountName"[^>]*>([^<]*)<` falling back to the ctrl id; `scrape` posts the Manage postback per service exactly as today.
- [ ] **Step 4:** Tests pass.
- [ ] **Step 5:** Tick Task 1, update memory note.

### Task 2: Linux `fetch_quota.py` rewrite

**Files:**
- Modify: `idm-quota-monitor/fetch_quota.py`
- Test: `tests/test_fetch_quota.py`

**Interfaces:**
- Consumes: Task 1 `fetch`, `list_services`.
- Produces CLI: default fetch, `--list`, `--write-config HEXU HEXP`; each prints one JSON line. `write_config(u, p)` writes 0600 (`os.open(..., 0o600)`, `os.fchmod`). Missing-dependency and any exception print `{"error": "...", "services": []}` and exit 1.

- [ ] **Step 1:** Failing tests: `write_config` then `stat` mode == 0o600 and `read_config` round-trips (monkeypatch `CONFIG_PATH`); `main(["--list"])` and `main([])` with `idm_core.fetch` monkeypatched print the expected JSON; error path prints `{"error":..., "services": []}` and returns 1.
- [ ] **Step 2:** Run, fail.
- [ ] **Step 3:** Rewrite: keep Fernet helpers and `read_config`; delete history code, `discover`/`scrape`/`parse_expiry`; add `main(argv) -> int`; `if __name__ == "__main__": sys.exit(main(sys.argv[1:]))`.
- [ ] **Step 4:** Tests pass; run `python3 idm-quota-monitor/fetch_quota.py` with no credentials and confirm the error JSON.
- [ ] **Step 5:** Tick Task 2, update memory.

### Task 3: speed engine

**Files:**
- Create: `idm-quota-monitor/speed_core.py`, `idm-quota-monitor/speed_run.py`
- Test: `tests/test_speed_core.py`

**Interfaces:**
- Produces: `run(progress: Callable[[dict], None], speedtest_cls=speedtest.Speedtest) -> dict`. Every `progress` dict has keys `phase` (`config|server|ping|download|upload|done|error`), `progress` (0..1), `ping` (ms|None), `download` (Mbps|None), `upload` (Mbps|None), `server` (str|None), `error` (str|None). `speed_run.py` writes each dict atomically to `$XDG_RUNTIME_DIR/idm-speedtest.json` (fallback `tempfile.gettempdir()`) and prints the final dict as JSON to stdout.

- [ ] **Step 1:** Failing tests with a fake `Speedtest` class whose `download`/`upload` invoke the callback 3 times: assert phase order `config, server, ping, download, upload, done`, monotonic `progress` within a phase, Mbps = bits/1e6, and an exception yields a final `phase == "error"` dict.
- [ ] **Step 2:** Run, fail.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Tests pass. Run `python3 idm-quota-monitor/speed_run.py` once against the real network and record the outcome.
- [ ] **Step 5:** Tick Task 3, update memory.

### Task 4: config schema and settings pages

**Files:**
- Modify: `contents/config/main.xml` (remove `connectionChoice`, `autoRefresh`; add `selectedServices` String default `[]`, `activeService` String default empty, `gaugeStyle` String default `speedometer`)
- Modify: `contents/config/config.qml` (add About category `configAbout.qml`, icon `help-about`)
- Rewrite: `contents/ui/configGeneral.qml`
- Modify: `contents/ui/configAbout.qml` (logo `../images/logo.png`, license `GPL-3.0-or-later`)

**Interfaces:**
- `configGeneral.qml` exposes `cfg_username`, `cfg_password`, `cfg_selectedServices` (JSON string), `cfg_gaugeStyle`. "Detect services" runs `python3 fetch_quota.py --write-config HEXU HEXP` and, on completion, `--list`; also auto-runs `--list` on open when a username exists. One `QQC2.CheckBox` per service showing `"<TYPE> <name>"` (plus expiry text if present), `enabled: checked || count < 3`. First detection with an empty selection ticks the first 3.

- [ ] **Step 1:** Implement the four files.
- [ ] **Step 2:** `qmllint` (if present) on the changed files; check the About logo path exists.
- [ ] **Step 3:** Tick Task 4, update memory.

### Task 5: main UI

**Files:**
- Rewrite: `contents/ui/main.qml`, `contents/ui/ConnectionTab.qml`
- Create: `contents/ui/SpeedTestPage.qml`

**Interfaces:**
- `ConnectionTab` props: `svc` (service object), `loading` (bool), `gaugeStyle` (string). Draws speedometer or semicircle, `Remaining`, `Updated`, `Expires In` (countdown computed live from `svc.expiry_iso` via a 60 s timer) and a second line with `d MMM yyyy HH:mm` (date only if no time). Amber at <= 5 days, red when expired.
- `SpeedTestPage` props: `pluginDir` (string). States idle, running, done, error. Polls `cat $XDG_RUNTIME_DIR/idm-speedtest.json` every 300 ms while running; final result from the runner's stdout. Tiles: Ping, Download, Upload, Server. Buttons: Start / Run again, Back (emits `back()`).
- `main.qml`: parse `d.error` and `d.services`; `shown` = selected ids (JSON) in order, else first 3, capped at 3; `activeService` cycles through `shown` on badge click and is persisted in `Plasmoid.configuration.activeService`; popup width 1 card 420, 2 cards 958 (logo between), 3 cards 1150, height 327; footer Canvas timer runs only while `root.expanded`, interval 50 ms; footer buttons Settings, Speed Test, Refresh; guard `percent == null` in the panel; the 15 min QML timer is the only scheduler.

- [ ] **Step 1:** Implement.
- [ ] **Step 2:** `plasmoidviewer -a idm-quota-monitor` with a fake fetch output (temporary stub script in scratchpad, not committed) to check 1, 2 and 3 cards, both gauge styles, expiry lines, speed page layout, and error states; screenshots to the scratchpad.
- [ ] **Step 3:** Tick Task 5, update memory.

### Task 6: cleanup, installer, docs

**Files:**
- Delete: `contents/fonts/Orbitron_Bold.ttf`, `idm-quota.service`, `idm-quota.timer`, `history_*.json`, `__pycache__/` (git rm --cached only for tracked ones is not done by Claude: file deletions are fine, the user stages)
- Modify: `.gitignore`, `install.sh`, `README.md`

- [ ] **Step 1:** `install.sh`: drop systemd steps, add `speedtest-cli` package (`python-speedtest-cli` pacman; `speedtest-cli` apt/dnf; pip fallback for `speedtest-cli`), check `rsync`, keep QML cache clear.
- [ ] **Step 2:** README rewrite (features, requirements, install, credentials caveat, file tree, speed test, manual refresh from the widget button, no systemd/logs sections).
- [ ] **Step 3:** `bash -n install.sh`; grep repo for leftover references to removed files or keys (`history`, `autoRefresh`, `connectionChoice`, `idm-quota.timer`).
- [ ] **Step 4:** Tick Task 6, update memory.

### Task 7: Windows

**Files:**
- Modify: `Win/fetch_quota.py` (wrapper over `idm_core`, DPAPI crypto via `ctypes` `CryptProtectData`/`CryptUnprotectData`, no history; `fetch_all()`, `list_services()`)
- Modify: `Win/main.py` (dynamic 1-3 service tabs, Settings dialog with detect button, checkboxes, gauge style combo via `QSettings("IDMQuota", "Monitor")`, semicircle paint mode, expiry date/time line, `SpeedTestDialog` in a `QThread`, tray cycles through shown services, remove unused imports)
- Modify: `Win/build.bat`, `.github/workflows/build-windows.yml`, `Win/idm_monitor.spec` (copy `idm_core.py` and `speed_core.py` into `Win/`, add `speedtest-cli`, hidden import `speedtest`), `Win/requirements.txt`
- Test: `tests/test_win_fetch.py` (fake `ctypes.windll` not needed: DPAPI functions isolated, test only that the non-Windows import path is guarded)

- [ ] **Step 1:** Implement; keep platform imports inside functions so the modules import on Linux.
- [ ] **Step 2:** Run `QT_QPA_PLATFORM=offscreen` smoke test constructing `MainWindow` with monkeypatched fetch data for 1, 2, 3 services and both styles; grab widget screenshots into the scratchpad.
- [ ] **Step 3:** `python3 -m pyflakes Win/*.py` clean.
- [ ] **Step 4:** Tick Task 7, update memory.

### Task 8: full verification

- [ ] **Step 1:** `pytest -v` all green; `python3 -m pyflakes idm-quota-monitor Win tests`.
- [ ] **Step 2:** `./install.sh` dry check by reading its output only for changed steps is not possible without sudo prompts: verify by `bash -n` and by running the rsync copy step manually into the scratchpad.
- [ ] **Step 3:** Grep for em-dash characters and dead code, re-read the full diff.
- [ ] **Step 4:** Invoke `superpowers:verification-before-completion`, then hand the user the git commands.
- [ ] **Step 5:** Tick Task 8, update memory.
