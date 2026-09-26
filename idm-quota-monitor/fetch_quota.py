#!/usr/bin/env python3
"""
Fetches the quota of every service on the IDM login stored in
~/.config/IDMQuota/config.conf and prints one JSON line.

Modes:
  fetch_quota.py                           quota of every service
  fetch_quota.py --list                    list services only
  fetch_quota.py --write-config HEXU HEXP  save credentials (hex-encoded args)
"""

import base64
import hashlib
import json
import os
import sys

CONFIG_PATH = os.path.expanduser("~/.config/IDMQuota/config.conf")


def _fernet():
    from cryptography.fernet import Fernet
    with open("/etc/machine-id") as f:
        mid = f.read().strip()
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(mid.encode()).digest()))


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
    for key in ("username", "password"):
        if config.get(key, "").startswith("gAAA"):
            try:
                config[key] = _fernet().decrypt(config[key].encode()).decode()
            except Exception:
                pass
    return config


def write_config(username, password):
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    f = _fernet()
    fd = os.open(CONFIG_PATH, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as out:
        os.fchmod(out.fileno(), 0o600)
        out.write(f"username={f.encrypt(username.encode()).decode()}\n"
                  f"password={f.encrypt(password.encode()).decode()}\n")


def _emit(obj):
    print(json.dumps(obj))


def _fail(message):
    _emit({"error": message, "services": []})
    return 1


def main(argv):
    if argv[:1] == ["--write-config"]:
        try:
            write_config(bytes.fromhex(argv[1]).decode("utf-8"),
                         bytes.fromhex(argv[2]).decode("utf-8"))
        except Exception as e:
            _emit({"ok": False, "error": str(e)})
            return 1
        _emit({"ok": True})
        return 0

    try:
        import idm_core
        config = read_config()
        username, password = config.get("username", ""), config.get("password", "")
        if not username or not password:
            return _fail("No credentials: open the widget Settings")
        action = idm_core.list_services if argv[:1] == ["--list"] else idm_core.fetch
        _emit(action(username, password))
        return 0
    except ImportError as e:
        return _fail(f"Missing dependency: pip install {e.name}")
    except Exception as e:
        return _fail(str(e))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
