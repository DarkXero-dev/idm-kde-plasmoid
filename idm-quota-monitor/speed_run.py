#!/usr/bin/env python3
"""Runs one speed test (download or upload); progress goes to a JSON file, the final result to stdout."""

import json
import os
import sys

import speed_core

PROGRESS_PATH = os.path.join(os.environ.get("XDG_RUNTIME_DIR") or "/tmp",
                             "idm-speedtest.json")


def write_progress(state):
    tmp = PROGRESS_PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f)
    os.replace(tmp, PROGRESS_PATH)


def main(argv):
    final = speed_core.run(write_progress, argv[0] if argv else "")
    print(json.dumps(final))
    return 1 if final["error"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
