"""Safety scoring tests."""

from orchestrator.agents.safety import evaluate_safety
from orchestrator.models import SafetyReport


def test_safety_report_verdict() -> None:
    r = SafetyReport(mint="x", score=80, passed=True)
    assert r.verdict == "PASS"
    r2 = SafetyReport(mint="x", score=30, passed=False, reasons=["honeypot"])
    assert r2.verdict == "BLOCK"


def test_pump_path_allows_mint_authority_and_no_jupiter() -> None:
    info = {
        "mintAuthority": "SomeAuth",
        "freezeAuthority": None,
    }
    report = evaluate_safety(
        mint="mint111111111111111111111111111111111",
        info=info,
        can_sell=False,
        source="pump",
        min_score=65,
    )
    assert report.passed
    assert "mint_authority_active" in report.reasons
    assert "no_jupiter_yet" in report.reasons


def test_pump_path_blocks_freeze_authority() -> None:
    info = {
        "mintAuthority": "SomeAuth",
        "freezeAuthority": "Freezer",
    }
    report = evaluate_safety(
        mint="mint111111111111111111111111111111111",
        info=info,
        can_sell=False,
        source="pump",
        min_score=65,
    )
    assert not report.passed
    assert "freeze_authority_active" in report.reasons


def test_graduated_token_requires_jupiter_and_no_mint_auth() -> None:
    info = {
        "mintAuthority": "SomeAuth",
        "freezeAuthority": None,
    }
    report = evaluate_safety(
        mint="mint111111111111111111111111111111111",
        info=info,
        can_sell=False,
        source="dex",
        min_score=65,
    )
    assert not report.passed
