"""Per-obligation assessment: evidence -> verdict + rationale + timeline flag.

Evidence resolution has two paths:
- questionnaire keys -> record.evidence[key]
- "auto." keys       -> derived from structured SystemRecord fields (the
  BOM-facing data), so Article 10 findings react to the same fields the
  AI-BOM exports. This is the Part 1 <-> Part 2 wiring.
"""

from __future__ import annotations

import datetime as dt
from enum import Enum
from typing import Callable, Optional

from pydantic import BaseModel

from aigov.classify import ClassificationResult, RiskTier
from aigov.knowledge import KnowledgeBase, Mapping, Obligation
from aigov.record import Answer, EvidenceItem, SystemRecord


class Status(str, Enum):
    COMPLIANT = "Compliant"
    PARTIAL = "Partial"
    GAP = "Gap"
    NOT_APPLICABLE = "Not Applicable"


class Finding(BaseModel):
    article: str
    obligation_id: str
    clause: str
    severity: str
    status: Status
    in_force: bool
    applies_from: dt.date
    rationale: str
    mappings: dict[str, list[Mapping]]
    priority_score: float = 0.0


class AuditResult(BaseModel):
    system_name: str
    knowledge_version: str
    assessment_date: dt.date
    classification: ClassificationResult
    findings: list[Finding]
    timeline_note: str


# --------------------------------------------------------------------------
# auto-evidence resolvers: derive an EvidenceItem from the structured record
# --------------------------------------------------------------------------

def _dataset_field_evidence(record: SystemRecord, field: str, label: str) -> EvidenceItem:
    """Compliant if every dataset documents `field`; partial if some do."""
    if not record.datasets:
        return EvidenceItem(answer=Answer.NO, note="No datasets are declared in the system record.")
    missing = [d.name for d in record.datasets if not getattr(d, field)]
    if not missing:
        return EvidenceItem(
            answer=Answer.YES,
            note=f"All {len(record.datasets)} declared dataset(s) document {label}.",
        )
    if len(missing) == len(record.datasets):
        return EvidenceItem(
            answer=Answer.NO,
            note=f"No declared dataset documents {label} (missing: {', '.join(missing)}).",
        )
    return EvidenceItem(
        answer=Answer.PARTIAL,
        note=f"{label} missing for dataset(s): {', '.join(missing)}.",
    )


def _list_presence_evidence(items: list, label: str, detail: str) -> EvidenceItem:
    if items:
        return EvidenceItem(answer=Answer.YES, note=f"{len(items)} {label} declared in the system record ({detail}).")
    return EvidenceItem(answer=Answer.NO, note=f"No {label} declared in the system record.")


def _model_components_evidence(record: SystemRecord) -> EvidenceItem:
    """Compliant if every model component carries version and license -
    the minimum for an Annex IV component record and a usable BOM entry."""
    if not record.models:
        return EvidenceItem(answer=Answer.NO, note="No model components are declared in the system record.")
    incomplete = [m.name for m in record.models if not (m.version and m.license)]
    if not incomplete:
        third_party = sum(1 for m in record.models if m.provider)
        return EvidenceItem(
            answer=Answer.YES,
            note=f"All {len(record.models)} model component(s) documented with version and license "
                 f"({third_party} third-party/pre-trained).",
        )
    return EvidenceItem(
        answer=Answer.PARTIAL,
        note=f"Model component(s) missing version or license: {', '.join(incomplete)}.",
    )


def _dependency_inventory_evidence(record: SystemRecord) -> EvidenceItem:
    if not record.dependencies:
        return EvidenceItem(answer=Answer.NO, note="No dependency inventory in the system record.")
    incomplete = [d.name for d in record.dependencies if not (d.version and d.license)]
    if not incomplete:
        return EvidenceItem(
            answer=Answer.YES,
            note=f"All {len(record.dependencies)} dependencies pinned with version and license.",
        )
    return EvidenceItem(
        answer=Answer.PARTIAL,
        note=f"Dependencies missing version or license: {', '.join(incomplete)}.",
    )


AUTO_RESOLVERS: dict[str, Callable[[SystemRecord], EvidenceItem]] = {
    "auto.dataset_provenance": lambda r: _dataset_field_evidence(
        r, "provenance", "collection process and origin (provenance)"),
    "auto.dataset_preparation": lambda r: _dataset_field_evidence(
        r, "preparation", "data-preparation operations"),
    "auto.dataset_bias_assessment": lambda r: _dataset_field_evidence(
        r, "bias_assessment", "a bias examination"),
    "auto.dataset_known_gaps": lambda r: _dataset_field_evidence(
        r, "known_gaps", "known gaps or shortcomings"),
    "auto.model_components_documented": _model_components_evidence,
    "auto.dependency_inventory": _dependency_inventory_evidence,
    "auto.evaluation_results": lambda r: _list_presence_evidence(
        r.evaluations, "evaluation result(s)",
        "validation/testing outcomes with metrics"),
    "auto.known_limitations": lambda r: _list_presence_evidence(
        r.known_limitations, "known limitation(s)",
        "documented performance limitations"),
}


def resolve_evidence(record: SystemRecord, key: str) -> EvidenceItem:
    if key.startswith("auto."):
        resolver = AUTO_RESOLVERS.get(key)
        if resolver is None:
            return EvidenceItem(answer=Answer.NO, note=f"Unknown auto-evidence key '{key}'.")
        return resolver(record)
    item = record.evidence.get(key)
    if item is None:
        return EvidenceItem(answer=Answer.NO, note=f"Questionnaire item '{key}' was not answered.")
    return item


# --------------------------------------------------------------------------
# applicability & status combination
# --------------------------------------------------------------------------

_APPLICABILITY_PREDICATES: dict[str, Callable[[SystemRecord], bool]] = {
    "datasets_contain_personal_data": lambda r: any(
        d.contains_personal_data for d in r.datasets
    ),
    "use_case_remote_biometric_id": lambda r: (
        "biometric_identification" in r.classification.use_case_tags
    ),
}


def _obligation_applies(record: SystemRecord, ob: Obligation) -> bool:
    if ob.applicability is None:
        return True
    return any(
        _APPLICABILITY_PREDICATES.get(cond, lambda _: True)(record)
        for cond in ob.applicability.requires_any
    )


def _combine(items: list[EvidenceItem]) -> Status:
    answers = [i.answer for i in items]
    if all(a == Answer.NA for a in answers):
        return Status.NOT_APPLICABLE
    relevant = [a for a in answers if a != Answer.NA]
    if all(a == Answer.YES for a in relevant):
        return Status.COMPLIANT
    if all(a == Answer.NO for a in relevant):
        return Status.GAP
    return Status.PARTIAL


def _filter_mappings(record: SystemRecord, ob: Obligation) -> dict[str, list[Mapping]]:
    out: dict[str, list[Mapping]] = {}
    for fw, maps in ob.mappings.items():
        kept = [m for m in maps if m.when is None or (m.when == "llm_based" and record.is_llm_based)]
        if kept:
            out[fw] = kept
    return out


def _priority(severity: str, status: Status, in_force: bool) -> float:
    if status in (Status.COMPLIANT, Status.NOT_APPLICABLE):
        return 0.0
    sev = {"high": 3.0, "medium": 2.0, "low": 1.0}.get(severity, 1.0)
    gap_weight = 1.0 if status == Status.GAP else 0.5
    urgency = 2.0 if in_force else 1.0
    return sev * gap_weight * urgency


# --------------------------------------------------------------------------
# main entry point
# --------------------------------------------------------------------------

def audit(
    record: SystemRecord,
    kb: KnowledgeBase,
    classification: ClassificationResult,
    assessment_date: Optional[dt.date] = None,
) -> AuditResult:
    assessment_date = assessment_date or dt.date.today()
    findings: list[Finding] = []

    tier_to_regime = {
        RiskTier.HIGH_RISK_ANNEX_III: "high_risk_annex_iii",
        RiskTier.HIGH_RISK_ANNEX_I: "high_risk_annex_i",
    }
    active_regime = tier_to_regime.get(classification.tier)

    if active_regime is not None:
        regime = kb.regimes[active_regime]
        in_force = assessment_date >= regime.applies_from
        for article in kb.articles:
            for ob in article.obligations:
                if not _obligation_applies(record, ob):
                    findings.append(Finding(
                        article=article.article, obligation_id=ob.id, clause=ob.clause,
                        severity=ob.severity, status=Status.NOT_APPLICABLE,
                        in_force=in_force, applies_from=regime.applies_from,
                        rationale=f"Assessed against {ob.clause}: applicability "
                                  f"condition(s) {ob.applicability.requires_any} not met.",
                        mappings=_filter_mappings(record, ob),
                    ))
                    continue
                items = [resolve_evidence(record, k) for k in ob.evidence_keys]
                status = _combine(items)
                notes = "; ".join(i.note for i in items if i.note)
                rationale = f"Assessed against {ob.clause}: {notes}" if notes else f"Assessed against {ob.clause}."
                f = Finding(
                    article=article.article, obligation_id=ob.id, clause=ob.clause,
                    severity=ob.severity, status=status,
                    in_force=in_force, applies_from=regime.applies_from,
                    rationale=rationale,
                    mappings=_filter_mappings(record, ob),
                )
                f.priority_score = _priority(ob.severity, status, in_force)
                findings.append(f)

    regime_note = ""
    if active_regime is not None:
        regime = kb.regimes[active_regime]
        state = "already apply" if assessment_date >= regime.applies_from else "apply from"
        regime_note = (
            f" High-risk obligations for this system {state} "
            f"{regime.applies_from.isoformat()} ({regime.source})."
        )
    timeline_note = (
        kb.meta["frameworks"]["eu_ai_act"]["omnibus_status"].strip() + regime_note
    )

    return AuditResult(
        system_name=record.name,
        knowledge_version=kb.version,
        assessment_date=assessment_date,
        classification=classification,
        findings=findings,
        timeline_note=timeline_note,
    )
