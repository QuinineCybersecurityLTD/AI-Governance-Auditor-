"""The shared SystemRecord: one description of an AI system that feeds both
the governance auditor (Part 1) and the AI-BOM generator (Part 2).

Design rule: every field that the BOM exports (datasets, dependencies,
licenses, limitations) is also evidence the auditor reads for Articles 10/11.
One record, two consumers.
"""

from __future__ import annotations

import datetime as dt
from enum import Enum
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field


class Answer(str, Enum):
    """Questionnaire answer for a single evidence item."""

    YES = "yes"          # practice exists and is documented
    PARTIAL = "partial"  # exists but incomplete / undocumented
    NO = "no"            # absent
    NA = "not_applicable"


class EvidenceItem(BaseModel):
    """One answered questionnaire item. The note is what makes a verdict
    defensible - it is quoted verbatim in the report rationale."""

    answer: Answer
    note: str = ""


class DatasetRef(BaseModel):
    """A training/validation/testing dataset. Provenance fields are exported
    to the BOM and simultaneously assessed under Article 10(2)(b)."""

    name: str
    role: str = "training"  # training | validation | testing | fine-tuning | rag-corpus
    source: Optional[str] = None            # where it came from (URL, vendor, internal)
    provenance: Optional[str] = None        # how it was collected, original purpose
    license: Optional[str] = None
    contains_personal_data: Optional[bool] = None
    preparation: Optional[str] = None       # labelling, cleaning, enrichment applied
    known_gaps: Optional[str] = None        # documented shortcomings
    bias_assessment: Optional[str] = None   # what bias examination was done


class ModelRef(BaseModel):
    """A model component (own-trained or third-party foundation model)."""

    name: str
    version: Optional[str] = None
    architecture_family: Optional[str] = None   # e.g. transformer-decoder, GBM
    provider: Optional[str] = None              # None => trained in-house
    license: Optional[str] = None
    is_foundation_model: bool = False
    source_url: Optional[str] = None


class DependencyRef(BaseModel):
    name: str
    version: Optional[str] = None
    license: Optional[str] = None
    purpose: Optional[str] = None


class EvaluationResult(BaseModel):
    name: str                       # e.g. "accuracy", "demographic parity gap"
    value: str                      # kept as string: "0.87", "3.2pp", "pass"
    dataset: Optional[str] = None
    notes: Optional[str] = None


class ClassificationInput(BaseModel):
    """Facts the Article 6 classifier consumes. Tags must match the
    use-case taxonomy in knowledge/data/classification.yaml."""

    use_case_tags: list[str] = Field(default_factory=list)
    annex_i_product_area: Optional[str] = None   # e.g. "machinery", "medical-devices"
    is_safety_component: bool = False
    # Post-Omnibus Art 6 narrowing: a "safety component" only makes a system
    # high-risk if its failure could endanger health or safety.
    failure_endangers_health_or_safety: bool = False
    performs_profiling: bool = False
    # Art 6(3) derogation claims - each must match a derogation id in the
    # knowledge base and is only accepted with a justification.
    derogation_claims: dict[str, str] = Field(default_factory=dict)
    placed_on_market_date: Optional[dt.date] = None
    generates_synthetic_content: bool = False
    interacts_with_natural_persons: bool = False


class SystemRecord(BaseModel):
    """The single shared record behind both tools."""

    # -- identity ---------------------------------------------------------
    name: str
    version: str = "0.1"
    description: str = ""
    provider: str = ""
    intended_purpose: str = ""
    intended_users: str = ""
    use_restrictions: str = ""
    is_llm_based: bool = False
    deployment_context: str = ""

    # -- Article 6 inputs --------------------------------------------------
    classification: ClassificationInput = Field(default_factory=ClassificationInput)

    # -- BOM-facing composition (also Article 10/11 evidence) --------------
    models: list[ModelRef] = Field(default_factory=list)
    datasets: list[DatasetRef] = Field(default_factory=list)
    dependencies: list[DependencyRef] = Field(default_factory=list)
    evaluations: list[EvaluationResult] = Field(default_factory=list)
    known_limitations: list[str] = Field(default_factory=list)

    # -- questionnaire evidence, keyed by evidence_key from the crosswalk --
    evidence: dict[str, EvidenceItem] = Field(default_factory=dict)

    @classmethod
    def from_yaml(cls, path: str | Path) -> "SystemRecord":
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return cls.model_validate(data)
