import re
from datetime import datetime

import requests

BASE_URL = "https://myaccount.idm.net.lb"
LOGIN_URL = BASE_URL + "/_layouts/15/IDMPortal/ManageUsers/Login.aspx"
ACCOUNTS_URL = BASE_URL + "/_layouts/15/IDMPortal/ManageServices/MyAccounts.aspx"

TYPE_MAP = {
    "adsl": "adsl", "vdsl": "adsl",
    "fiber": "fiber",
    "3g": "lte", "4g": "lte", "lte": "lte",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

_DATE = r"\d{1,4}[/\-]\d{1,2}[/\-]\d{2,4}"
_TIME = r"\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AaPp][Mm])?"

_EXPIRY_PATTERNS = [
    re.compile(rf"Expiry\s+Date\s*</td>\s*<td[^>]*>\s*({_DATE}[\s\xa0]+{_TIME})", re.IGNORECASE),
    re.compile(r'id="ctl00_PlaceHolderMain_ExpiryDateLabel"[^>]*>([^<]+)<'),
    re.compile(
        r"(?:ExpiryDate|EndDate|expiry|expire)[^>]*?"
        rf"(?:data-\w+|value|title|datetime)=[\"']({_DATE}(?:[T \t]{_TIME})?)[\"']",
        re.IGNORECASE),
    re.compile(rf"(?:expir\w*|end\s*date)[^<]{{0,80}}?({_DATE}(?:[T \t\xa0]{_TIME})?)", re.IGNORECASE),
]

_DATETIME_FORMATS = (
    "%m/%d/%Y %H:%M", "%d/%m/%Y %H:%M", "%Y-%m-%d %H:%M", "%d-%m-%Y %H:%M",
    "%m/%d/%Y %H:%M:%S", "%d/%m/%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M",
    "%m/%d/%Y %I:%M %p", "%d/%m/%Y %I:%M %p", "%m/%d/%Y %I:%M:%S %p", "%d/%m/%Y %I:%M:%S %p",
)
_DATE_FORMATS = ("%d/%m/%Y", "%Y-%m-%d", "%m/%d/%Y", "%d-%m-%Y")

_GRID_ROW = re.compile(
    r"ResidentialServicesGridView_(ctl\d+)_ResidentialAccountName(.*?)_\1_Type[^>]*>([^<]+)<",
    re.DOTALL)
_QUOTA_PERCENT = re.compile(r'ctl00_PlaceHolderMain_TraficUsed[^>]*data-percent="([^"]+)"')
_QUOTA_REMAINING = re.compile(r'id="ctl00_PlaceHolderMain_RemainingLabel"[^>]*>([^<]+)<')


def extract_hidden_fields(html):
    fields = {}
    for m in re.finditer(r'<input[^>]+type=["\']hidden["\'][^>]*>', html, re.IGNORECASE):
        tag = m.group(0)
        name = re.search(r'name=["\']([^"\']*)["\']', tag)
        value = re.search(r'value=["\']([^"\']*)["\']', tag)
        if name:
            fields[name.group(1)] = value.group(1) if value else ""
    return fields


def parse_expiry(text):
    s = re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()
    for fmt in _DATETIME_FORMATS:
        try:
            return datetime.strptime(s, fmt), True
        except ValueError:
            continue
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt), False
        except ValueError:
            continue
    return None, False


def expiry_iso(dt, has_time):
    return dt.strftime("%Y-%m-%dT%H:%M" if has_time else "%Y-%m-%d")


def _cell_text(raw):
    raw = raw.split(">", 1)[1] if ">" in raw else raw
    raw = re.sub(r"<[^<]*$", "", raw)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]*>", " ", raw)).strip()


def parse_services(html):
    services, seen = [], set()
    for ctrl, between, raw_type in _GRID_ROW.findall(html):
        name = _cell_text(between) or ctrl
        sid = name if name not in seen else f"{name}#{ctrl}"
        seen.add(sid)
        raw_type = raw_type.strip()
        services.append({
            "ctrl": ctrl,
            "id": sid,
            "name": name,
            "raw_type": raw_type,
            "type": TYPE_MAP.get(raw_type.lower(), "other"),
        })
    return services


def scrape_page(html):
    pct = _QUOTA_PERCENT.search(html)
    rem = _QUOTA_REMAINING.search(html)
    if not pct and not rem:
        raise ValueError("Could not find quota elements")
    exp = next((m for m in (p.search(html) for p in _EXPIRY_PATTERNS) if m), None)
    exp_str = exp.group(1).strip() if exp else None
    dt, has_time = parse_expiry(exp_str) if exp_str else (None, False)
    return {
        "percent": round(float(pct.group(1)), 2) if pct else None,
        "remaining": re.sub(r"\s*remaining$", "", rem.group(1).strip(), flags=re.IGNORECASE) if rem else None,
        "expiry": exp_str,
        "expiry_iso": expiry_iso(dt, has_time) if dt else None,
        "updated": datetime.now().strftime("%H:%M"),
        "error": None,
    }


def _new_session():
    session = requests.Session()
    session.headers.update(HEADERS)
    return session


def login(session, username, password):
    r = session.get(LOGIN_URL, timeout=20)
    r.raise_for_status()
    payload = extract_hidden_fields(r.text)
    payload["__EVENTTARGET"] = "ctl00$PlaceHolderMain$signInControl$SignInButton"
    payload["__EVENTARGUMENT"] = ""
    payload["ctl00$PlaceHolderMain$signInControl$UserName"] = username
    payload["ctl00$PlaceHolderMain$signInControl$password"] = password
    r = session.post(LOGIN_URL, data=payload, timeout=20, headers={"Referer": LOGIN_URL})
    r.raise_for_status()
    if "signInControl_UserName" in r.text:
        raise RuntimeError("Login failed: check username and password")


def discover(session):
    r = session.get(ACCOUNTS_URL, timeout=20)
    r.raise_for_status()
    services = parse_services(r.text)
    if not services:
        raise RuntimeError("No services found on this login")
    return services, r.text


def _scrape_service(session, ctrl, accounts_html):
    payload = extract_hidden_fields(accounts_html)
    payload["__EVENTTARGET"] = (
        f"ctl00$PlaceHolderMain$ResidentialServicesGridView${ctrl}$ManageResidentialButton")
    payload["__EVENTARGUMENT"] = ""
    r = session.post(ACCOUNTS_URL, data=payload, timeout=20,
                     headers={"Referer": ACCOUNTS_URL}, allow_redirects=True)
    r.raise_for_status()
    return scrape_page(r.text)


def fetch(username, password, session=None):
    session = session or _new_session()
    login(session, username, password)
    services, accounts_html = discover(session)
    out = []
    for svc in services:
        try:
            data = _scrape_service(session, svc["ctrl"], accounts_html)
        except Exception as e:
            data = {"percent": None, "remaining": None, "expiry": None, "expiry_iso": None,
                    "updated": datetime.now().strftime("%H:%M"), "error": str(e)}
        out.append({"id": svc["id"], "type": svc["type"], "name": svc["name"], **data})
    return {"error": None, "services": out}


def list_services(username, password, session=None):
    session = session or _new_session()
    login(session, username, password)
    services, _ = discover(session)
    return {"error": None, "services": [
        {k: s[k] for k in ("id", "type", "name", "raw_type")} for s in services]}
