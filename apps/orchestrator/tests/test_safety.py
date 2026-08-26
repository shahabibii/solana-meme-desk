"""Safety scoring tests (offline logic)."""

from orchestrator.models import SafetyReport


def test_safety_report_verdict() -> None:
    r = SafetyReport(mint="x", score=80, passed=True)
    assert r.verdict == "PASS"
    r2 = SafetyReport(mint="x", score=30, passed=False, reasons=["honeypot"])
    assert r2.verdict == "BLOCK"
