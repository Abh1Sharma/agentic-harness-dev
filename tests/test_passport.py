import base64
import os
import subprocess
import sys
from datetime import date

import pytest

from reuse_router.catalog import CATALOG, get_tool
from reuse_router.passport import KEY_ENV, issue, public_key_info, verify

EMMA = get_tool("emma")


@pytest.fixture(autouse=True)
def demo_key(monkeypatch):
    monkeypatch.delenv(KEY_ENV, raising=False)


def test_fresh_passport_is_valid_for_the_certified_commit():
    result = verify(issue(EMMA), current_commit=EMMA.commit, today=date(2026, 9, 1))
    assert result["status"] == "VALID"
    assert [step["ok"] for step in result["steps"]] == [True, True, True]


def test_every_catalog_asset_gets_a_verifiable_passport():
    for tool in CATALOG:
        assert verify(issue(tool), current_commit=tool.commit, today=date(2026, 9, 1))["status"] == "VALID"


def test_issuing_is_deterministic():
    assert issue(EMMA) == issue(EMMA)


@pytest.mark.parametrize(
    ("path", "value"),
    [(("risk_tier",), "low"), (("approved_data_up_to",), "restricted"), (("asset", "commit"), "0" * 40),
     (("expires_on",), "2099-01-01")],
)
def test_changing_any_field_is_detected(path, value):
    passport = issue(EMMA)
    target = passport["payload"]
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    result = verify(passport, current_commit=EMMA.commit)
    assert result["status"] == "TAMPERED"
    assert result["steps"][1]["ok"] is None  # nothing else is trusted


def test_dropping_a_failed_check_is_detected():
    passport = issue(EMMA)
    passport["payload"]["checks"].pop()
    assert verify(passport)["status"] == "TAMPERED"


@pytest.mark.parametrize("broken", [{}, {"payload": {}}, {"payload": {}, "signature": "x"},
                                    {"payload": {}, "signature": {"value": "not base64!"}}, []])
def test_malformed_passports_are_tampered_not_errors(broken):
    assert verify(broken)["status"] == "TAMPERED"


def test_new_commit_suspends_the_passport():
    result = verify(issue(EMMA), current_commit="f" * 40, today=date(2026, 9, 1))
    assert result["status"] == "SUSPENDED"
    assert "4f2c9e1" in result["steps"][2]["detail"]


def test_expired_passport():
    result = verify(issue(EMMA), current_commit=EMMA.commit, today=date(2027, 6, 3))
    assert result["status"] == "EXPIRED"


def test_configured_key_replaces_the_demo_key(monkeypatch):
    signed_with_demo = issue(EMMA)
    monkeypatch.setenv(KEY_ENV, base64.b64encode(os.urandom(32)).decode())
    assert public_key_info()["demo_key"] is False
    result = verify(signed_with_demo)
    assert result["status"] == "TAMPERED"
    assert "different key" in result["steps"][0]["detail"]
    assert verify(issue(EMMA))["status"] == "VALID"


def test_keygen_prints_a_usable_key():
    out = subprocess.run([sys.executable, "-m", "reuse_router.passport", "keygen"],
                         capture_output=True, text=True, check=True).stdout
    value = out.splitlines()[0].split("=", 1)[1]
    assert len(base64.b64decode(value)) == 32
