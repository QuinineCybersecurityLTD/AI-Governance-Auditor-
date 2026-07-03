"""Honesty layer: what the BOM CANNOT say because the record doesn't know it.

Dependency versions and licenses can be automated; training-data provenance
and governance narrative generally cannot. Anything missing is flagged as
manual-input-required - never left silently blank, never invented. The same
missing fields also surface as Article 10/11 findings in the audit.
"""

from __future__ import annotations

from pydantic import BaseModel

from aigov.record import SystemRecord


class BomGap(BaseModel):
    component: str
    field: str
    hint: str


def manual_input_gaps(record: SystemRecord) -> list[BomGap]:
    gaps: list[BomGap] = []
    for d in record.datasets:
        if not d.provenance:
            gaps.append(BomGap(
                component=f"dataset:{d.name}", field="provenance",
                hint="Collection process and origin cannot be inferred automatically - "
                     "document how and why this data was collected (Art 10(2)(b))."))
        if not d.license:
            gaps.append(BomGap(
                component=f"dataset:{d.name}", field="license",
                hint="Dataset licensing/usage terms require manual confirmation."))
        if d.contains_personal_data is None:
            gaps.append(BomGap(
                component=f"dataset:{d.name}", field="contains_personal_data",
                hint="Personal-data status must be determined by a human (GDPR scoping)."))
    for m in record.models:
        if not m.license:
            gaps.append(BomGap(
                component=f"model:{m.name}", field="license",
                hint="Model license requires manual verification against the source."))
        if m.is_foundation_model and not m.source_url:
            gaps.append(BomGap(
                component=f"model:{m.name}", field="source_url",
                hint="Third-party foundation model without a source reference - "
                     "supply-chain provenance is unverifiable (OWASP LLM03)."))
    for dep in record.dependencies:
        if not dep.version or not dep.license:
            gaps.append(BomGap(
                component=f"dependency:{dep.name}", field="version/license",
                hint="Pin the version and confirm the license (usually automatable "
                     "from the package manager)."))
    if not record.evaluations:
        gaps.append(BomGap(
            component="system", field="evaluations",
            hint="No evaluation results declared - performance claims in the BOM "
                 "would be unsubstantiated (Annex IV 2(g))."))
    if not record.known_limitations:
        gaps.append(BomGap(
            component="system", field="known_limitations",
            hint="No documented limitations. Every real system has them; an empty "
                 "list reads as 'not assessed', not 'none'."))
    return gaps
