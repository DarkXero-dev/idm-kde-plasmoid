#!/usr/bin/env python3
"""
IDM Quota Monitor — Windows (PyQt5 / Qt 5.15)
Supports Windows 7 SP1 → 11
System tray icon + popup window
"""

import sys, os, math
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QTabWidget,
    QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QPushButton, QDialog, QLineEdit, QFormLayout,
    QDialogButtonBox, QSystemTrayIcon, QMenu, QAction,
    QSizePolicy, QGraphicsOpacityEffect, QCheckBox,
)
from PyQt5.QtGui  import (
    QPainter, QColor, QPen, QFont, QLinearGradient,
    QPainterPath, QIcon, QPixmap,
)
from PyQt5.QtCore import (
    Qt, QTimer, QThread, pyqtSignal, QPointF, QRectF, QSize,
)

import fetch_quota as fq

APP_NAME   = "IDM Quota Monitor"
REFRESH_MS = 15 * 60 * 1000   # 15 minutes

# Resolve paths whether running as script or frozen .exe
BASE_DIR   = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
LOGO_PATH  = os.path.join(BASE_DIR, "logo.png")
ICON_PATH  = os.path.join(BASE_DIR, "IDMLB.ico")
STARTUP_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
STARTUP_NAME = "IDMQuotaMonitor"


# ── Colours ───────────────────────────────────────────────────────────────────

BG      = "#1e2130"
BG_CARD = "#252840"
SEP     = "#2e3250"
GREEN   = "#2ecc71"
ORANGE  = "#f39c12"
RED     = "#e74c3c"
BLUE    = "#3b82f6"
TEXT    = "#e0e4f0"
MUTED   = "#6b7280"


# ── Startup registry helpers ──────────────────────────────────────────────────

def _startup_exe() -> str:
    """Return the path to register — the frozen .exe or the script itself."""
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


# ── Background fetch thread ───────────────────────────────────────────────────

class FetchThread(QThread):
    done  = pyqtSignal(dict)
    error = pyqtSignal(str)

    def run(self):
        try:
            self.done.emit(fq.fetch_all())
        except Exception as e:
            self.error.emit(str(e))


# ── Circular gauge widget ─────────────────────────────────────────────────────

class GaugeWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._pct   = 0.0
        self._color = GREEN
        self._label = "—"
        self.setFixedSize(130, 130)

    def set_data(self, pct, color, label):
        self._pct   = pct or 0.0
        self._color = color
        self._label = label
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        cx, cy = self.width() / 2, self.height() / 2
        r      = min(cx, cy) - 10
        rect   = QRectF(cx - r, cy - r, r * 2, r * 2)

        # Track (faint)
        p.setPen(QPen(QColor(255, 255, 255, 25), 10, Qt.SolidLine, Qt.RoundCap))
        p.drawArc(rect, 225 * 16, -270 * 16)

        # Filled arc
        if self._pct > 0:
            p.setPen(QPen(QColor(self._color), 10, Qt.SolidLine, Qt.RoundCap))
            p.drawArc(rect, 225 * 16, int(-270 * 16 * self._pct / 100))

        # Percentage label
        p.setPen(QColor(self._color))
        p.setFont(QFont("Segoe UI", 14, QFont.Bold))
        p.drawText(QRectF(0, cy - 20, self.width(), 26),
                   Qt.AlignHCenter, self._label)

        # "used" sub-label
        p.setPen(QColor(MUTED))
        p.setFont(QFont("Segoe UI", 8))
        p.drawText(QRectF(0, cy + 8, self.width(), 18),
                   Qt.AlignHCenter, "used")


# ── Gradient "CURRENT PROVIDER" label ────────────────────────────────────────

class GradientLabel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        grad = QLinearGradient(0, 0, self.width(), 0)
        grad.setColorAt(0.0, QColor(BLUE))
        grad.setColorAt(1.0, QColor(RED))

        p.setPen(Qt.NoPen)
        # Use gradient as brush for text via path
        f = QFont("Segoe UI", 20, QFont.Bold)
        f.setLetterSpacing(QFont.AbsoluteSpacing, 3)
        p.setFont(f)

        fm   = p.fontMetrics()
        line1, line2 = "CURRENT", "PROVIDER"
        lh   = fm.height()
        gap  = 6
        total_h = lh * 2 + gap
        y1   = (self.height() - total_h) / 2 + lh
        y2   = y1 + lh + gap

        path = QPainterPath()
        path.addText(QPointF((self.width() - fm.horizontalAdvance(line1)) / 2, y1), f, line1)
        path.addText(QPointF((self.width() - fm.horizontalAdvance(line2)) / 2, y2), f, line2)

        p.setOpacity(0.28)
        p.fillPath(path, grad)


# ── Single connection tab ─────────────────────────────────────────────────────

class ConnectionTab(QWidget):
    def __init__(self, label="", parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background:{BG};")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 12, 16, 12)
        outer.setSpacing(6)

        # Service label header
        hdr_lbl = QLabel(label)
        hdr_lbl.setAlignment(Qt.AlignCenter)
        hdr_lbl.setStyleSheet(
            f"color:{MUTED}; font-size:11px; font-weight:bold; letter-spacing:2px;")
        outer.addWidget(hdr_lbl)

        # Gauge + stats row, centered
        row = QHBoxLayout()
        row.setSpacing(16)
        row.addStretch()

        self.gauge = GaugeWidget()
        row.addWidget(self.gauge, 0, Qt.AlignVCenter)

        # Stats
        stats = QVBoxLayout()
        stats.setSpacing(0)
        stats.setContentsMargins(0, 0, 0, 0)

        def shdr(text):
            l = QLabel(text)
            l.setStyleSheet(f"color:{MUTED}; font-size:10px; margin-top:6px;")
            return l

        def val(size=13, bold=False):
            l = QLabel("—")
            l.setStyleSheet(
                f"color:{TEXT}; font-size:{size}px;"
                f" font-weight:{'bold' if bold else 'normal'};")
            return l

        self.lbl_rem = val(13, bold=True)
        self.lbl_upd = val(12)
        self.lbl_exp = val(12, bold=True)

        for h, v in (("Remaining",  self.lbl_rem),
                     ("Updated",    self.lbl_upd),
                     ("Expires In", self.lbl_exp)):
            stats.addWidget(shdr(h))
            stats.addWidget(v)

        stats.addStretch()
        row.addLayout(stats)
        row.addStretch()
        outer.addLayout(row)
        outer.addStretch()

    def refresh(self, data: dict, loading: bool):
        pct   = data.get("percent") or 0
        color = pct_color(pct)

        if loading:
            self.gauge.set_data(0, MUTED, "…")
            self.lbl_rem.setText("Loading…")
            self.lbl_rem.setStyleSheet(f"color:{MUTED}; font-size:13px;")
        elif data.get("error"):
            self.gauge.set_data(0, RED, "ERR")
            self.lbl_rem.setText(data["error"])
            self.lbl_rem.setStyleSheet(f"color:{RED}; font-size:11px; font-weight:bold;")
        else:
            self.gauge.set_data(pct, color, f"{pct:.1f}%")
            self.lbl_rem.setText(data.get("remaining") or "—")
            self.lbl_rem.setStyleSheet(
                f"color:{TEXT}; font-size:13px; font-weight:bold;")

        self.lbl_upd.setText(data.get("updated") or "—")

        days  = data.get("days_left")
        etime = data.get("expiry_time")

        if days is None:
            exp_text, exp_color = "—", TEXT
        elif days < 0:
            exp_text, exp_color = "Expired", RED
        elif days == 0:
            exp_text, exp_color = (f"Today at {etime}" if etime else "Today"), ORANGE
        elif days <= 5:
            exp_text, exp_color = f"{days} days", ORANGE
        else:
            exp_text, exp_color = f"{days} days", TEXT

        self.lbl_exp.setText(exp_text)
        self.lbl_exp.setStyleSheet(
            f"color:{exp_color}; font-size:12px; font-weight:bold;")


# ── Settings dialog ───────────────────────────────────────────────────────────

class SettingsDialog(QDialog):
    saved = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setFixedWidth(360)
        self.setStyleSheet(f"""
            QDialog   {{ background:{BG_CARD}; color:{TEXT}; }}
            QLabel    {{ color:{TEXT}; }}
            QLineEdit {{ background:#1a1d2e; color:{TEXT};
                         border:1px solid {SEP}; border-radius:4px; padding:6px; }}
        """)

        form = QFormLayout(self)
        form.setSpacing(10)
        form.setContentsMargins(20, 20, 20, 20)

        self.u_edit = QLineEdit()
        self.p_edit = QLineEdit()
        self.p_edit.setEchoMode(QLineEdit.Password)

        try:
            cfg = fq.read_config()
            self.u_edit.setText(cfg.get("username", ""))
            self.p_edit.setText(cfg.get("password", ""))
        except Exception:
            pass

        form.addRow("Username:", self.u_edit)
        form.addRow("Password:", self.p_edit)

        self.startup_chk = QCheckBox("Launch on Windows startup")
        self.startup_chk.setStyleSheet(f"color:{TEXT}; font-size:11px; margin-top:8px;")
        self.startup_chk.setChecked(is_startup_enabled())
        form.addRow(self.startup_chk)

        btns = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        btns.setStyleSheet(f"QPushButton {{ background:{BG}; color:{TEXT};"
                           f" border:1px solid {SEP}; border-radius:4px; padding:5px 12px; }}")
        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        form.addRow(btns)

    def _save(self):
        u = self.u_edit.text().strip()
        p = self.p_edit.text().strip()
        if u and p:
            fq.write_config(u, p)
            self.saved.emit(u, p)
        set_startup(self.startup_chk.isChecked())
        self.accept()


# ── Main window ───────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(900, 300)
        self.setStyleSheet(f"QMainWindow {{ background:{BG}; color:{TEXT}; }}")
        if os.path.exists(ICON_PATH):
            self.setWindowIcon(QIcon(ICON_PATH))

        central = QWidget()
        self.setCentralWidget(central)
        vbox = QVBoxLayout(central)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)

        # Side-by-side: ADSL | logo | LTE
        body = QWidget()
        body.setStyleSheet(f"background:{BG};")
        row  = QHBoxLayout(body)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)

        self.tab_adsl = ConnectionTab("ADSL")
        self.tab_lte  = ConnectionTab("LTE")

        row.addWidget(self.tab_adsl, 1)

        # Vertical separator
        sep1 = QFrame(); sep1.setFrameShape(QFrame.VLine)
        sep1.setStyleSheet(f"color:{SEP};"); row.addWidget(sep1)

        # Center logo
        logo_widget = QLabel()
        logo_widget.setFixedWidth(200)
        logo_widget.setAlignment(Qt.AlignCenter)
        logo_widget.setStyleSheet(f"background:{BG};")
        if os.path.exists(LOGO_PATH):
            pix = QPixmap(LOGO_PATH).scaled(
                180, 90, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            logo_widget.setPixmap(pix)
        row.addWidget(logo_widget)

        # Vertical separator
        sep2 = QFrame(); sep2.setFrameShape(QFrame.VLine)
        sep2.setStyleSheet(f"color:{SEP};"); row.addWidget(sep2)

        row.addWidget(self.tab_lte, 1)
        vbox.addWidget(body, 1)

        # Footer separator
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"color:{SEP}; background:{SEP};")
        sep.setFixedHeight(1)
        vbox.addWidget(sep)

        # Footer bar
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

        self.refresh_btn = QPushButton("⟳  Refresh")
        self.refresh_btn.setStyleSheet(btn_style)
        self.refresh_btn.clicked.connect(self.do_refresh)
        footer.addWidget(self.refresh_btn)

        settings_btn = QPushButton("⚙  Settings")
        settings_btn.setStyleSheet(btn_style)
        settings_btn.clicked.connect(self._open_settings)
        footer.addWidget(settings_btn)

        vbox.addLayout(footer)

        self._loading = False
        self._thread  = None

        self._timer = QTimer(self)
        self._timer.setInterval(REFRESH_MS)
        self._timer.timeout.connect(self.do_refresh)
        self._timer.start()

        self.do_refresh()

    def do_refresh(self):
        if self._loading:
            return
        self._loading = True
        self.refresh_btn.setEnabled(False)
        self.refresh_btn.setText("Loading…")
        self.status_lbl.setText("Fetching…")
        self.tab_adsl.refresh({}, loading=True)
        self.tab_lte.refresh({},  loading=True)

        self._thread = FetchThread(self)
        self._thread.done.connect(self._on_done)
        self._thread.error.connect(self._on_error)
        self._thread.start()

    def _on_done(self, data: dict):
        self._loading = False
        self.refresh_btn.setEnabled(True)
        self.refresh_btn.setText("⟳  Refresh")
        self.status_lbl.setText(
            f"Updated {data.get('adsl', {}).get('updated', '')}")
        self.tab_adsl.refresh(data.get("adsl", {}), loading=False)
        self.tab_lte.refresh(data.get("lte",  {}), loading=False)
        if hasattr(self, "_tray"):
            self._tray.update_data(data)

    def _on_error(self, msg: str):
        self._loading = False
        self.refresh_btn.setEnabled(True)
        self.refresh_btn.setText("⟳  Refresh")
        self.status_lbl.setText(f"Error: {msg}")
        err = {"error": msg}
        self.tab_adsl.refresh(err, loading=False)
        self.tab_lte.refresh(err,  loading=False)

    def _open_settings(self):
        dlg = SettingsDialog(self)
        dlg.saved.connect(lambda u, p: self.do_refresh())
        dlg.exec_()

    def closeEvent(self, event):
        event.ignore()
        self.hide()


# ── System tray ───────────────────────────────────────────────────────────────

class TrayIcon(QSystemTrayIcon):
    def __init__(self, window: MainWindow):
        super().__init__()
        self._window = window
        window._tray = self

        self._active = "adsl"   # which service the icon currently shows
        self._data   = {}

        self.setIcon(QIcon(ICON_PATH) if os.path.exists(ICON_PATH) else self._make_icon(None))
        self.setToolTip(APP_NAME)

        menu = QMenu()
        menu.setStyleSheet(f"""
            QMenu {{ background:{BG_CARD}; color:{TEXT};
                     border:1px solid {SEP}; padding:4px; }}
            QMenu::item {{ padding:6px 20px; }}
            QMenu::item:selected {{ background:{SEP}; }}
            QMenu::separator {{ background:{SEP}; height:1px; margin:4px 8px; }}
        """)

        self._adsl_act = QAction("ADSL: —", menu); self._adsl_act.setEnabled(False)
        self._lte_act  = QAction("LTE:  —", menu); self._lte_act.setEnabled(False)
        menu.addAction(self._adsl_act)
        menu.addAction(self._lte_act)
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

    def _on_activate(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            # Left-click toggles between ADSL and LTE
            self._active = "lte" if self._active == "adsl" else "adsl"
            self.update_data(self._data)


    def _show(self):
        self._window.show()
        self._window.raise_()
        self._window.activateWindow()

    def update_data(self, data: dict):
        if data:
            self._data = data
        adsl = self._data.get("adsl", {})
        lte  = self._data.get("lte",  {})
        ap   = adsl.get("percent")
        lp   = lte.get("percent")

        self._adsl_act.setText(
            f"ADSL: {ap:.1f}%  —  {adsl.get('remaining', '')}" if ap is not None else "ADSL: —")
        self._lte_act.setText(
            f"LTE:  {lp:.1f}%  —  {lte.get('remaining', '')}"  if lp is not None else "LTE: —")

        # Icon and tooltip reflect the active service
        svc   = adsl if self._active == "adsl" else lte
        pct   = svc.get("percent")
        label = "ADSL" if self._active == "adsl" else "LTE"
        self.setIcon(self._make_icon(pct))
        self.setToolTip(
            f"{APP_NAME}  [{label}]\n"
            f"{pct:.1f}%  {svc.get('remaining', '')}\n"
            f"Click icon to switch service"
            if pct is not None else APP_NAME)

    def _make_icon(self, pct):
        """Draw a 64×64 single-arc tray icon for the active service."""
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

        # Small label showing which service is active
        label = "ADSL" if self._active == "adsl" else "LTE"
        p.setPen(QColor(MUTED))
        p.setFont(QFont("Arial", 7))
        p.drawText(QRectF(0, sz - 14, sz, 12), Qt.AlignHCenter, label)

        p.end()
        return QIcon(pix)


# ── Entry point ───────────────────────────────────────────────────────────────

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
    tray   = TrayIcon(window)

    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
