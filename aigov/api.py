"""aigov as a service: FastAPI layer over the same engine the CLI uses.

The SystemRecord is the API contract - the same Pydantic model that the CLI
loads from YAML is the JSON request body here, so CLI and SaaS can never
drift apart. Endpoints are stateless: no system data is persisted.
"""

from __future__ import annotations

import datetime as dt
from typing import Optional

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel

from aigov import __version__, knowledge
from aigov.auth import require_api_key
from aigov.assess import AuditResult, audit as run_audit
from aigov.bom import build_cdx, build_spdx, manual_input_gaps, validate_cdx, validate_spdx
from aigov.bom.gaps import BomGap
from aigov.classify import ClassificationResult, classify as run_classify
from aigov.record import SystemRecord
from aigov.report import render_markdown

app = FastAPI(
    title="AI Governance Auditor",
    version=__version__,
    description=(
        "EU AI Act (Arts 6, 9-15) compliance auditing crosswalked to "
        "ISO/IEC 42001, NIST AI RMF and OWASP LLM Top 10, plus AI-BOM "
        "generation (SPDX 3.0.1 AI Profile / CycloneDX 1.7 ML-BOM) - "
        "one SystemRecord in, evidence-backed findings and validated BOMs out."
    ),
)

# /health is open (load balancers need it); everything under /v1 requires an
# API key when AIGOV_API_KEYS is set, and is rate-limited per key.
v1 = APIRouter(prefix="/v1", dependencies=[Depends(require_api_key)])


class HealthResponse(BaseModel):
    status: str
    version: str
    knowledge_version: str
    articles_covered: list[str]


class AuditResponse(BaseModel):
    result: AuditResult
    report_markdown: Optional[str] = None


class BomResponse(BaseModel):
    spdx: dict
    cyclonedx: dict
    spdx_validation_errors: list[str]
    cyclonedx_validation_errors: list[str]
    manual_input_required: list[BomGap]


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    kb = knowledge.load()
    return HealthResponse(
        status="ok",
        version=__version__,
        knowledge_version=kb.version,
        articles_covered=sorted(a.article for a in kb.articles),
    )


@v1.post("/classify", response_model=ClassificationResult)
def classify(record: SystemRecord) -> ClassificationResult:
    """Article 6 classification only - fast pre-check."""
    return run_classify(record, knowledge.load())


@v1.post("/audit", response_model=AuditResponse)
def audit(
    record: SystemRecord,
    assessment_date: Optional[dt.date] = Query(default=None),
    include_report: bool = Query(default=False, description="Include rendered Markdown report"),
) -> AuditResponse:
    """Full audit: classification + per-obligation findings."""
    kb = knowledge.load()
    result = run_audit(record, kb, run_classify(record, kb), assessment_date)
    return AuditResponse(
        result=result,
        report_markdown=render_markdown(result) if include_report else None,
    )


@v1.post("/bom", response_model=BomResponse)
def bom(record: SystemRecord) -> BomResponse:
    """Generate both BOM formats; validation runs on every request and the
    errors are returned rather than hidden - an invalid BOM is a 500, not a
    silently shipped artifact."""
    spdx_doc = build_spdx(record)
    cdx_doc = build_cdx(record)
    spdx_errors = validate_spdx(spdx_doc)
    cdx_errors = validate_cdx(cdx_doc)
    if spdx_errors or cdx_errors:
        raise HTTPException(
            status_code=500,
            detail={"spdx_errors": spdx_errors, "cyclonedx_errors": cdx_errors},
        )
    return BomResponse(
        spdx=spdx_doc,
        cyclonedx=cdx_doc,
        spdx_validation_errors=[],
        cyclonedx_validation_errors=[],
        manual_input_required=manual_input_gaps(record),
    )


@v1.get("/crosswalk")
def crosswalk() -> dict:
    """The full crosswalk matrix with rationales - the knowledge base as API."""
    kb = knowledge.load()
    return {
        "knowledge_version": kb.version,
        "articles": [a.model_dump() for a in kb.articles],
    }


@v1.get("/timeline")
def timeline() -> dict:
    """Regulatory timeline (post-Digital-Omnibus) as data."""
    kb = knowledge.load()
    return {
        "knowledge_version": kb.version,
        "omnibus_status": kb.meta["frameworks"]["eu_ai_act"]["omnibus_status"].strip(),
        "regimes": {k: v.model_dump(mode="json") for k, v in kb.regimes.items()},
    }


app.include_router(v1)
