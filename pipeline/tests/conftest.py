import json
from pathlib import Path

import pytest


@pytest.fixture()
def landing_dir(tmp_path, monkeypatch):
    """Redirect the landing zone and fetch log into the test's tmp dir."""
    from dontdie import config

    monkeypatch.setattr(config, "LANDING_DIR", tmp_path / "landing")
    monkeypatch.setattr(config, "FETCH_LOG", tmp_path / "fetch_log.jsonl")
    return config.LANDING_DIR


@pytest.fixture()
def fixture_path():
    return Path(__file__).parent / "fixtures"


@pytest.fixture()
def ctgov_payload(fixture_path):
    return json.loads((fixture_path / "ctgov_studies.json").read_text())
