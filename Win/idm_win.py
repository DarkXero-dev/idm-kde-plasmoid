import base64
import ctypes
import os
import re
from datetime import datetime

import idm_core

CONFIG_PATH = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")),
                           "IDMQuota", "config.conf")
TOKEN_PREFIX = "dpapi:"
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


class _Blob(ctypes.Structure):
    _fields_ = [("cbData", ctypes.c_uint32), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _dpapi(function, data):
    windll = ctypes.windll
    buf = ctypes.create_string_buffer(data, len(data))
    src = _Blob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
    out = _Blob()
    if not getattr(windll.crypt32, function)(ctypes.byref(src), None, None, None, None, 0,
                                             ctypes.byref(out)):
        raise ctypes.WinError()
    try:
        return ctypes.string_at(out.pbData, out.cbData)
    finally:
        windll.kernel32.LocalFree(out.pbData)


def _protect(data):
    return _dpapi("CryptProtectData", data)


def _unprotect(data):
    return _dpapi("CryptUnprotectData", data)


def read_config():
    config = {}
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    config[k.strip()] = v.strip()
    except FileNotFoundError:
        return config
    for key in ("username", "password"):
        value = config.get(key, "")
        if value.startswith(TOKEN_PREFIX):
            try:
                value = _unprotect(base64.b64decode(value[len(TOKEN_PREFIX):])).decode("utf-8")
            except Exception:
                value = ""
        elif value.startswith("v2:"):
            value = ""
        config[key] = value
    return config


def write_config(username, password):
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)

    def seal(text):
        return TOKEN_PREFIX + base64.b64encode(_protect(text.encode("utf-8"))).decode()

    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        f.write(f"username={seal(username)}\npassword={seal(password)}\n")


def _credentials():
    config = read_config()
    username, password = config.get("username", ""), config.get("password", "")
    if not username or not password:
        raise RuntimeError("No credentials configured.")
    return username, password


def fetch_all():
    return idm_core.fetch(*_credentials())


def list_services(credentials=None):
    return idm_core.list_services(*(credentials or _credentials()))


def expiry_state(iso, now):
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})(?:T(\d{2}):(\d{2}))?", iso or "")
    if not m:
        return {"text": "-", "line": "", "level": "ok"}
    y, mo, d = int(m[1]), int(m[2]), int(m[3])
    has_time = m[4] is not None
    hh, mm = (int(m[4]), int(m[5])) if has_time else (0, 0)
    clock = f"{hh:02d}:{mm:02d}"
    line = f"{d} {MONTHS[mo - 1]} {y}" + (f" {clock}" if has_time else "")
    days = (datetime(y, mo, d).date() - now.date()).days
    expired = datetime(y, mo, d, hh, mm) <= now if has_time else days < 0
    if expired:
        return {"text": "Expired", "line": line, "level": "expired"}
    if days == 0:
        text = f"Today {clock}" if has_time else "Today"
    else:
        text = f"{days} day" + ("" if days == 1 else "s")
    return {"text": text, "line": line, "level": "soon" if days <= 5 else "ok"}


MAX_SHOWN = 3
TYPE_LABELS = {"adsl": "ADSL", "lte": "LTE", "fiber": "FIBER"}


def type_label(service_type):
    return TYPE_LABELS.get(service_type, "SERVICE")


def shown_services(services, selected):
    picked = [s for s in services if s["id"] in selected]
    return (picked or services)[:MAX_SHOWN]


def display_name(service, names):
    return names.get(service["id"]) or service["name"]
