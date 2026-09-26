import io
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

import speed_core

CHUNK = 16384


class SpeedHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    rate = 2_000_000
    need_user_agent = True

    def _pace(self):
        time.sleep(CHUNK / self.rate)

    def _ok(self):
        return not self.need_user_agent or self.headers.get("User-Agent")

    def do_GET(self):
        if not self._ok():
            self.send_response(500)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if self.path.startswith("/latency.txt"):
            body = b"test=test\n"
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path.startswith("/download"):
            size = int(self.path.split("size=")[1])
            self.send_response(200)
            self.send_header("Content-Length", str(size))
            self.end_headers()
            sent = 0
            try:
                while sent < size:
                    n = min(CHUNK, size - sent)
                    self.wfile.write(b"x" * n)
                    sent += n
                    self._pace()
            except OSError:
                pass
        else:
            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.end_headers()

    def do_POST(self):
        size = int(self.headers["Content-Length"])
        try:
            remaining = size
            while remaining > 0:
                data = self.rfile.read(min(CHUNK, remaining))
                if not data:
                    return
                remaining -= len(data)
                self._pace()
            body = f"size={size}\n".encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except OSError:
            pass

    def log_message(self, *args):
        pass


@pytest.fixture
def local_server():
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), SpeedHandler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield {"id": "1", "name": "Local", "country": "Testland", "sponsor": "Test",
           "host": f"127.0.0.1:{httpd.server_port}", "scheme": "http"}
    httpd.shutdown()
    httpd.server_close()


def make_server(name, host="h:8080"):
    return {"id": name, "name": name, "country": "X", "sponsor": "S", "host": host, "scheme": "https"}


# -- server list ---------------------------------------------------------------

def test_fetch_servers_maps_the_speedtest_api(monkeypatch):
    payload = [
        {"id": "71669", "name": "Thessaloniki", "country": "Greece", "sponsor": "Telekom GR",
         "host": "a.example:8080", "distance": 6},
        {"id": "5", "name": "NoHost", "country": "Greece", "sponsor": "S", "host": ""},
        {"id": "62559", "name": "Thessaloniki", "country": "Greece", "sponsor": "Inalan ISP",
         "host": "b.example:8080", "distance": 8},
    ]
    seen = {}

    def fake_urlopen(request, timeout=None):
        seen["url"], seen["ua"] = request.full_url, request.get_header("User-agent")
        return io.BytesIO(json.dumps(payload).encode())

    monkeypatch.setattr(speed_core.urllib.request, "urlopen", fake_urlopen)
    servers = speed_core.fetch_servers(12)
    assert [s["host"] for s in servers] == ["a.example:8080", "b.example:8080"]
    assert servers[0] == {"id": "71669", "name": "Thessaloniki", "country": "Greece",
                          "sponsor": "Telekom GR", "host": "a.example:8080", "scheme": "https"}
    assert seen["url"].startswith("https://") and "limit=12" in seen["url"]
    assert seen["ua"]


# -- latency and server choice -------------------------------------------------

def test_measure_latency_returns_a_positive_median(local_server):
    ms = speed_core.measure_latency(local_server)
    assert ms is not None and 0 < ms < 1000


def test_measure_latency_needs_a_user_agent_like_the_real_servers(local_server, monkeypatch):
    monkeypatch.setattr(speed_core, "HEADERS", {})
    assert speed_core.measure_latency(local_server) is None


def test_measure_latency_is_none_for_an_unreachable_server():
    assert speed_core.measure_latency({"host": "127.0.0.1:1", "scheme": "http"}, timeout=1) is None


def test_pick_server_takes_the_lowest_latency_reachable_server():
    servers = [make_server("far"), make_server("near"), make_server("down")]
    latency = {"far": 90.0, "near": 6.4, "down": None}
    best, ping = speed_core.pick_server(servers, probe=lambda s, samples=5: latency[s["name"]])
    assert (best["name"], ping) == ("near", 6.4)


def test_pick_server_rechecks_the_finalists_with_more_samples():
    calls = []

    def probe(server, samples=5):
        calls.append((server["name"], samples))
        return {"a": 10.0, "b": 11.0, "c": 12.0, "d": 50.0}[server["name"]]

    speed_core.pick_server([make_server(n) for n in "abcd"], probe=probe)
    finalists = [c for c in calls if c[1] > 5]
    assert sorted(name for name, _ in finalists) == ["a", "b", "c"]


def test_pick_server_without_a_reachable_server_is_an_error():
    with pytest.raises(RuntimeError, match="No speed test server reachable"):
        speed_core.pick_server([make_server("x")], probe=lambda s, samples=5: None)


# -- transfer accuracy ---------------------------------------------------------

@pytest.mark.parametrize("test", ["download", "upload"])
def test_measured_speed_matches_a_server_with_a_known_rate(local_server, test):
    SpeedHandler.rate = 2_000_000
    samples = []
    result = speed_core.measure_speed(local_server, test, lambda p, live: samples.append((p, live)),
                                      streams=4, warmup=0.6, duration=2.6)
    expected = 4 * 2_000_000 * 8 / 1e6
    assert result == pytest.approx(expected, rel=0.15)


def test_samples_report_progress_and_a_moving_live_speed(local_server):
    SpeedHandler.rate = 2_000_000
    samples = []
    speed_core.measure_speed(local_server, "download", lambda p, live: samples.append((p, live)),
                             streams=2, warmup=0.3, duration=1.5)
    progress = [p for p, _ in samples]
    assert progress == sorted(progress) and 0 < progress[0] < 1 and progress[-1] == 1.0
    assert samples[-1][1] == pytest.approx(2 * 2_000_000 * 8 / 1e6, rel=0.3)


def test_measure_speed_with_a_dead_server_raises():
    dead = {"host": "127.0.0.1:1", "scheme": "http"}
    with pytest.raises(RuntimeError, match="did not respond"):
        speed_core.measure_speed(dead, "download", lambda p, live: None, streams=2, warmup=0.1, duration=0.6)


# -- run() ---------------------------------------------------------------------

def fake_run(test, **overrides):
    events = []
    kwargs = dict(
        fetch=lambda: [make_server("near")],
        probe=lambda s, samples=5: 6.4,
        transfer=lambda server, kind, on_sample: [on_sample(0.5, 100.0), on_sample(1.0, 120.0), 118.5][2],
    )
    kwargs.update(overrides)
    final = speed_core.run(events.append, test, **kwargs)
    return events, final


def phases(events):
    names = [e["phase"] for e in events]
    return [p for i, p in enumerate(names) if i == 0 or p != names[i - 1]]


@pytest.mark.parametrize("test", ["download", "upload"])
def test_run_reports_only_the_requested_step(test):
    events, final = fake_run(test)
    assert phases(events) == ["config", "server", "ping", test, "done"]
    assert final[test] == 118.5
    assert final["download" if test == "upload" else "upload"] is None
    assert (final["live"], final["ping"], final["server"], final["error"]) == (118.5, 6.4, "near, X", None)
    assert final == events[-1]


@pytest.mark.parametrize("test", ["download", "upload"])
def test_run_step_starts_from_zero_and_streams_live_speed(test):
    events, _ = fake_run(test)
    step = [e for e in events if e["phase"] == test]
    assert step[0]["live"] is None and step[0]["progress"] == 0.0
    assert [(e["progress"], e["live"]) for e in step[1:3]] == [(0.5, 100.0), (1.0, 120.0)]


def test_run_rejects_an_unknown_test_name():
    _, final = fake_run("both")
    assert final["phase"] == "error" and "Unknown speed test" in final["error"]


def test_run_reports_a_server_list_failure():
    def broken():
        raise OSError("offline")

    _, final = fake_run("download", fetch=broken)
    assert final["phase"] == "error" and "server list" in final["error"]


def test_run_reports_when_no_server_is_reachable():
    _, final = fake_run("download", probe=lambda s, samples=5: None)
    assert final["phase"] == "error" and final["error"] == "No speed test server reachable"


def test_run_reports_a_transfer_failure():
    def broken(server, kind, on_sample):
        raise RuntimeError("Speed test server did not respond")

    _, final = fake_run("upload", transfer=broken)
    assert final["error"] == "Speed test server did not respond"


@pytest.mark.parametrize("value, fraction", [
    (None, 0.0), (-5, 0.0), (0, 0.0), (5, 1 / 8), (7.5, 1.5 / 8), (25, 3 / 8),
    (1000, 1.0), (5000, 1.0),
])
def test_scale_fraction_follows_the_marks(value, fraction):
    assert speed_core.scale_fraction(value) == pytest.approx(fraction)
