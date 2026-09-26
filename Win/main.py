#!/usr/bin/env python3
"""
IDM Quota Monitor - Windows (PyQt5 / Qt 5.15)
Supports Windows 7 SP1 to 11
System tray icon + popup window
"""

import sys, os, math
from datetime import datetime
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QPushButton, QDialog, QLineEdit, QFormLayout,
    QDialogButtonBox, QSystemTrayIcon, QMenu, QAction,
    QCheckBox, QComboBox,
)
from PyQt5.QtGui  import (
    QPainter, QColor, QPen, QFont, QIcon, QPixmap,
)
from PyQt5.QtCore import (
    Qt, QTimer, QThread, pyqtSignal, QPointF, QRectF,
    QVariantAnimation, QEasingCurve,
)

if not getattr(sys, "frozen", False):
    sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 "..", "idm-quota-monitor"))

import idm_win as backend
import speed_core

APP_NAME   = "IDM Quota Monitor"
APP_VERSION = "2.0"
REFRESH_MS = 15 * 60 * 1000   # 15 minutes

# Resolve paths whether running as script or frozen .exe
BASE_DIR   = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
LOGO_PATH  = os.path.join(BASE_DIR, "logo.png")
# When frozen, load the icon from the exe itself (already embedded as PE resource).
# When running as a script, fall back to the .ico file next to main.py.
ICON_PATH  = sys.executable if getattr(sys, "frozen", False) \
             else os.path.join(os.path.dirname(os.path.abspath(__file__)), "IDMLB.ico")
STARTUP_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
STARTUP_NAME = "IDMQuotaMonitor"


# -- Colours ------------------------------------------------------------------

BG      = "#1e2130"
BG_CARD = "#252840"
SEP     = "#2e3250"
GREEN   = "#2ecc71"
ORANGE  = "#f39c12"
RED     = "#e74c3c"
BLUE    = "#3b82f6"
TEXT    = "#e0e4f0"
MUTED   = "#6b7280"


# -- Startup registry helpers -------------------------------------------------

def _startup_exe() -> str:
    """Return the path to register: the frozen .exe or the script itself."""
    return sys.executable if getattr(sys, "frozen", False) else os.path.abspath(__file__)


def is_startup_enabled() -> bool:
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, STARTUP_KEY) as k:
            winreg.QueryValueEx(k, STARTUP_NAME)
            return True
    except Exception:
        return False


def set_startup(enabled: bool):
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, STARTUP_KEY,
                            0, winreg.KEY_SET_VALUE) as k:
            if enabled:
                winreg.SetValueEx(k, STARTUP_NAME, 0, winreg.REG_SZ,
                                  f'"{_startup_exe()}"')
            else:
                try:
                    winreg.DeleteValue(k, STARTUP_NAME)
                except FileNotFoundError:
                    pass
    except Exception as e:
        print(f"[startup] {e}", file=sys.stderr)


def pct_color(pct):
    if pct is None: return MUTED
    if pct >= 90:   return RED
    if pct >= 70:   return ORANGE
    return GREEN


# -- Background threads -------------------------------------------------------

class FetchThread(QThread):
    done  = pyqtSignal(dict)
    error = pyqtSignal(str)

    def run(self):
        try:
            self.done.emit(backend.fetch_all())
        except Exception as e:
            self.error.emit(str(e))


_running_threads = set()


class ListThread(QThread):
    done  = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, credentials):
        super().__init__()
        self._credentials = credentials
        # A QThread destroyed while running aborts the process; the dialog may close first.
        _running_threads.add(self)
        self.finished.connect(lambda: _running_threads.discard(self))

    def run(self):
        try:
            self.done.emit(backend.list_services(self._credentials))
        except Exception as e:
            self.error.emit(str(e))


class SpeedThread(QThread):
    progress = pyqtSignal(dict)

    def __init__(self, test, parent=None):
        super().__init__(parent)
        self._test = test

    def run(self):
        speed_core.run(self.progress.emit, self._test)


# -- Gauge widget -------------------------------------------------------------

class GaugeWidget(QWidget):
    SIZES = {"speedometer": (140, 140), "simple": (280, 160)}

    def __init__(self, style="speedometer", parent=None):
        super().__init__(parent)
        self._pct   = 0.0
        self._color = GREEN
        self._label = "-"
        self._style = style
        self.font_pt = 14
        self.set_style(style)

    def set_style(self, style):
        self._style = style
        self.setFixedSize(*self.SIZES[style])
        self.update()

    def set_data(self, pct, color, label):
        self._pct   = pct or 0.0
        self._color = color
        self._label = label
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        if self._style == "simple":
            self._paint_simple(p)
        else:
            self._paint_speedometer(p)

    def _paint_speedometer(self, p):
        cx, cy = self.width() / 2, self.height() / 2
        r      = min(cx, cy) - 10
        rect   = QRectF(cx - r, cy - r, r * 2, r * 2)

        for i in range(11):
            a     = math.radians(225 - 270 * i / 10)
            inner = r - (15 if i % 5 == 0 else 11)
            p.setPen(QPen(QColor(255, 255, 255, 90 if i % 5 == 0 else 45), 1))
            p.drawLine(QPointF(cx + math.cos(a) * inner, cy - math.sin(a) * inner),
                       QPointF(cx + math.cos(a) * (r - 8), cy - math.sin(a) * (r - 8)))

        p.setPen(QPen(QColor(255, 255, 255, 25), 10, Qt.SolidLine, Qt.RoundCap))
        p.drawArc(rect, 225 * 16, -270 * 16)

        if self._pct > 0:
            p.setPen(QPen(QColor(self._color), 10, Qt.SolidLine, Qt.RoundCap))
            p.drawArc(rect, 225 * 16, int(-270 * 16 * self._pct / 100))

        a = math.radians(225 - 270 * min(self._pct, 100) / 100)
        tip = r - 22
        p.setPen(QPen(QColor(self._color), 2, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(cx - math.cos(a) * 8, cy + math.sin(a) * 8),
                   QPointF(cx + math.cos(a) * tip, cy - math.sin(a) * tip))
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(self._color))
        p.drawEllipse(QPointF(cx, cy), 4, 4)

        p.setPen(QColor(self._color))
        p.setFont(QFont("Segoe UI", self.font_pt, QFont.Bold))
        p.drawText(QRectF(0, cy + r * 0.35, self.width(), 26),
                   Qt.AlignHCenter, self._label)

    def _paint_simple(self, p):
        stroke = max(12, round(self.width() * 0.07))
        cx = self.width() / 2
        cy = self.height() - stroke
        r  = cx - stroke
        rect = QRectF(cx - r, cy - r, r * 2, r * 2)

        p.setPen(QPen(QColor(255, 255, 255, 25), stroke, Qt.SolidLine, Qt.RoundCap))
        p.drawArc(rect, 180 * 16, -180 * 16)

        if self._pct > 0:
            p.setPen(QPen(QColor(self._color), stroke, Qt.SolidLine, Qt.RoundCap))
            p.drawArc(rect, 180 * 16, int(-180 * 16 * min(self._pct, 100) / 100))

        pt = max(self.font_pt, int(r * 0.24))
        h = pt * 2
        p.setPen(QColor(self._color))
        p.setFont(QFont("Segoe UI", pt, QFont.Bold))
        p.drawText(QRectF(0, cy - r * 0.34 - h / 2, self.width(), h),
                   Qt.AlignCenter, self._label)


# -- Single service card ------------------------------------------------------

class ConnectionTab(QWidget):
    def __init__(self, style="speedometer", parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background:{BG};")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 12, 16, 12)
        outer.setSpacing(6)
        outer.addStretch()

        self.hdr_lbl = QLabel("")
        self.hdr_lbl.setAlignment(Qt.AlignCenter)
        self.hdr_lbl.setStyleSheet(
            f"color:{MUTED}; font-size:11px; font-weight:bold; letter-spacing:2px;")
        outer.addWidget(self.hdr_lbl)

        self.gauge = GaugeWidget(style)

        def shdr(text):
            l = QLabel(text)
            l.setStyleSheet(f"color:{MUTED}; font-size:10px; margin-top:6px;")
            return l

        def val(size=13, bold=False):
            l = QLabel("-")
            l.setStyleSheet(
                f"color:{TEXT}; font-size:{size}px;"
                f" font-weight:{'bold' if bold else 'normal'};")
            return l

        self.lbl_rem = val(13, bold=True)
        self.lbl_upd = val(12)
        self.lbl_exp = val(12, bold=True)
        self.lbl_exp_line = QLabel("")
        self.lbl_exp_line.setStyleSheet(f"color:{MUTED}; font-size:10px;")

        groups = []
        for title, widgets in (("Remaining", [self.lbl_rem]), ("Updated", [self.lbl_upd]),
                               ("Expires In", [self.lbl_exp, self.lbl_exp_line])):
            group = QVBoxLayout()
            group.setSpacing(0)
            group.addWidget(shdr(title))
            for w in widgets:
                group.addWidget(w)
            group.addStretch()
            groups.append(group)

        if style == "simple":
            outer.addWidget(self.gauge, 0, Qt.AlignHCenter)
            stats = QHBoxLayout()
            stats.setSpacing(24)
            stats.addStretch()
            for group in groups:
                stats.addLayout(group)
            stats.addStretch()
            outer.addLayout(stats)
        else:
            row = QHBoxLayout()
            row.setSpacing(16)
            row.addStretch()
            row.addWidget(self.gauge, 0, Qt.AlignVCenter)
            stats = QVBoxLayout()
            stats.setSpacing(0)
            stats.setContentsMargins(0, 0, 0, 0)
            for group in groups:
                stats.addLayout(group)
            stats.addStretch()
            row.addLayout(stats)
            row.addStretch()
            outer.addLayout(row)
        outer.addStretch()

    def refresh(self, svc: dict, loading: bool, alias: str):
        self.hdr_lbl.setText(alias or f"{backend.type_label(svc.get('type'))}  {svc.get('name', '')}")
        pct   = svc.get("percent") or 0
        color = pct_color(pct)

        if loading:
            self.gauge.set_data(0, MUTED, "...")
            self.lbl_rem.setText("Loading...")
            self.lbl_rem.setStyleSheet(f"color:{MUTED}; font-size:13px;")
        elif svc.get("error"):
            self.gauge.set_data(0, RED, "ERR")
            self.lbl_rem.setText(svc["error"])
            self.lbl_rem.setStyleSheet(f"color:{RED}; font-size:11px; font-weight:bold;")
        else:
            self.gauge.set_data(pct, color, f"{pct:.1f}%")
            self.lbl_rem.setText(svc.get("remaining") or "-")
            self.lbl_rem.setStyleSheet(
                f"color:{TEXT}; font-size:13px; font-weight:bold;")

        self.lbl_upd.setText(svc.get("updated") or "-")

        state = backend.expiry_state(svc.get("expiry_iso"), datetime.now())
        exp_color = {"expired": RED, "soon": ORANGE}.get(state["level"], TEXT)
        self.lbl_exp.setText(state["text"])
        self.lbl_exp.setStyleSheet(
            f"color:{exp_color}; font-size:12px; font-weight:bold;")
        self.lbl_exp_line.setText(state["line"])


# -- Settings dialog ----------------------------------------------------------

class SettingsDialog(QDialog):
    saved = pyqtSignal()

    def __init__(self, prefs, parent=None):
        super().__init__(parent)
        self._prefs = prefs
        self._services = []
        self._checks = []
        self._rows = []
        self._aliases = {}
        self._selected = list(prefs.selected)
        self._names = dict(prefs.names)
        self._thread = None

        self.setWindowTitle("Settings")
        self.setFixedWidth(400)
        self.setStyleSheet(f"""
            QDialog   {{ background:{BG_CARD}; color:{TEXT}; }}
            QLabel    {{ color:{TEXT}; }}
            QLineEdit {{ background:#1a1d2e; color:{TEXT};
                         border:1px solid {SEP}; border-radius:4px; padding:6px; }}
            QComboBox {{ background:#1a1d2e; color:{TEXT};
                         border:1px solid {SEP}; border-radius:4px; padding:4px 6px; }}
            QCheckBox {{ color:{TEXT}; }}
            QPushButton {{ background:{BG}; color:{TEXT};
                           border:1px solid {SEP}; border-radius:4px; padding:5px 12px; }}
            QPushButton:disabled {{ color:{MUTED}; }}
        """)

        form = QFormLayout(self)
        form.setSpacing(10)
        form.setContentsMargins(20, 20, 20, 20)

        self.u_edit = QLineEdit()
        self.p_edit = QLineEdit()
        self.p_edit.setEchoMode(QLineEdit.Password)

        try:
            cfg = backend.read_config()
            self.u_edit.setText(cfg.get("username", ""))
            self.p_edit.setText(cfg.get("password", ""))
        except Exception:
            pass

        form.addRow("Username:", self.u_edit)
        form.addRow("Password:", self.p_edit)

        self.detect_btn = QPushButton("Detect services")
        self.detect_btn.clicked.connect(self._detect)
        self.status_lbl = QLabel("")
        self.status_lbl.setStyleSheet(f"color:{MUTED}; font-size:10px;")
        form.addRow(self.detect_btn, self.status_lbl)

        self.checks_box = QVBoxLayout()
        form.addRow(f"Show (max {backend.MAX_SHOWN}):", self.checks_box)
        hint = QLabel("Tick to show. Type a name to rename a service.")
        hint.setStyleSheet(f"color:{MUTED}; font-size:10px;")
        form.addRow(hint)

        self.style_combo = QComboBox()
        self.style_combo.addItem("Speedometer", "speedometer")
        self.style_combo.addItem("Simple", "simple")
        self.style_combo.setCurrentIndex(self.style_combo.findData(prefs.gauge_style))
        form.addRow("Usage gauge:", self.style_combo)

        self.startup_chk = QCheckBox("Launch on Windows startup")
        self.startup_chk.setStyleSheet(f"color:{TEXT}; font-size:11px; margin-top:8px;")
        self.startup_chk.setChecked(is_startup_enabled())
        form.addRow(self.startup_chk)

        btns = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        form.addRow(btns)

        if self.u_edit.text() and self.p_edit.text():
            self._detect()

    def _detect(self):
        u, p = self.u_edit.text().strip(), self.p_edit.text().strip()
        if not u or not p:
            self.status_lbl.setText("Enter username and password first")
            return
        self.detect_btn.setEnabled(False)
        self.status_lbl.setText("Detecting services...")
        self._thread = ListThread((u, p))
        self._thread.done.connect(self._on_listed)
        self._thread.error.connect(self._on_list_error)
        self._thread.start()

    def _on_list_error(self, msg):
        self.detect_btn.setEnabled(True)
        self.status_lbl.setText(msg)

    def _on_listed(self, data):
        self.detect_btn.setEnabled(True)
        self._services = data["services"]
        n = len(self._services)
        self.status_lbl.setText(f"{n} service{'' if n == 1 else 's'} found")

        ids = [s["id"] for s in self._services]
        kept = [i for i in self._selected if i in ids] or ids[:backend.MAX_SHOWN]

        while self._rows:
            row = self._rows.pop()
            row.setParent(None)
            row.deleteLater()
        self._checks.clear()
        self._aliases.clear()
        for svc in self._services:
            row = QWidget()
            lay = QHBoxLayout(row)
            lay.setContentsMargins(0, 0, 0, 0)
            chk = QCheckBox(backend.type_label(svc["type"]))
            chk.setProperty("service_id", svc["id"])
            chk.setChecked(svc["id"] in kept)
            chk.toggled.connect(self._update_caps)
            alias = QLineEdit(self._names.get(svc["id"], ""))
            alias.setPlaceholderText(svc["name"])
            lay.addWidget(chk)
            lay.addWidget(alias, 1)
            self.checks_box.addWidget(row)
            self._rows.append(row)
            self._checks.append(chk)
            self._aliases[svc["id"]] = alias
        self._update_caps()

    def _update_caps(self):
        full = sum(c.isChecked() for c in self._checks) >= backend.MAX_SHOWN
        for c in self._checks:
            c.setEnabled(c.isChecked() or not full)

    def _save(self):
        u = self.u_edit.text().strip()
        p = self.p_edit.text().strip()
        if u and p:
            backend.write_config(u, p)
        if self._checks:
            self._prefs.selected = [c.property("service_id") for c in self._checks if c.isChecked()]
            names = {sid: edit.text().strip() for sid, edit in self._aliases.items() if edit.text().strip()}
            self._prefs.names = names
        self._prefs.gauge_style = self.style_combo.currentData()
        set_startup(self.startup_chk.isChecked())
        self.saved.emit()
        self.accept()


# -- Speed test dialog --------------------------------------------------------

class SpeedGauge(QWidget):
    """Speedometer with an animated needle on the speedtest.net-style scale."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(320, 260)
        self._needle = 0.0
        self._color  = BLUE
        self._text   = "-"
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(450)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.valueChanged.connect(self._set_needle)

    def _set_needle(self, value):
        self._needle = value
        self.update()

    def move_to(self, fraction):
        self._anim.stop()
        self._anim.setStartValue(float(self._needle))
        self._anim.setEndValue(float(fraction))
        self._anim.start()

    def set_look(self, color, text):
        self._color, self._text = color, text
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        cx, cy = self.width() / 2, self.height() / 2 + 4
        r = min(cx, cy) - 38
        rect = QRectF(cx - r, cy - r, r * 2, r * 2)

        p.setPen(QPen(QColor(255, 255, 255, 25), 12, Qt.SolidLine, Qt.RoundCap))
        p.drawArc(rect, 225 * 16, -270 * 16)
        if self._needle > 0.002:
            p.setPen(QPen(QColor(self._color), 12, Qt.SolidLine, Qt.RoundCap))
            p.drawArc(rect, 225 * 16, int(-270 * 16 * self._needle))

        marks = speed_core.SCALE
        p.setFont(QFont("Segoe UI", 8))
        for i, mark in enumerate(marks):
            a = math.radians(225 - 270 * i / (len(marks) - 1))
            p.setPen(QPen(QColor(255, 255, 255, 100), 2))
            p.drawLine(QPointF(cx + math.cos(a) * (r - 16), cy - math.sin(a) * (r - 16)),
                       QPointF(cx + math.cos(a) * (r - 8), cy - math.sin(a) * (r - 8)))
            p.setPen(QColor(MUTED))
            lx, ly = cx + math.cos(a) * (r + 24), cy - math.sin(a) * (r + 24)
            p.drawText(QRectF(lx - 20, ly - 8, 40, 16), Qt.AlignCenter, str(mark))

        a = math.radians(225 - 270 * self._needle)
        tip = r - 22
        p.setPen(QPen(QColor(self._color), 3, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(cx - math.cos(a) * 14, cy + math.sin(a) * 14),
                   QPointF(cx + math.cos(a) * tip, cy - math.sin(a) * tip))
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(self._color))
        p.drawEllipse(QPointF(cx, cy), 7, 7)

        p.setPen(QColor(self._color))
        p.setFont(QFont("Segoe UI", 26, QFont.Bold))
        p.drawText(QRectF(0, cy + r * 0.38, self.width(), 40), Qt.AlignCenter, self._text)
        p.setPen(QColor(MUTED))
        p.setFont(QFont("Segoe UI", 9))
        p.drawText(QRectF(0, cy + r * 0.38 + 38, self.width(), 16), Qt.AlignCenter, "Mbps")


class SpeedPanel(QWidget):
    """One independent speedometer with its own Start button."""
    startRequested = pyqtSignal()

    def __init__(self, title, color, parent=None):
        super().__init__(parent)
        self._color = color
        lay = QVBoxLayout(self)
        lay.setSpacing(8)

        self.title = QLabel(title)
        self.title.setAlignment(Qt.AlignCenter)
        self.title.setStyleSheet(f"color:{color}; font-size:15px; font-weight:bold; letter-spacing:2px;")
        lay.addWidget(self.title)

        self.gauge = SpeedGauge()
        lay.addWidget(self.gauge, 0, Qt.AlignHCenter)

        self.caption = QLabel("Ready")
        self.caption.setAlignment(Qt.AlignCenter)
        self.caption.setWordWrap(True)
        lay.addWidget(self.caption)

        self.button = QPushButton("Start")
        self.button.clicked.connect(self.startRequested)
        lay.addWidget(self.button, 0, Qt.AlignHCenter)

        self.reset()

    def reset(self):
        self.show_value(None)

    def show_value(self, value):
        self.gauge.move_to(speed_core.scale_fraction(value))
        self.gauge.set_look(self._color, "-" if value is None else f"{value:.1f}")

    def set_caption(self, text, error=False):
        self.caption.setText(text)
        self.caption.setStyleSheet(f"color:{RED if error else TEXT}; font-size:13px;")

    def set_button(self, text, enabled):
        self.button.setText(text)
        self.button.setEnabled(enabled)


class SpeedTestDialog(QDialog):
    PHASE_CAPTIONS = {
        "config": "Contacting speedtest.net", "server": "Choosing the best server",
        "ping": "Measuring latency",
    }
    DOWNLOAD_COLOR = "#22d3ee"
    UPLOAD_COLOR   = "#a855f7"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Internet Speed Test")
        self._thread = None
        self._active = None
        self.setStyleSheet(f"""
            QDialog {{ background:{BG_CARD}; color:{TEXT}; }}
            QLabel  {{ color:{TEXT}; font-size:13px; }}
            QPushButton {{ background:{BG}; color:{TEXT};
                           border:1px solid {SEP}; border-radius:4px; padding:6px 16px; }}
            QPushButton:disabled {{ color:{MUTED}; }}
        """)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(10)

        row = QHBoxLayout()
        row.setSpacing(20)
        self.panels = {
            "download": SpeedPanel("DOWNLOAD", self.DOWNLOAD_COLOR),
            "upload":   SpeedPanel("UPLOAD", self.UPLOAD_COLOR),
        }
        for kind, panel in self.panels.items():
            panel.startRequested.connect(lambda k=kind: self._start(k))
            row.addWidget(panel, 1)
            if kind == "download":
                line = QFrame()
                line.setFrameShape(QFrame.VLine)
                line.setStyleSheet(f"color:{SEP};")
                row.addWidget(line)
        lay.addLayout(row)

        self.info_lbl = QLabel("")
        self.info_lbl.setAlignment(Qt.AlignCenter)
        self.info_lbl.setStyleSheet(f"color:{MUTED}; font-size:11px;")
        lay.addWidget(self.info_lbl)

        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.reject)
        lay.addWidget(self.close_btn, 0, Qt.AlignHCenter)

    def _start(self, kind):
        self._active = kind
        for k, panel in self.panels.items():
            panel.set_button("Testing..." if k == kind else panel.button.text(), False)
        self.close_btn.setEnabled(False)
        self.panels[kind].show_value(None)
        self.panels[kind].set_caption("Contacting speedtest.net")
        self._thread = SpeedThread(kind, self)
        self._thread.progress.connect(self._on_progress)
        self._thread.finished.connect(self._finished)
        self._thread.start()

    def _finished(self):
        self._active = None
        for panel in self.panels.values():
            done = panel.caption.text() != "Ready"
            panel.set_button("Run again" if done else "Start", True)
        self.close_btn.setEnabled(True)

    def reject(self):
        if self._active is None:
            super().reject()

    def _on_progress(self, s):
        if self._active is None:
            return
        panel, phase = self.panels[self._active], s["phase"]
        if s["ping"] is not None:
            self.info_lbl.setText(f"Ping {s['ping']} ms   Server: {s['server']}")
        if phase == "error":
            panel.show_value(None)
            panel.set_caption(s["error"], error=True)
        elif phase == "done":
            panel.show_value(s[self._active])
            panel.set_caption("Complete")
        else:
            panel.show_value(s["live"])
            panel.set_caption(self.PHASE_CAPTIONS.get(phase, f"Testing {self._active}"))


# -- Main window --------------------------------------------------------------

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.prefs = backend.Settings()
        self.services = []
        self._error = ""
        self._loading = False
        self._thread = None
        self._tray = None

        self.setWindowTitle(f"{APP_NAME} {APP_VERSION}")
        self.setMinimumSize(620, 300)
        self.resize(1000, 330)
        self.setStyleSheet(f"QMainWindow {{ background:{BG}; color:{TEXT}; }}")
        if os.path.exists(ICON_PATH):
            self.setWindowIcon(QIcon(ICON_PATH))

        central = QWidget()
        self.setCentralWidget(central)
        vbox = QVBoxLayout(central)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)

        self.body = QWidget()
        self.body.setStyleSheet(f"background:{BG};")
        self.row = QHBoxLayout(self.body)
        self.row.setContentsMargins(0, 0, 0, 0)
        self.row.setSpacing(0)
        vbox.addWidget(self.body, 1)

        self.corner_logo = QLabel(self.body)
        self.corner_logo.setFixedSize(56, 28)
        self.corner_logo.setStyleSheet("background:transparent;")
        if os.path.exists(LOGO_PATH):
            self.corner_logo.setPixmap(QPixmap(LOGO_PATH).scaled(
                56, 28, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.corner_logo.move(10, 8)
        self.corner_logo.hide()

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"color:{SEP}; background:{SEP};")
        sep.setFixedHeight(1)
        vbox.addWidget(sep)

        footer = QHBoxLayout()
        footer.setContentsMargins(12, 6, 12, 6)

        self.status_lbl = QLabel("")
        self.status_lbl.setStyleSheet(f"color:{MUTED}; font-size:10px;")
        footer.addWidget(self.status_lbl)
        footer.addStretch()

        btn_style = (f"QPushButton {{ background:{BG_CARD}; color:{TEXT};"
                     f" border:1px solid {SEP}; border-radius:4px;"
                     f" padding:5px 14px; font-size:11px; }}"
                     f"QPushButton:hover {{ background:{SEP}; }}"
                     f"QPushButton:disabled {{ color:{MUTED}; }}")

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.setStyleSheet(btn_style)
        self.refresh_btn.clicked.connect(self.do_refresh)
        footer.addWidget(self.refresh_btn)

        speed_btn = QPushButton("Speed Test")
        speed_btn.setStyleSheet(btn_style)
        speed_btn.clicked.connect(lambda: SpeedTestDialog(self).exec_())
        footer.addWidget(speed_btn)

        settings_btn = QPushButton("Settings")
        settings_btn.setStyleSheet(btn_style)
        settings_btn.clicked.connect(self._open_settings)
        footer.addWidget(settings_btn)

        vbox.addLayout(footer)

        self._timer = QTimer(self)
        self._timer.setInterval(REFRESH_MS)
        self._timer.timeout.connect(self.do_refresh)
        self._timer.start()

        self.do_refresh()

    def shown(self):
        return backend.shown_services(self.services, self.prefs.selected)

    def _clear_row(self):
        while self.row.count():
            widget = self.row.takeAt(0).widget()
            if widget:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()

    def _logo(self):
        logo = QLabel()
        logo.setFixedWidth(200)
        logo.setAlignment(Qt.AlignCenter)
        logo.setStyleSheet(f"background:{BG};")
        if os.path.exists(LOGO_PATH):
            logo.setPixmap(QPixmap(LOGO_PATH).scaled(
                180, 90, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        return logo

    def _vline(self):
        line = QFrame()
        line.setFrameShape(QFrame.VLine)
        line.setStyleSheet(f"color:{SEP};")
        return line

    def _render(self):
        self._clear_row()
        shown = self.shown()
        self.corner_logo.setVisible(len(shown) == 3)
        if not shown:
            msg = ("Loading..." if self._loading
                   else self._error or "No services selected. Open Settings and tick the services to show.")
            lbl = QLabel(msg)
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setWordWrap(True)
            lbl.setStyleSheet(f"color:{RED if self._error and not self._loading else MUTED}; font-size:14px;")
            self.row.addWidget(lbl, 1)
            return
        style = self.prefs.gauge_style
        for i, svc in enumerate(shown):
            tab = ConnectionTab(style)
            tab.refresh(svc, self._loading, self.prefs.names.get(svc["id"], ""))
            if i > 0:
                self.row.addWidget(self._vline())
                if len(shown) == 2:
                    self.row.addWidget(self._logo())
                    self.row.addWidget(self._vline())
            self.row.addWidget(tab, 1)
        self.corner_logo.raise_()

    def do_refresh(self):
        if self._loading:
            return
        self._loading = True
        self.refresh_btn.setEnabled(False)
        self.refresh_btn.setText("Loading...")
        self.status_lbl.setText("Fetching...")
        self._render()

        self._thread = FetchThread(self)
        self._thread.done.connect(self._on_done)
        self._thread.error.connect(self._on_error)
        self._thread.start()

    def _finish_refresh(self):
        self._loading = False
        self.refresh_btn.setEnabled(True)
        self.refresh_btn.setText("Refresh")

    def _on_done(self, data: dict):
        self._finish_refresh()
        self.services = data["services"]
        self._error = ""
        self.status_lbl.setText(
            f"Updated {self.services[0].get('updated', '')}" if self.services else "")
        self._render()
        if self._tray:
            self._tray.update_data()

    def _on_error(self, msg: str):
        self._finish_refresh()
        self.services = []
        self._error = msg
        self.status_lbl.setText(f"Error: {msg}")
        self._render()
        if self._tray:
            self._tray.update_data()

    def _open_settings(self):
        dlg = SettingsDialog(self.prefs, self)
        dlg.saved.connect(self.do_refresh)
        dlg.exec_()

    def closeEvent(self, event):
        event.ignore()
        self.hide()


# -- System tray --------------------------------------------------------------

class TrayIcon(QSystemTrayIcon):
    def __init__(self, window: MainWindow):
        super().__init__()
        self._window = window
        window._tray = self

        self._active = None   # id of the service the icon currently shows

        self.setIcon(QIcon(ICON_PATH) if os.path.exists(ICON_PATH) else self._make_icon(None, ""))
        self.setToolTip(APP_NAME)

        menu = QMenu()
        menu.setStyleSheet(f"""
            QMenu {{ background:{BG_CARD}; color:{TEXT};
                     border:1px solid {SEP}; padding:4px; }}
            QMenu::item {{ padding:6px 20px; }}
            QMenu::item:selected {{ background:{SEP}; }}
            QMenu::separator {{ background:{SEP}; height:1px; margin:4px 8px; }}
        """)

        self._svc_acts = []
        for _ in range(backend.MAX_SHOWN):
            act = QAction("", menu)
            act.setEnabled(False)
            act.setVisible(False)
            menu.addAction(act)
            self._svc_acts.append(act)
        menu.addSeparator()

        open_act = QAction("Open",    menu); open_act.triggered.connect(self._show)
        ref_act  = QAction("Refresh", menu); ref_act.triggered.connect(window.do_refresh)
        menu.addAction(open_act)
        menu.addAction(ref_act)
        menu.addSeparator()

        quit_act = QAction("Quit", menu)
        quit_act.triggered.connect(QApplication.instance().quit)
        menu.addAction(quit_act)

        self.setContextMenu(menu)
        self.activated.connect(self._on_activate)
        self.show()

    def _active_service(self, shown):
        return next((s for s in shown if s["id"] == self._active), shown[0] if shown else None)

    def _on_activate(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            shown = self._window.shown()
            if len(shown) > 1:
                ids = [s["id"] for s in shown]
                current = self._active_service(shown)["id"]
                self._active = ids[(ids.index(current) + 1) % len(ids)]
            self.update_data()

    def _show(self):
        self._window.show()
        self._window.raise_()
        self._window.activateWindow()

    def update_data(self):
        shown = self._window.shown()
        for act, svc in zip(self._svc_acts, shown + [None] * backend.MAX_SHOWN):
            act.setVisible(svc is not None)
            if svc is not None:
                pct = svc.get("percent")
                act.setText(f"{backend.type_label(svc['type'])} {backend.display_name(svc, self._window.prefs.names)}: "
                            + (f"{pct:.1f}%  {svc.get('remaining') or ''}" if pct is not None else "-"))

        svc = self._active_service(shown)
        if svc is None:
            self.setIcon(self._make_icon(None, ""))
            self.setToolTip(APP_NAME)
            return
        pct   = svc.get("percent")
        label = backend.type_label(svc["type"])
        self.setIcon(self._make_icon(pct, label))
        self.setToolTip(
            f"{APP_NAME}  [{label} {backend.display_name(svc, self._window.prefs.names)}]\n"
            f"{pct:.1f}%  {svc.get('remaining') or ''}\n"
            f"Click icon to switch service"
            if pct is not None else APP_NAME)

    def _make_icon(self, pct, label):
        """Draw a 64x64 single-arc tray icon for the active service."""
        sz   = 64
        pix  = QPixmap(sz, sz)
        pix.fill(Qt.transparent)
        p    = QPainter(pix)
        p.setRenderHint(QPainter.Antialiasing)

        color = pct_color(pct)
        rect  = QRectF(5, 5, 54, 54)

        p.setPen(QPen(QColor(255, 255, 255, 30), 8, Qt.SolidLine, Qt.RoundCap))
        p.drawArc(rect, 225 * 16, -270 * 16)

        if pct is not None and pct > 0:
            p.setPen(QPen(QColor(color), 8, Qt.SolidLine, Qt.RoundCap))
            p.drawArc(rect, 225 * 16, int(-270 * 16 * pct / 100))

        if pct is not None:
            p.setPen(QColor(color))
            p.setFont(QFont("Arial", 12, QFont.Bold))
            p.drawText(QRectF(0, 0, sz, sz), Qt.AlignCenter, f"{int(pct)}%")

        p.setPen(QColor(MUTED))
        p.setFont(QFont("Arial", 7))
        p.drawText(QRectF(0, sz - 14, sz, 12), Qt.AlignHCenter, label)

        p.end()
        return QIcon(pix)


# -- Entry point --------------------------------------------------------------

def main():
    # DPI awareness for Win8.1+
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setQuitOnLastWindowClosed(False)
    app.setStyle("Fusion")             # consistent look across all Windows versions
    app.setStyleSheet(
        "QWidget { font-family: 'Segoe UI', Arial, sans-serif; font-size: 11px; }")

    if os.path.exists(ICON_PATH):
        app.setWindowIcon(QIcon(ICON_PATH))

    if not QSystemTrayIcon.isSystemTrayAvailable():
        print("No system tray available.", file=sys.stderr)

    window = MainWindow()
    TrayIcon(window)

    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
