#!/usr/bin/env python3
"""
IDM quota fetcher — Windows version.
Credentials stored AES-encrypted in %APPDATA%/IDMQuota/config.conf,
key derived from the Windows MachineGuid (no external keystore needed).
"""

import re, json, os, sys, base64, hashlib, hmac
from datetime import datetime
import requests

CONFIG_PATH = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")),
                           "IDMQuota", "config.conf")

LOGIN_URL = "https://myaccount.idm.net.lb/_layouts/15/IDMPortal/ManageUsers/Login.aspx"

CONNECTIONS = {
    "adsl": "https://myaccount.idm.net.lb/_layouts/15/IDMPortal/ManageServices/ManageService.aspx?type=2&si=MTI2OTI=&ai=NTAyODQ0NjM=&pi=67185&un=TDk4NzU5Nw==&ps=MkpnYXg3ekQzWg==&an=WGVyb0RTTA==",
    "lte":  "https://myaccount.idm.net.lb/_layouts/15/IDMPortal/ManageServices/ManageService.aspx?type=2&si=MjExMzM3&ai=NTA0NDM4NTE=&pi=67185&un=RzM2MTI4MA==&ps=QU5Z&an=WGVyb0xURQ==",
}
HISTORY_MAX = 96

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


# ── Encryption (stdlib only — no external crypto deps) ────────────────────────
# Scheme: PBKDF2-HMAC-SHA256 key derivation + SHA-256 counter-mode stream
#         cipher + HMAC-SHA256 authentication tag.
# Token format (base64url): "v2:" + b64(salt[16] | hmac[32] | ciphertext)

def _machine_key() -> str:
    """Return the Windows MachineGuid; fall back to hostname."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                            r"SOFTWARE\Microsoft\Cryptography") as k:
            return winreg.QueryValueEx(k, "MachineGuid")[0]
    except Exception:
        import socket
        return socket.gethostname()


def _derive_key(salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac(
        'sha256', _machine_key().encode('utf-8'), salt, 100_000)


def _xor_stream(data: bytes, key: bytes) -> bytes:
    """SHA-256 counter-mode keystream XOR."""
    out, block = bytearray(len(data)), 32
    for i in range(0, len(data), block):
        ks = hashlib.sha256(key + i.to_bytes(8, 'big')).digest()
        for j, b in enumerate(data[i:i + block]):
            out[i + j] = b ^ ks[j]
    return bytes(out)


def _encrypt(plaintext: str) -> str:
    salt = os.urandom(16)
    key  = _derive_key(salt)
    ct   = _xor_stream(plaintext.encode('utf-8'), key)
    mac  = hmac.new(key, ct, hashlib.sha256).digest()
    return "v2:" + base64.urlsafe_b64encode(salt + mac + ct).decode()


def _decrypt(token: str) -> str:
    raw  = base64.urlsafe_b64decode(token[3:] + "==")   # strip "v2:"
    salt, mac_stored, ct = raw[:16], raw[16:48], raw[48:]
    key  = _derive_key(salt)
    if not hmac.compare_digest(mac_stored,
                               hmac.new(key, ct, hashlib.sha256).digest()):
        raise ValueError("MAC mismatch — wrong machine or tampered file")
    return _xor_stream(ct, key).decode('utf-8')


# ── Config ────────────────────────────────────────────────────────────────────

def read_config() -> dict:
    config = {}
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    config[k.strip()] = v.strip()
    except FileNotFoundError:
        pass
    for key in ("username", "password"):
        if key in config and config[key].startswith("v2:"):
            try:
                config[key] = _decrypt(config[key])
            except Exception:
                pass
    return config


def write_config(username: str, password: str):
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        f.write(f"username={_encrypt(username)}\npassword={_encrypt(password)}\n")


# ── History ───────────────────────────────────────────────────────────────────

def _history_path(conn: str) -> str:
    return os.path.join(os.path.dirname(CONFIG_PATH), f"history_{conn}.json")


def load_history(conn: str) -> list:
    try:
        with open(_history_path(conn)) as f:
            return json.load(f)
    except Exception:
        return []


def save_history(conn: str, history: list):
    with open(_history_path(conn), "w") as f:
        json.dump(history[-HISTORY_MAX:], f)


# ── Scraping ──────────────────────────────────────────────────────────────────

def extract_hidden_fields(html: str) -> dict:
    fields = {}
    for m in re.finditer(r'<input[^>]+type=["\']hidden["\'][^>]*>', html, re.IGNORECASE):
        tag = m.group(0)
        name  = re.search(r'name=["\']([^"\']*)["\']', tag)
        value = re.search(r'value=["\']([^"\']*)["\']', tag)
        if name:
            fields[name.group(1)] = value.group(1) if value else ""
    return fields


def parse_expiry(date_str: str):
    """Return (days_remaining, 'HH:MM' or None)."""
    s = date_str.strip().replace('\xa0', ' ')
    for fmt in ("%m/%d/%Y %H:%M", "%d/%m/%Y %H:%M", "%Y-%m-%d %H:%M", "%d-%m-%Y %H:%M",
                "%m/%d/%Y %H:%M:%S", "%d/%m/%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%dT%H:%M:%S"):
        try:
            exp  = datetime.strptime(s, fmt)
            days = (exp.date() - datetime.now().date()).days
            return days, exp.strftime("%H:%M")
        except ValueError:
            continue
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%m/%d/%Y", "%d-%m-%Y"):
        try:
            exp  = datetime.strptime(s, fmt)
            days = (exp.date() - datetime.now().date()).days
            return days, None
        except ValueError:
            continue
    return None, None


def scrape(session, url: str) -> dict:
    r = session.get(url, timeout=20)
    r.raise_for_status()

    pct = re.search(r'ctl00_PlaceHolderMain_TraficUsed[^>]*data-percent="([^"]+)"', r.text)
    rem = re.search(r'id="ctl00_PlaceHolderMain_RemainingLabel"[^>]*>([^<]+)<', r.text)

    exp = re.search(
        r'Expiry\s+Date\s*</td>\s*<td[^>]*>\s*'
        r'(\d{1,4}[\/\-]\d{1,2}[\/\-]\d{2,4}[\s\xa0]+\d{2}:\d{2}(?::\d{2})?)',
        r.text, re.IGNORECASE)
    if not exp:
        exp = re.search(r'id="ctl00_PlaceHolderMain_ExpiryDateLabel"[^>]*>([^<]+)<', r.text)
    if not exp:
        exp = re.search(
            r'(?:expir\w*|end\s*date)[^<]{0,80}?'
            r'(\d{1,4}[\/\-]\d{1,2}[\/\-]\d{2,4}(?:[T \t\xa0]\d{2}:\d{2}(?::\d{2})?)?)',
            r.text, re.IGNORECASE)

    if not pct and not rem:
        raise ValueError("Could not find quota elements")

    exp_str            = exp.group(1).strip() if exp else None
    days_left, exp_time = parse_expiry(exp_str) if exp_str else (None, None)

    return {
        "percent":     round(float(pct.group(1)), 2) if pct else None,
        "remaining":   rem.group(1).strip() if rem else None,
        "days_left":   days_left,
        "expiry":      exp_str,
        "expiry_time": exp_time,
        "updated":     datetime.now().strftime("%H:%M"),
        "error":       None,
    }


# ── Main fetch ────────────────────────────────────────────────────────────────

def fetch_all() -> dict:
    config   = read_config()
    username = config.get("username", "")
    password = config.get("password", "")

    if not username or not password:
        raise RuntimeError("No credentials configured.")

    session = requests.Session()
    session.headers.update(HEADERS)

    r = session.get(LOGIN_URL, timeout=20)
    r.raise_for_status()

    payload = extract_hidden_fields(r.text)
    payload["__EVENTTARGET"]   = "ctl00$PlaceHolderMain$signInControl$SignInButton"
    payload["__EVENTARGUMENT"] = ""
    payload["ctl00$PlaceHolderMain$signInControl$UserName"] = username
    payload["ctl00$PlaceHolderMain$signInControl$password"] = password

    r = session.post(LOGIN_URL, data=payload, timeout=20, headers={"Referer": LOGIN_URL})
    r.raise_for_status()

    if "signInControl_UserName" in r.text:
        raise RuntimeError("Login failed — check username and password.")

    result = {}
    for conn, url in CONNECTIONS.items():
        try:
            data = scrape(session, url)
        except Exception as e:
            data = {"percent": None, "remaining": None, "days_left": None,
                    "expiry": None, "expiry_time": None,
                    "updated": datetime.now().strftime("%H:%M"), "error": str(e)}

        history = load_history(conn)
        if data["percent"] is not None:
            history.append({"t": data["updated"], "pct": data["percent"]})
            save_history(conn, history)

        result[conn]              = data
        result[f"{conn}_history"] = history[-HISTORY_MAX:]

    return result
