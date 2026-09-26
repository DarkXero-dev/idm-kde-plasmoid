import http.client
import json
import os
import statistics
import threading
import time
import urllib.request
from collections import deque
from concurrent.futures import ThreadPoolExecutor

SERVERS_URL = "https://www.speedtest.net/api/js/servers?engine=js&limit={limit}"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; IDMQuotaMonitor)"}

CANDIDATES = 12
FINALISTS = 3
STREAMS = 8
WARMUP = 2.0
DURATION = 10.0
SAMPLE_EVERY = 0.25
LIVE_WINDOW = 1.0
DOWNLOAD_BYTES = 25_000_000
UPLOAD_BYTES = 10_000_000
CHUNK = 65536

SCALE = (0, 5, 10, 25, 50, 100, 250, 500, 1000)


def scale_fraction(mbps):
    if not mbps or mbps <= 0:
        return 0.0
    if mbps >= SCALE[-1]:
        return 1.0
    for i in range(len(SCALE) - 1):
        if mbps < SCALE[i + 1]:
            return (i + (mbps - SCALE[i]) / (SCALE[i + 1] - SCALE[i])) / (len(SCALE) - 1)


def fetch_servers(limit=CANDIDATES):
    request = urllib.request.Request(SERVERS_URL.format(limit=limit), headers=HEADERS)
    with urllib.request.urlopen(request, timeout=15) as response:
        data = json.load(response)
    return [{"id": str(s["id"]), "name": s["name"], "country": s["country"],
             "sponsor": s["sponsor"], "host": s["host"], "scheme": "https"}
            for s in data if s.get("host")]


def _connect(server, timeout):
    host, _, port = server["host"].partition(":")
    cls = http.client.HTTPConnection if server.get("scheme") == "http" else http.client.HTTPSConnection
    return cls(host, int(port) if port else None, timeout=timeout)


def measure_latency(server, samples=5, timeout=5):
    """Median round trip on one kept-alive connection; the first request pays for the TLS handshake."""
    try:
        conn = _connect(server, timeout)
        times = []
        for i in range(samples + 1):
            start = time.perf_counter()
            conn.request("GET", f"/latency.txt?x={time.time_ns()}.{i}", headers=HEADERS)
            response = conn.getresponse()
            body = response.read()
            elapsed = time.perf_counter() - start
            if response.status != 200 or not body.startswith(b"test=test"):
                return None
            if i:
                times.append(elapsed)
        conn.close()
        return round(statistics.median(times) * 1000, 1)
    except Exception:
        return None


def pick_server(servers, probe=measure_latency):
    with ThreadPoolExecutor(len(servers) or 1) as pool:
        first = list(pool.map(probe, servers))
    reachable = sorted(((ms, i) for i, ms in enumerate(first) if ms is not None))
    if not reachable:
        raise RuntimeError("No speed test server reachable")
    finalists = [servers[i] for _, i in reachable[:FINALISTS]]
    with ThreadPoolExecutor(len(finalists)) as pool:
        second = list(pool.map(lambda s: probe(s, samples=12), finalists))
    rechecked = [(ms if ms is not None else first[servers.index(s)], n)
                 for n, (s, ms) in enumerate(zip(finalists, second))]
    ms, n = min(rechecked)
    return finalists[n], ms


def measure_speed(server, test, on_sample, streams=STREAMS, warmup=WARMUP, duration=DURATION,
                  clock=time.perf_counter):
    """Parallel transfers against one server; the result skips the warm-up so TCP ramp-up is not counted."""
    counts = [0] * streams
    conns = [None] * streams
    stop = threading.Event()
    body = memoryview(os.urandom(CHUNK))

    def download(conn, nocache, i):
        conn.request("GET", f"/download?nocache={nocache}&size={DOWNLOAD_BYTES}", headers=HEADERS)
        response = conn.getresponse()
        if response.status != 200:
            raise OSError(f"HTTP {response.status}")
        while not stop.is_set():
            chunk = response.read(CHUNK)
            if not chunk:
                break
            counts[i] += len(chunk)

    def upload(conn, nocache, i):
        conn.putrequest("POST", f"/upload?nocache={nocache}")
        conn.putheader("User-Agent", HEADERS["User-Agent"])
        conn.putheader("Content-Length", str(UPLOAD_BYTES))
        conn.endheaders()
        sent = 0
        while sent < UPLOAD_BYTES and not stop.is_set():
            conn.send(body)
            sent += CHUNK
            counts[i] += CHUNK
        if not stop.is_set():
            conn.getresponse().read()

    def worker(i):
        transfer = download if test == "download" else upload
        while not stop.is_set():
            try:
                conns[i] = _connect(server, 10)
                transfer(conns[i], os.urandom(4).hex(), i)
                conns[i].close()
            except Exception:
                stop.wait(0.05)

    threads = [threading.Thread(target=worker, args=(i,), daemon=True) for i in range(streams)]
    start = clock()
    for thread in threads:
        thread.start()

    window = deque([(0.0, 0)])
    mark, elapsed, total = None, 0.0, 0
    try:
        while elapsed < duration:
            time.sleep(min(SAMPLE_EVERY, max(duration - elapsed, 0.001)))
            elapsed = clock() - start
            total = sum(counts)
            if mark is None and elapsed >= warmup:
                mark = (elapsed, total)
            window.append((elapsed, total))
            while len(window) > 1 and window[0][0] < elapsed - LIVE_WINDOW:
                window.popleft()
            t0, b0 = window[0]
            live = (total - b0) * 8 / (elapsed - t0) / 1e6 if elapsed > t0 else 0.0
            on_sample(min(elapsed / duration, 1.0), round(live, 2))
    finally:
        stop.set()
        for conn in conns:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass
    if total == 0:
        raise RuntimeError("Speed test server did not respond")
    mark_time, mark_bytes = mark
    return round((total - mark_bytes) * 8 / (elapsed - mark_time) / 1e6, 2)


def run(progress, test, fetch=fetch_servers, probe=measure_latency, transfer=measure_speed):
    state = {"phase": "config", "progress": 0.0, "ping": None, "download": None,
             "upload": None, "server": None, "live": None, "error": None}

    def emit(phase, value):
        state["phase"], state["progress"] = phase, value
        progress(dict(state))

    def on_sample(fraction, live):
        state["live"] = live
        emit(test, fraction)

    try:
        if test not in ("download", "upload"):
            raise ValueError(f"Unknown speed test: {test}")
        emit("config", 0.0)
        try:
            servers = fetch()
        except Exception as e:
            raise RuntimeError(f"Could not fetch the speed test server list: {e}")
        if not servers:
            raise RuntimeError("No speed test servers available")
        emit("server", 0.0)
        best, state["ping"] = pick_server(servers, probe)
        state["server"] = f"{best['name']}, {best['country']}"
        emit("ping", 1.0)

        emit(test, 0.0)
        state[test] = transfer(best, test, on_sample)
        state["live"] = state[test]
        emit(test, 1.0)
        emit("done", 1.0)
    except Exception as e:
        state["error"] = str(e)
        emit("error", state["progress"])
    return dict(state)
