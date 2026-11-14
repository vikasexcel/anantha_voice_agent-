"""Verify seed parsing counts and spot-check rules/staff from client docs."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.seed_from_docs import build_seed  # noqa: E402


def test_seed_counts():
    payload = build_seed()
    # Directory has ~100 staff rows across 3 pages
    assert len(payload.staff) >= 95, f"expected >=95 staff, got {len(payload.staff)}"
    assert len(payload.staff) <= 120, f"unexpectedly high staff count: {len(payload.staff)}"
    # Keyword table is large; allow a few missing flagged keywords
    assert len(payload.keyword_rules) >= 95, f"expected >=95 rules, got {len(payload.keyword_rules)}"
    assert len(payload.status_updates) == 4


def test_preferred_name_spot_checks():
    payload = build_seed()
    by_key = {
        (s.last_name.lower(), (s.first_preferred or s.first_legal).lower()): s
        for s in payload.staff
    }
    assert ("bolen", "val") in by_key
    assert by_key[("bolen", "val")].extension == "139"
    assert ("branson", "frank") in by_key
    assert by_key[("branson", "frank")].first_legal == "Luther"
    assert by_key[("walker", "david")].shareable is False


def test_no_extension_staff_flagged():
    payload = build_seed()
    missing = {
        (s.last_name, s.first_legal)
        for s in payload.staff
        if not s.extension and not s.external_number and s.shareable
    }
    expected = {
        ("Adams", "Candis"),
        ("Martin", "Jade"),
        ("Robinson", "Donna"),
        ("Shinn", "Tacola"),
        ("Thompson", "Skylar"),
        ("Thompson", "Cailyn"),
    }
    assert expected.issubset(missing), f"missing no-ext staff: {expected - missing}"


def test_keyword_aliases_and_flows():
    payload = build_seed()
    by_kw = {r.keyword: r for r in payload.keyword_rules}

    assert by_kw["CSBG"].action_type == "alias_of"
    assert "Utility Assistance" in (by_kw["HEAP"].target or by_kw["HEAP"].keyword)
    assert by_kw["HEAP"].action_type == "alias_of"

    util = by_kw["Utility Assistance"]
    assert util.action_type == "flow"
    assert util.ambiguous is True  # x821 open question
    assert util.followup_question and "disconnect" in util.followup_question.lower()

    dv = by_kw["Domestic Violence"]
    assert dv.action_type == "transfer_external"
    assert dv.target == "9374566891"

    greene = by_kw["Greene County"]
    assert greene.target == "601"
    assert greene.ambiguous is True


def test_status_winter_crisis():
    payload = build_seed()
    messages = " ".join(s.message for s in payload.status_updates)
    assert "Winter Crisis" in messages
    assert "November 1, 2026" in messages


def test_katie_and_keianna_directory_extensions():
    payload = build_seed()
    katie = next(
        s
        for s in payload.staff
        if "O'Donoghue" in s.last_name.replace("'", "'") or "ODonoghue" in s.last_name.replace("'", "")
        or s.first_preferred == "Katie"
    )
    keianna = next(s for s in payload.staff if s.first_preferred == "Keianna")
    assert katie.extension == "157"
    assert keianna.extension == "157"
    assert katie.ambiguous and keianna.ambiguous
