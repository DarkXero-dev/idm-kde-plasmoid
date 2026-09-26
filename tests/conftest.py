import os
import shutil
import sys

import pytest

sys.dont_write_bytecode = True

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "idm-quota-monitor"))
sys.path.append(os.path.join(ROOT, "Win"))


@pytest.fixture(autouse=True)
def remove_test_leftovers(tmp_path):
    yield
    shutil.rmtree(tmp_path, ignore_errors=True)


def pytest_sessionfinish(session):
    basetemp = session.config._tmp_path_factory.getbasetemp()
    shutil.rmtree(os.path.dirname(str(basetemp)), ignore_errors=True)
    for folder in ("tests", "Win", "idm-quota-monitor"):
        shutil.rmtree(os.path.join(ROOT, folder, "__pycache__"), ignore_errors=True)
