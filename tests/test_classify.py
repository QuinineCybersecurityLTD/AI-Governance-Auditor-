import datetime as dt

import pytest

from aigov import knowledge
from aigov.classify import RiskTier, classify
from aigov.record import ClassificationInput, SystemRecord


@pytest.fixture(scope="module")
def kb():
    return knowledge.load()


def make_record(**cls_kwargs) -> SystemRecord:
    return SystemRecord(name="t", classification=ClassificationInput(**cls_kwargs))


def test_annex_iii_recruitment_is_high_risk(kb):
    r = make_record(use_case_tags=["recruitment_screening"])
    out = classify(r, kb)
    assert out.tier == RiskTier.HIGH_RISK_ANNEX_III
    assert "annexIII.4" in out.matched_categories


def test_profiling_defeats_derogation(kb):
    r = make_record(
        use_case_tags=["recruitment_screening"],
        performs_profiling=True,
        derogation_claims={"art6.3.d": "preparatory only"},
    )
    out = classify(r, kb)
    assert out.tier == RiskTier.HIGH_RISK_ANNEX_III
    assert any("profiling" in line for line in out.reasoning)


def test_valid_derogation_without_profiling_downgrades(kb):
    r = make_record(
        use_case_tags=["recruitment_screening"],
        performs_profiling=False,
        derogation_claims={"art6.3.a": "spell-checks job ads only"},
    )
    out = classify(r, kb)
    assert out.tier == RiskTier.MINIMAL_RISK


def test_post_omnibus_safety_component_narrowing(kb):
    # Safety component whose failure does NOT endanger health/safety:
    # post-Omnibus, not high-risk via Annex I.
    r = make_record(
        annex_i_product_area="machinery",
        is_safety_component=True,
        failure_endangers_health_or_safety=False,
    )
    out = classify(r, kb)
    assert out.tier == RiskTier.MINIMAL_RISK

    r2 = make_record(
        annex_i_product_area="machinery",
        is_safety_component=True,
        failure_endangers_health_or_safety=True,
    )
    assert classify(r2, kb).tier == RiskTier.HIGH_RISK_ANNEX_I


def test_art50_only_chatbot(kb):
    r = make_record(interacts_with_natural_persons=True)
    out = classify(r, kb)
    assert out.tier == RiskTier.LIMITED_RISK_ART50


def test_marking_grace_only_for_pre_aug2026_systems(kb):
    old = make_record(
        generates_synthetic_content=True,
        placed_on_market_date=dt.date(2026, 1, 1),
    )
    new = make_record(
        generates_synthetic_content=True,
        placed_on_market_date=dt.date(2026, 9, 1),
    )
    assert classify(old, kb).marking_grace_applies is True
    assert classify(new, kb).marking_grace_applies is False
