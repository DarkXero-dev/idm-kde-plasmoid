# IDM Quota Monitor: multi-service, gauge styles, speed test, expiry

Scope: Linux Plasma 6 plasmoid and the Windows PyQt5 app, both changed together.

## Terms

- **Login**: the one IDM portal username/password the user enters. The widget supports exactly one login.
- **Service**: one row in the portal's MyAccounts grid under that login. A login can hold many services: any number of ADSL/VDSL, LTE and Fiber lines.
- Never "account" for a service; "account" means the login.

## Goals

1. Detect every service under the login; user ticks which to show (max 3 shown at once).
2. Gauge style switch: speedometer (current) or plain semicircle.
3. Embedded speed test (Linux QML page, Windows dialog) on a shared engine.
4. Show each service's expiry date and time.
5. Fix all defects found in the code review (list in "Fixes").

## 1. Layout and shared core

- `idm-quota-monitor/idm_core.py` (new): login, service discovery, scrape, expiry parsing. No config, crypto or UI. Imported by `fetch_quota.py` (Linux) and `Win/fetch_quota.py`. The Windows build (`build.bat`, CI) copies it into `Win/` as it already does for `logo.png`.
- `idm-quota-monitor/speed_core.py` (new): wraps `speedtest.Speedtest()` (sivel `speedtest-cli`) with a progress callback for ping, download, upload.
- `idm-quota-monitor/speed_run.py` (new, Linux): CLI around `speed_core`; writes progress JSON to `$XDG_RUNTIME_DIR/idm-speedtest.json`.
- `fetch_quota.py` (Linux) keeps config path, Fernet, CLI modes. `Win/fetch_quota.py` keeps config path and crypto.
- Removed: `contents/fonts/Orbitron_Bold.ttf`, tracked `__pycache__`, `history_*.json`, `idm-quota.service`, `idm-quota.timer`, the stderr debug print, the stray `import sys` in `scrape`. `.gitignore` gains `__pycache__/` and `history_*.json`.
- History feature removed entirely (written and parsed but never rendered).

## 2. Data model and multi-service

- Type map: `adsl`, `vdsl` -> `adsl`; `3g`, `4g`, `lte` -> `lte`; `fiber` -> `fiber`. Any other portal type maps to `other` and is still listed (not silently dropped).
- Service object: `{id, type, name, percent, remaining, expiry, expiry_iso, updated, error}`. `id` is the portal's per-service name (`ResidentialAccountName` cell); it is the stable key, so several services of one type coexist.
- Fetch output: `{"services": [ ... ]}`.
- CLI modes: default fetch; `--list` (login and grid only: id, type, name, raw type string; used by settings); `--write-config`.
- kcfg keys: `username`, `password`, `selectedServices` (comma-separated ids), `activeService` (id shown on panel), `gaugeStyle` (`speedometer` | `arc`). `connectionChoice` and `autoRefresh` are removed.
- Settings page: "Detect services" button runs `--list`; checkbox per service; the 4th tick is disabled while 3 are ticked. Default selection when none saved: first 3 discovered.
- Popup: one row of 1 to 3 `ConnectionTab`s (card width adapts; logo shown only with 1 or 2 cards).
- Panel: shows `activeService`; clicking the badge cycles through ticked services only. `percent == null` handled.

## 3. Gauge style and expiry

- `arc` style: 180 degree semicircle, track plus fill, percent centred under it. No needle, no ticks. `speedometer` unchanged. Selected in Settings (Linux) and Settings dialog (Windows).
- Expiry: the card shows a bold countdown ("16 days" / "Today" / "Expired") plus a second line with date and time ("12 Oct 2026 23:59"; date only if the portal gives no time). Python emits `expiry_iso`; QML/Qt compute the countdown live so it does not go stale after midnight. Amber at 5 days or less, red when expired.
- Risk: `parse_expiry` tries `%m/%d/%Y` before `%d/%m/%Y`. `--list` also prints the raw expiry string so the user can confirm the format on their real login once.

## 4. Speed test

- Linux: "Speed Test" button in the popup footer swaps the popup to an inline page with a Back button (inline, not a separate window: it would close with the popup on Wayland anyway). One animated gauge changes per phase (Ping, Download, Upload) with live Mbps; result tiles for ping, jitter, down, up; "Run again". QML polls the progress file every ~300 ms via the executable engine (which only returns at process exit, so streaming is not possible).
- Windows: `SpeedTestDialog` (QDialog) runs `speed_core` in a QThread, callbacks feed the same phases and tiles.
- Deps: `install.sh` installs `python-speedtest-cli` (pacman) / `speedtest-cli` (apt, dnf), else pip; `Win/requirements.txt` and CI add `speedtest-cli`.

## 5. Fixes

- Scheduler: systemd timer/service, the switch and `autoRefresh` removed; the 15 min QML timer is the only scheduler (fixes double-fetch and broken re-enable). Behaviour change: refresh only while the widget is loaded.
- Credentials: `config.conf` created 0600 via `os.open`. Fernet key from machine-id stays and is documented as obfuscation, not security. The password briefly appears in the shell command line when saved via `P5Support`; no clean in-engine fix exists, documented in README.
- Windows crypto: replace the hand-rolled SHA-256 stream cipher with DPAPI (`CryptProtectData` via `ctypes`, per-user, no dependency). Not runnable on Linux; needs the user's Windows test.
- `configAbout.qml` registered in `config.qml`; logo path fixed to `../images/logo.png`; license text matches `metadata.json`.
- End-Of-Line footer Canvas repaints only while the popup is visible and is throttled.
- Windows: unused imports removed (`math`, `QTabWidget`, `QGraphicsOpacityEffect`, `QSize`); regex pattern 3 gained through the shared core.
- README rewritten: features, requirements (`requests`, `cryptography`, `speedtest-cli`), file tree, no chart claim, credential caveat.

## Testing

- `pytest`: `idm_core` (`parse_expiry`, discovery, scrape) against synthetic HTML fixtures built from the existing regexes; `speed_core` with a fake `Speedtest`; `--list`/fetch JSON shape.
- Linux UI: `plasmoidviewer` here, then install and run in Plasma.
- Windows: syntax and unit tests here; CI build and the user's manual run for GUI and DPAPI.
- No commits or pushes by Claude; git commands handed over at the end.

## Revisions made during the build

- Gauge styles are `speedometer` and `simple` (was `arc` / "Semicircle").
- Logo: 2 cards, between them; 3 cards, tiny in the top-left corner; 1 card, none.
- Services can be renamed: kcfg `serviceNames` (JSON map id to alias) on Linux, `QSettings` on Windows. The portal name is the fallback and the placeholder.
- Speed test runs in its own window (Linux `SpeedTestWindow.qml`, Windows `SpeedTestDialog`) with a needle on a 0, 5, 10, 25, 50, 100, 250, 500, 1000 Mbps scale. `speed_core` adds a `live` Mbps estimate (bytes of completed requests over elapsed time) and shows Ping, Download and Upload as separate steps. No jitter (the library does not provide it).
- `speed_core` picks the server itself: speedtest-cli 2.1.3 marks every Ookla server unreachable (no redirect handling, no User-Agent).
- `selectedServices` is a JSON array string; cards follow portal order; `--list` has no expiry; the portal returns ISO expiry dates, so the day/month ambiguity does not occur.
- The popup height is derived from its content; the gauge shrinks to fit the card.
- Plasma's built-in About page is used; `configAbout.qml` was removed.
- Windows: PyInstaller `pathex` points at `idm-quota-monitor/` (no module copies); backend is `Win/idm_win.py`; legacy `v2:` credentials are dropped and must be re-entered once.
- Speed test shows two steps, Download (cyan) and Upload (purple); each starts from 0 and the last reading stays on the gauge when done. Ping is a small info line.
- A service name replaces the type heading on the card (type and portal name show only when no name is set); the panel badge keeps the type label.
- Simple style: large semicircle sized to the card with the three stats in a row underneath (Windows too).
- Plasma appends its own About page after the applet pages and cannot be removed or reordered by an applet, so the applet ships none (sidebar: General, Keyboard Shortcuts, About).
- The trailing word "Remaining" is dropped from the portal's remaining text.
- Speed test is two independent elements (`SpeedPanel.qml` x2 on Linux, `SpeedPanel` widgets on Windows), each with its own colour, gauge and Start button. Nothing autostarts; only one test runs at a time (`speed_run.py download|upload`, `speed_core.run(progress, test)`). Each needle starts from 0.
- Live speed comes from the bytes speedtest-cli's workers really move (tracked by wrapping `HTTPDownloader` and `HTTPUploaderData`), sampled every 250 ms; counting finished requests by declared size overshot on upload.
- With 2 cards the logo has no negative margin (it overlapped the wider Simple gauges).
- Speed engine replaced (`speedtest-cli` removed, no extra dependency): server list from Speedtest's `api/js/servers` (its old static list lacked the user's nearest servers and picked a far one); latency probe of the 12 nearest over HTTPS on a kept-alive connection (median), the 3 best re-probed with 12 samples; 8 parallel streams against `/download` and `/upload`, 2 s warm-up excluded, 10 s total, live speed over a 1 s sliding window. Measured 302 down / 152 up Mbps on a line rated 300 / 150, where speedtest-cli reported about 125 / 125.
- The endpoint is unofficial; if it changes the test reports "Could not fetch the speed test server list".
- Windows CI runs the Windows-relevant tests (including a real DPAPI round trip) before building.
- Version 2.0 (`metadata.json`, Windows window title). The plugin icon is the Xero logo (`contents/images/Xero.png`, 512px square) shown by Plasma's built-in About page, which places the icon left of the title at a fixed size and cannot be centred by an applet.
- The popup layout moved from `main.qml` into `Popup.qml` so it can be rendered on its own; the speed test needle glides over 950 ms because the executable data source only delivers about one update per second.
- README demo: `docs/demo.gif`, rendered frame by frame from the real QML (popup, settings page, Plasma's About page with real metadata, and a live speed test) with PySide6 `grabWindow`.
