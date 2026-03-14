#!/usr/bin/env python3
"""
Fetches IDM quota for both ADSL and LTE in one login session.
Credentials are read from ~/.config/IDMQuota/config.conf

Modes:
  fetch_quota.py                             fetch quota
  fetch_quota.py --write-config B64U B64P   save credentials (base64-encoded args)
"""

import re, json, os, sys
from datetime import datetime
import requests

SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.expanduser("~/.config/IDMQuota/config.conf")
LOGIN_URL   = "https://myaccount.idm.net.lb/_layouts/15/IDMPortal/ManageUsers/Login.aspx"

CONNECTIONS = {
    "adsl": "https://myaccount.idm.net.lb/_layouts/15/IDMPortal/ManageServices/ManageService.aspx?type=2&si=MTI2OTI=&ai=NTAyODQ0NjM=&pi=67185&un=TDk4NzU5Nw==&ps=MkpnYXg3ekQzWg==&an=WGVyb0RTTA==",
    "lte":  "https://myaccount.idm.net.lb/_layouts/15/IDMPortal/ManageServices/ManageService.aspx?type=2&si=MjExMzM3&ai=NTA0NDM4NTE=&pi=67185&un=RzM2MTI4MA==&ps=QU5Z&an=WGVyb0xURQ==",
}
HISTORY_MAX = 96

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


def read_config():
    config = {}
    try:
        with open(CONFIG_PATH) as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    config[k.strip()] = v.strip()
    except FileNotFoundError:
        pass
    return config


def write_config(username, password):
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        f.write(f"username={username}\npassword={password}\n")


def extract_hidden_fields(html):
    fields = {}
    for m in re.finditer(r'<input[^>]+type=["\']hidden["\'][^>]*>', html, re.IGNORECASE):
        tag = m.group(0)
        name  = re.search(r'name=["\']([^"\']*)["\']', tag)
        value = re.search(r'value=["\']([^"\']*)["\']', tag)
        if name:
            fields[name.group(1)] = value.group(1) if value else ""
    return fields


def load_history(conn):
    path = os.path.join(SCRIPT_DIR, f"history_{conn}.json")
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return []


def save_history(conn, history):
    path = os.path.join(SCRIPT_DIR, f"history_{conn}.json")
    with open(path, "w") as f:
        json.dump(history[-HISTORY_MAX:], f)


def parse_expiry(date_str):
    """Return (days_remaining, time_str_or_None). Negative days = already expired."""
    s = date_str.strip().replace('\xa0', ' ')
    # Try datetime formats first (date + time)
    for fmt in ("%m/%d/%Y %H:%M", "%d/%m/%Y %H:%M", "%Y-%m-%d %H:%M", "%d-%m-%Y %H:%M",
                "%m/%d/%Y %H:%M:%S", "%d/%m/%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            exp = datetime.strptime(s, fmt)
            days = (exp.date() - datetime.now().date()).days
            return days, exp.strftime("%H:%M")
        except ValueError:
            continue
    # Date-only formats
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%m/%d/%Y", "%d-%m-%Y"):
        try:
            exp = datetime.strptime(s, fmt)
            days = (exp.date() - datetime.now().date()).days
            return days, None
        except ValueError:
            continue
    return None, None


def scrape(session, url):
    r = session.get(url, timeout=20)
    r.raise_for_status()
    pct = re.search(r'ctl00_PlaceHolderMain_TraficUsed[^>]*data-percent="([^"]+)"', r.text)
    rem = re.search(r'id="ctl00_PlaceHolderMain_RemainingLabel"[^>]*>([^<]+)<', r.text)
    # Pattern 1: "Expiry Date</td><td...>DATE TIME</td>" (LTE table layout)
    exp = re.search(
        r'Expiry\s+Date\s*</td>\s*<td[^>]*>\s*'
        r'(\d{1,4}[\/\-]\d{1,2}[\/\-]\d{2,4}[\s\xa0]+\d{2}:\d{2}(?::\d{2})?)',
        r.text, re.IGNORECASE)
    # Pattern 2: label element with ID (ADSL layout)
    if not exp:
        exp = re.search(
            r'id="ctl00_PlaceHolderMain_ExpiryDateLabel"[^>]*>([^<]+)<',
            r.text)
    # Pattern 3: data attributes near expiry keyword
    if not exp:
        exp = re.search(
            r'(?:ExpiryDate|EndDate|expiry|expire)[^>]*?'
            r'(?:data-\w+|value|title|datetime)=["\']'
            r'(\d{1,4}[\/\-]\d{1,2}[\/\-]\d{2,4}(?:[T \t]\d{2}:\d{2}(?::\d{2})?)?)["\']',
            r.text, re.IGNORECASE)
    # Pattern 4: wide sweep fallback
    if not exp:
        exp = re.search(
            r'(?:expir\w*|end\s*date)[^<]{0,80}?'
            r'(\d{1,4}[\/\-]\d{1,2}[\/\-]\d{2,4}(?:[T \t\xa0]\d{2}:\d{2}(?::\d{2})?)?)',
            r.text, re.IGNORECASE)
    if not pct and not rem:
        raise ValueError("Could not find quota elements")
    exp_str          = exp.group(1).strip() if exp else None
    days_left, exp_time = parse_expiry(exp_str) if exp_str else (None, None)
    # Debug: log raw expiry string to stderr so we can see what the portal returns
    if exp_str:
        import sys; print(f"[expiry raw] {exp_str!r}", file=sys.stderr)
    return {
        "percent":    round(float(pct.group(1)), 2) if pct else None,
        "remaining":  rem.group(1).strip() if rem else None,
        "days_left":  days_left,
        "expiry":     exp_str,
        "expiry_time": exp_time,
        "updated":    datetime.now().strftime("%H:%M"),
        "error":      None,
    }


def run():
    config   = read_config()
    username = config.get("username", "")
    password = config.get("password", "")

    if not username or not password:
        raise RuntimeError("No credentials — edit ~/.config/IDMQuota/config.conf or use widget Settings")

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
        raise RuntimeError("Login failed — check username and password")

    result = {}
    for conn, url in CONNECTIONS.items():
        try:
            data = scrape(session, url)
        except Exception as e:
            data = {"percent": None, "remaining": None,
                    "updated": datetime.now().strftime("%H:%M"), "error": str(e)}

        history = load_history(conn)
        if data["percent"] is not None:
            history.append({"t": data["updated"], "pct": data["percent"]})
            save_history(conn, history)

        result[conn] = data
        result[f"{conn}_history"] = history[-HISTORY_MAX:]

    print(json.dumps(result))


if __name__ == "__main__":
    if "--write-config" in sys.argv:
        idx = sys.argv.index("--write-config")
        try:
            username = bytes.fromhex(sys.argv[idx + 1]).decode("utf-8")
            password = bytes.fromhex(sys.argv[idx + 2]).decode("utf-8")
            write_config(username, password)
            print(json.dumps({"ok": True}))
        except Exception as e:
            print(json.dumps({"ok": False, "error": str(e)}))
            sys.exit(1)
        sys.exit(0)

    try:
        run()
    except Exception as e:
        err = {"adsl": {"error": str(e)}, "lte": {"error": str(e)},
               "adsl_history": [], "lte_history": []}
        print(json.dumps(err))
        sys.exit(1)
