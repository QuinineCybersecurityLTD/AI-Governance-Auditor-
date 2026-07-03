"""Article 6 classification - runs before everything else, since it gates
which obligations even load.

Deterministic decision tree; every step emits a reasoning line so the
classification itself is defensible, not just the verdict.
"""

from __future__ import annotations

import datetime as dt
from enum import Enum

from pydantic import BaseModel

from aigov.knowledge import KnowledgeBase
from aigov.record import SystemRecord

# Systems already on the market before this date get the Omnibus watermarking
# grace period (Art 50(2) marking due 2026-12-02 instead of on placement).
ART50_MARKING_CUTOFF = dt.date(2026, 8, 2)


class RiskTier(str, Enum):
    HIGH_RISK_ANNEX_III = "high_risk_annex_iii"
    HIGH_RISK_ANNEX_I = "high_risk_annex_i"
    LIMITED_RISK_ART50 = "limited_risk_art50"
    MINIMAL_RISK = "minimal_risk"


class ClassificationResult(BaseModel):
    tier: RiskTier
    matched_categories: list[str] = []
    reasoning: list[str] = []
    art50_applies: bool = False
    marking_grace_applies: bool = False


def classify(record: SystemRecord, kb: KnowledgeBase) -> ClassificationResult:
    ci = record.classification
    reasoning: list[str] = []
    matched: list[str] = []

    # --- Step 1: Annex I product-safety route (Art 6(1), post-Omnibus) ----
    if ci.annex_i_product_area:
        if ci.is_safety_component and ci.failure_endangers_health_or_safety:
            reasoning.append(
                f"Art 6(1): safety component in Annex I product area "
                f"'{ci.annex_i_product_area}' whose failure could endanger "
                f"health or safety -> high-risk (Annex I route)."
            )
            return ClassificationResult(
                tier=RiskTier.HIGH_RISK_ANNEX_I,
                matched_categories=[f"annexI:{ci.annex_i_product_area}"],
                reasoning=reasoning,
                art50_applies=_art50(ci),
            )
        reasoning.append(
            f"Art 6(1) as amended by the Digital Omnibus: Annex I product area "
            f"'{ci.annex_i_product_area}' declared, but the system is "
            + ("not a safety component" if not ci.is_safety_component
               else "a safety component whose failure is not declared to "
                    "endanger health or safety (post-Omnibus narrowing)")
            + " -> Annex I route not triggered."
        )

    # --- Step 2: Annex III use-case matching (Art 6(2)) -------------------
    tags = set(ci.use_case_tags)
    for cat in kb.annex_iii_categories:
        hit = tags.intersection(cat.tags)
        if hit:
            matched.append(cat.id)
            reasoning.append(
                f"Art 6(2): use-case tag(s) {sorted(hit)} match {cat.id} "
                f"({cat.label})."
            )

    if matched:
        # --- Step 3: Art 6(3) derogation check -----------------------------
        if ci.performs_profiling:
            reasoning.append(
                "Art 6(3) final subparagraph: the system performs profiling of "
                "natural persons - derogations are unavailable; classification "
                "remains high-risk."
            )
            return ClassificationResult(
                tier=RiskTier.HIGH_RISK_ANNEX_III,
                matched_categories=matched,
                reasoning=reasoning,
                art50_applies=_art50(ci),
                marking_grace_applies=_marking_grace(ci),
            )
        if ci.derogation_claims:
            known = {d.id for d in kb.derogations}
            for claim, justification in ci.derogation_claims.items():
                if claim not in known:
                    reasoning.append(f"Derogation claim '{claim}' is not a valid Art 6(3) ground - ignored.")
                    continue
                label = next(d.label for d in kb.derogations if d.id == claim)
                reasoning.append(
                    f"Art 6(3) derogation accepted on ground {claim} ({label}): "
                    f"{justification} -> not high-risk despite Annex III match. "
                    f"Note: Art 6(4) documentation of this assessment is required."
                )
                return ClassificationResult(
                    tier=RiskTier.LIMITED_RISK_ART50 if _art50(ci) else RiskTier.MINIMAL_RISK,
                    matched_categories=matched,
                    reasoning=reasoning,
                    art50_applies=_art50(ci),
                    marking_grace_applies=_marking_grace(ci),
                )
        reasoning.append("No Art 6(3) derogation claimed -> high-risk (Annex III route).")
        return ClassificationResult(
            tier=RiskTier.HIGH_RISK_ANNEX_III,
            matched_categories=matched,
            reasoning=reasoning,
            art50_applies=_art50(ci),
            marking_grace_applies=_marking_grace(ci),
        )

    # --- Step 4: not high-risk; Art 50 transparency may still apply -------
    reasoning.append("No Annex I or Annex III route triggered -> not high-risk.")
    if _art50(ci):
        reasoning.append(
            "Art 50 applies: the system interacts with natural persons and/or "
            "generates synthetic content (transparency-only obligations)."
        )
        return ClassificationResult(
            tier=RiskTier.LIMITED_RISK_ART50,
            reasoning=reasoning,
            art50_applies=True,
            marking_grace_applies=_marking_grace(ci),
        )
    reasoning.append("Art 50 not triggered -> minimal risk; no AI Act obligations assessed.")
    return ClassificationResult(tier=RiskTier.MINIMAL_RISK, reasoning=reasoning)


def _art50(ci) -> bool:
    return ci.generates_synthetic_content or ci.interacts_with_natural_persons


def _marking_grace(ci) -> bool:
    return (
        ci.generates_synthetic_content
        and ci.placed_on_market_date is not None
        and ci.placed_on_market_date < ART50_MARKING_CUTOFF
    )
