"""Local tests for find_staff directory tool."""

from __future__ import annotations

from agent.directory import find_staff


def test_sales_team_head_no_invented_staff():
    result = find_staff("Who is the sales team head?")
    assert result["match_count"] == 0
    assert result["matches"] == []
    assert result["note"] and "sales" in result["note"].lower()
    # May suggest grants/CEO as alternatives, but never invent Development Director
    blob = (result.get("note") or "").lower()
    assert "development director" not in blob or "do not invent" in blob
    names = " ".join(s.get("name", "") for s in result.get("suggestions") or []).lower()
    assert "yannick" not in names


def test_yannick_doktor_does_not_hallucinate():
    result = find_staff("Yannick Doktor sales manager")
    names = " ".join(m["name"].lower() for m in result["matches"])
    assert "yannick" not in names
    assert "doktor" not in names
    assert result["match_count"] == 0


def test_yannick_alone_does_not_match_nick():
    result = find_staff("Yannick")
    names = " ".join(m["name"].lower() for m in result["matches"])
    assert "nick" not in names
    assert "trimbach" not in names
    assert "mick" not in names
    assert result["match_count"] == 0


def test_business_development_no_false_name_hits():
    result = find_staff("business development")
    assert result["match_count"] == 0
    assert result.get("suggestions")


def test_billing_returns_accounts_payable_or_finance():
    result = find_staff("Who handles billing?")
    assert result["match_count"] >= 1
    blob = " ".join(
        f"{m['name']} {m['title']}".lower() for m in result["matches"]
    )
    assert any(
        k in blob
        for k in ("payable", "accountant", "controller", "cfo", "fiscal", "payroll")
    )
    # Prefer Caseam Pleasant in top results for AP
    top = " ".join(m["name"].lower() for m in result["matches"][:3])
    assert "pleasant" in top or "donnelly" in top or "ekoh" in top or "foster" in top


def test_preferred_name_val():
    result = find_staff("Val Bolen")
    assert result["match_count"] >= 1
    assert any("bolen" in m["name"].lower() for m in result["matches"])


def test_misspelled_full_names():
    assert any("jeffries" in m["name"].lower() for m in find_staff("Eren Jeffries")["matches"])
    assert any("jeffries" in m["name"].lower() for m in find_staff("Erin Jeffres")["matches"])
    assert any("cooper" in m["name"].lower() for m in find_staff("Eddy Cooper")["matches"])
    top = find_staff("Eddy Cooper")["matches"][0]["name"].lower()
    assert "eddie cooper" in top
    assert any("bolen" in m["name"].lower() for m in find_staff("Val Boln")["matches"])
    assert any("moody" in m["name"].lower() for m in find_staff("Ronda Moody")["matches"])


def test_first_name_only_unique():
    result = find_staff("Who is Keianna?")
    assert result["match_count"] >= 1
    assert "keianna" in result["matches"][0]["name"].lower()


def test_ambiguous_first_and_last_name():
    ashley = find_staff("Who is Ashley?")
    assert ashley["match_count"] >= 2
    assert ashley.get("clarify")
    names = " ".join(m["name"].lower() for m in ashley["matches"])
    assert "king" in names and "lewis" in names

    young = find_staff("Who is Young?")
    assert young["match_count"] >= 2
    assert young.get("clarify")
    names = " ".join(m["name"].lower() for m in young["matches"])
    assert "keianna" in names and "marquetta" in names

    smith = find_staff("Who is Smith?")
    assert smith["match_count"] >= 2
    assert smith.get("clarify")
