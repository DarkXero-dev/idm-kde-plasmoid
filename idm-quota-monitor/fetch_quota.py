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


def scrape(session, url):
    r = session.get(url, timeout=20)
    r.raise_for_status()
    pct = re.search(r'ctl00_PlaceHolderMain_TraficUsed[^>]*data-percent="([^"]+)"', r.text)
    rem = re.search(r'id="ctl00_PlaceHolderMain_RemainingLabel"[^>]*>([^<]+)<', r.text)
    if not pct and not rem:
        raise ValueError("Could not find quota elements")
    return {
        "percent":   round(float(pct.group(1)), 2) if pct else None,
        "remaining": rem.group(1).strip() if rem else None,
        "updated":   datetime.now().strftime("%H:%M"),
        "error":     None,
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
