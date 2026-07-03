"""Typed loader for the knowledge base (crosswalk, timeline, classification).

The YAML files are the IP; this module only validates and exposes them.
Schema violations in the data fail loudly at load time, not at report time.
"""

from __future__ import annotations

import datetime as dt
from functools import lru_cache
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field

DATA_DIR = Path(__file__).parent / "data"


class Mapping(BaseModel):
    ref: str
    rationale: str
    when: Optional[str] = None  # e.g. "llm_based" - conditional applicability


class Applicability(BaseModel):
    requires_any: list[str] = Field(default_factory=list)


class Obligation(BaseModel):
    id: str
    clause: str
    severity: str  # high | medium | low
    text: str
    evidence_keys: list[str]
    applicability: Optional[Applicability] = None
    mappings: dict[str, list[Mapping]] = Field(default_factory=dict)
    note: Optional[str] = None  # crosswalk-design commentary, not shown in findings


class ArticleCrosswalk(BaseModel):
    article: str
    title: str
    regime: str
    summary: str
    obligations: list[Obligation]


class Regime(BaseModel):
    label: str
    applies_from: dt.date
    original_date: dt.date
    source: str
    condition: Optional[str] = None


class AnnexIIICategory(BaseModel):
    id: str
    label: str
    tags: list[str]


class Derogation(BaseModel):
    id: str
    label: str


class KnowledgeBase(BaseModel):
    meta: dict
    regimes: dict[str, Regime]
    annex_iii_categories: list[AnnexIIICategory]
    derogations: list[Derogation]
    articles: list[ArticleCrosswalk]

    @property
    def version(self) -> str:
        return self.meta["knowledge_version"]


def _load_yaml(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


@lru_cache(maxsize=1)
def load() -> KnowledgeBase:
    meta = _load_yaml(DATA_DIR / "meta.yaml")
    timeline = _load_yaml(DATA_DIR / "timeline.yaml")
    classification = _load_yaml(DATA_DIR / "classification.yaml")
    articles = [
        ArticleCrosswalk.model_validate(_load_yaml(p))
        for p in sorted((DATA_DIR / "crosswalk").glob("article_*.yaml"))
    ]
    return KnowledgeBase(
        meta=meta,
        regimes=timeline["regimes"],
        annex_iii_categories=classification["annex_iii_categories"],
        derogations=classification["art6_3_derogations"],
        articles=articles,
    )
