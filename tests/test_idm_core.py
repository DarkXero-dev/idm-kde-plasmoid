from datetime import datetime

import pytest

import idm_core

GRID = "ctl00_PlaceHolderMain_ResidentialServicesGridView_%s_"


def row(ctrl, name, svc_type):
    p = GRID % ctrl
    return (
        f'<tr><td><span id="{p}ResidentialAccountName">{name}</span></td>'
        f'<td><span id="{p}Type">{svc_type}</span></td></tr>'
    )


def grid(*rows):
    return "<table>" + "".join(rows) + "</table>"


def test_parse_expiry_month_first_with_time():
    assert idm_core.parse_expiry("10/16/2026 23:59") == (datetime(2026, 10, 16, 23, 59), True)


def test_parse_expiry_day_first_when_month_first_invalid():
    assert idm_core.parse_expiry("16/10/2026 23:59") == (datetime(2026, 10, 16, 23, 59), True)


def test_parse_expiry_iso_with_seconds():
    assert idm_core.parse_expiry("2026-10-16 23:59:00") == (datetime(2026, 10, 16, 23, 59), True)


def test_parse_expiry_pm_is_24_hour():
    assert idm_core.parse_expiry("10/16/2026 11:59 PM") == (datetime(2026, 10, 16, 23, 59), True)


def test_parse_expiry_nbsp_separator():
    assert idm_core.parse_expiry("10/16/2026\xa008:05") == (datetime(2026, 10, 16, 8, 5), True)


def test_parse_expiry_date_only():
    assert idm_core.parse_expiry("2026-10-16") == (datetime(2026, 10, 16), False)


def test_parse_expiry_garbage():
    assert idm_core.parse_expiry("soon") == (None, False)


def test_expiry_iso_with_and_without_time():
    assert idm_core.expiry_iso(datetime(2026, 10, 16, 9, 5), True) == "2026-10-16T09:05"
    assert idm_core.expiry_iso(datetime(2026, 10, 16), False) == "2026-10-16"


def test_parse_services_maps_types_and_names():
    html = grid(
        row("ctl02", "adsl_home", "ADSL"),
        row("ctl03", "vdsl_office", "VDSL"),
        row("ctl04", "lte_phone", "4G"),
        row("ctl05", "fiber_shop", "Fiber"),
        row("ctl06", "sat_1", "Satellite"),
    )
    got = [(s["id"], s["type"], s["raw_type"], s["ctrl"]) for s in idm_core.parse_services(html)]
    assert got == [
        ("adsl_home", "adsl", "ADSL", "ctl02"),
        ("vdsl_office", "adsl", "VDSL", "ctl03"),
        ("lte_phone", "lte", "4G", "ctl04"),
        ("fiber_shop", "fiber", "Fiber", "ctl05"),
        ("sat_1", "other", "Satellite", "ctl06"),
    ]


def test_parse_services_duplicate_names_get_unique_ids():
    html = grid(row("ctl02", "line", "ADSL"), row("ctl03", "line", "ADSL"))
    ids = [s["id"] for s in idm_core.parse_services(html)]
    assert ids == ["line", "line#ctl03"]


def test_parse_services_empty_name_falls_back_to_ctrl():
    html = grid(row("ctl02", "", "LTE"))
    assert idm_core.parse_services(html)[0]["id"] == "ctl02"


def test_parse_services_name_inside_link():
    p = GRID % "ctl02"
    html = (
        f'<span id="{p}ResidentialAccountName"><a href="#">acct_x</a></span>'
        f'<span id="{p}Type">ADSL</span>'
    )
    assert idm_core.parse_services(html)[0]["id"] == "acct_x"


LTE_PAGE = (
    '<div id="ctl00_PlaceHolderMain_TraficUsed" data-percent="42.5"></div>'
    '<span id="ctl00_PlaceHolderMain_RemainingLabel">57.5 GB</span>'
    "<table><tr><td>Expiry Date</td><td>10/16/2026 23:59</td></tr></table>"
)

ADSL_PAGE = (
    '<div id="ctl00_PlaceHolderMain_TraficUsed" data-percent="10"></div>'
    '<span id="ctl00_PlaceHolderMain_RemainingLabel">90 GB</span>'
    '<span id="ctl00_PlaceHolderMain_ExpiryDateLabel">16/10/2026</span>'
)


def test_scrape_page_lte_table_layout():
    d = idm_core.scrape_page(LTE_PAGE)
    assert d["percent"] == 42.5
    assert d["remaining"] == "57.5 GB"
    assert d["expiry"] == "10/16/2026 23:59"
    assert d["expiry_iso"] == "2026-10-16T23:59"
    assert d["error"] is None


def test_scrape_page_adsl_label_layout_date_only():
    d = idm_core.scrape_page(ADSL_PAGE)
    assert d["percent"] == 10.0
    assert d["expiry_iso"] == "2026-10-16"


def test_scrape_page_without_expiry():
    d = idm_core.scrape_page(LTE_PAGE.split("<table>")[0])
    assert d["expiry"] is None and d["expiry_iso"] is None


def test_scrape_page_pm_time_is_converted():
    page = LTE_PAGE.replace("10/16/2026 23:59", "10/16/2026 11:59 PM")
    assert idm_core.scrape_page(page)["expiry_iso"] == "2026-10-16T23:59"


def test_scrape_page_drops_the_trailing_remaining_word():
    page = LTE_PAGE.replace("57.5 GB", "99.74 GB Remaining")
    assert idm_core.scrape_page(page)["remaining"] == "99.74 GB"


def test_scrape_page_missing_quota_raises():
    with pytest.raises(ValueError, match="Could not find quota elements"):
        idm_core.scrape_page("<html></html>")


class Resp:
    def __init__(self, text):
        self.text = text

    def raise_for_status(self):
        pass


class FakeSession:
    def __init__(self, login_ok=True):
        self.login_ok = login_ok
        self.headers = {}
        self.grid = grid(row("ctl02", "adsl_home", "ADSL"), row("ctl03", "lte_phone", "LTE"))

    def get(self, url, **kw):
        if url == idm_core.LOGIN_URL:
            return Resp('<input type="hidden" name="__VIEWSTATE" value="vs">signInControl_UserName')
        return Resp(self.grid + '<input type="hidden" name="__VIEWSTATE" value="acc">')

    def post(self, url, data=None, **kw):
        if url == idm_core.LOGIN_URL:
            return Resp("signInControl_UserName" if not self.login_ok else "welcome")
        target = data["__EVENTTARGET"]
        return Resp(LTE_PAGE if "ctl03" in target else ADSL_PAGE)


def test_login_failure_raises():
    with pytest.raises(RuntimeError, match="Login failed"):
        idm_core.login(FakeSession(login_ok=False), "u", "p")


def test_fetch_returns_all_services():
    out = idm_core.fetch("u", "p", session=FakeSession())
    assert out["error"] is None
    assert [(s["id"], s["type"], s["percent"]) for s in out["services"]] == [
        ("adsl_home", "adsl", 10.0),
        ("lte_phone", "lte", 42.5),
    ]
    assert set(out["services"][0]) == {
        "id", "type", "name", "percent", "remaining", "expiry",
        "expiry_iso", "updated", "error",
    }


def test_fetch_scrape_failure_is_reported_per_service():
    s = FakeSession()
    s.post = lambda url, data=None, **kw: (
        Resp("welcome") if url == idm_core.LOGIN_URL else Resp("<html></html>")
    )
    out = idm_core.fetch("u", "p", session=s)
    assert all(svc["percent"] is None and svc["error"] for svc in out["services"])


def test_list_services_shape():
    out = idm_core.list_services("u", "p", session=FakeSession())
    assert out["error"] is None
    assert out["services"][1] == {
        "id": "lte_phone", "type": "lte", "name": "lte_phone",
        "raw_type": "LTE",
    }
