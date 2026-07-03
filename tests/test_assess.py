import datetime as dt
from pathlib import Path

import pytest

from aigov import knowledge
from aigov.assess import Status, audit
from aigov.classify import classify
from aigov.record import SystemRecord

EXAMPLE = Path(__file__).parent.parent / "examples" / "resume_screener.yaml"


@pytest.fixture(scope="module")
def kb():
    return knowledge.load()


@pytest.fixture(scope="module")
def result(kb):
    record = SystemRecord.from_yaml(EXAMPLE)
    return audit(record, kb, classify(record, kb), assessment_date=dt.date(2026, 7, 3))


def test_knowledge_base_loads_and_validates(kb):
    assert kb.version
    assert {a.article for a in kb.articles} == {"9", "10", "11", "13", "14", "15"}
    # every mapping must carry a rationale - no rationale, no link
    for article in kb.articles:
        for ob in article.obligations:
            for maps in ob.mappings.values():
                for m in maps:
                    assert m.rationale.strip(), f"{ob.id} -> {m.ref} has no rationale"


def test_auto_evidence_from_bom_fields(result):
    """The dataset with missing provenance must surface as a partial on Art 10(2)(b)."""
    f = next(f for f in result.findings if f.obligation_id == "art10.2b")
    assert f.status == Status.PARTIAL
    assert "cv-parsing-corpus" in f.rationale


def test_timeline_awareness(result):
    # Assessment on 2026-07-03: Annex III high-risk obligations apply from
    # 2027-12-02 post-Omnibus -> nothing is in force yet.
    assert all(not f.in_force for f in result.findings)
    assert all(f.applies_from == dt.date(2027, 12, 2) for f in result.findings)


def test_llm_conditional_mappings_included(result):
    f = next(f for f in result.findings if f.obligation_id == "art10.2b")
    owasp_refs = [m.ref for m in f.mappings.get("owasp_llm", [])]
    assert "LLM03" in owasp_refs and "LLM04" in owasp_refs


def test_gap_prioritisation_orders_high_severity_first(result):
    gaps = sorted(
        (f for f in result.findings if f.priority_score > 0),
        key=lambda f: f.priority_score, reverse=True,
    )
    assert gaps, "example must produce gaps"
    assert gaps[0].severity == "high"


def test_art11_bom_auto_evidence_compliant(result):
    """CandidateRank declares complete model/dependency metadata, so the
    Annex IV component-documentation obligation is met from the record alone."""
    f = next(f for f in result.findings if f.obligation_id == "art11.annexIV.2bc")
    assert f.status == Status.COMPLIANT
    assert "third-party" in f.rationale


def test_art11_reuses_art10_dataset_evidence(result):
    """The same missing provenance surfaces under both Art 10 and Art 11."""
    f10 = next(f for f in result.findings if f.obligation_id == "art10.2b")
    f11 = next(f for f in result.findings if f.obligation_id == "art11.annexIV.2d")
    assert f10.status == Status.PARTIAL and f11.status == Status.PARTIAL
    assert "cv-parsing-corpus" in f11.rationale


def test_art14_5_not_applicable_without_biometrics(result):
    f = next(f for f in result.findings if f.obligation_id == "art14.5")
    assert f.status == Status.NOT_APPLICABLE


def test_art14_5_applicable_for_biometric_system(kb):
    record = SystemRecord.from_yaml(EXAMPLE)
    record.classification.use_case_tags.append("biometric_identification")
    res = audit(record, kb, classify(record, kb), assessment_date=dt.date(2026, 7, 3))
    f = next(f for f in res.findings if f.obligation_id == "art14.5")
    # applicable but unanswered -> Gap, not N/A
    assert f.status == Status.GAP


def test_art15_owasp_density_for_llm_system(result):
    f = next(f for f in result.findings if f.obligation_id == "art15.5")
    owasp_refs = {m.ref for m in f.mappings.get("owasp_llm", [])}
    assert owasp_refs == {"LLM01", "LLM02", "LLM04", "LLM10"}
    assert f.status == Status.PARTIAL  # one 'no' + one 'partial' evidence item


def test_full_scope_obligation_count(result):
    # 16 (Arts 9+10) + 16 (Arts 11,13,14,15) obligations assessed
    assert len(result.findings) == 32


def test_not_applicable_when_condition_unmet(kb):
    record = SystemRecord.from_yaml(EXAMPLE)
    for d in record.datasets:
        d.contains_personal_data = False
    res = audit(record, kb, classify(record, kb), assessment_date=dt.date(2026, 7, 3))
    f = next(f for f in res.findings if f.obligation_id == "art10.5")
    assert f.status == Status.NOT_APPLICABLE
