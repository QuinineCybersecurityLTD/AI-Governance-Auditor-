"""Model-card ingestion (the stretch goal, scoped honestly).

Parses the YAML frontmatter of a HuggingFace-style model card into a PARTIAL
SystemRecord. What a model card can reliably give you: model name, license,
base model, dataset identifiers, evaluation results (model-index). What it
cannot: training-data provenance narratives, governance answers, Article 6
facts. Those are left empty and therefore surface as manual-input-required
gaps and audit findings - auto-fill never fakes completeness.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from aigov.record import DatasetRef, EvaluationResult, ModelRef, SystemRecord

_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)

AUTOFILL_MARK = "[auto-filled from model card - verify]"


def parse_frontmatter(text: str) -> dict:
    m = _FRONTMATTER_RE.match(text)
    if not m:
        raise ValueError("No YAML frontmatter found (expected a '---' block at the top).")
    data = yaml.safe_load(m.group(1))
    if not isinstance(data, dict):
        raise ValueError("Frontmatter is not a YAML mapping.")
    return data


def _evaluations_from_model_index(fm: dict) -> list[EvaluationResult]:
    evals: list[EvaluationResult] = []
    for entry in fm.get("model-index") or []:
        for result in entry.get("results") or []:
            ds = (result.get("dataset") or {}).get("name")
            for metric in result.get("metrics") or []:
                if metric.get("type") is None or metric.get("value") is None:
                    continue
                evals.append(EvaluationResult(
                    name=str(metric["type"]),
                    value=str(metric["value"]),
                    dataset=ds,
                    notes=AUTOFILL_MARK,
                ))
    return evals


def record_from_model_card(path: str | Path, system_name: str | None = None) -> SystemRecord:
    text = Path(path).read_text(encoding="utf-8")
    fm = parse_frontmatter(text)

    model_name = (
        (fm.get("model-index") or [{}])[0].get("name")
        or fm.get("model_name")
        or Path(path).stem
    )
    license_ = fm.get("license")
    base_model = fm.get("base_model")
    if isinstance(base_model, list):
        base_model = base_model[0] if base_model else None

    models = [ModelRef(
        name=str(model_name),
        license=str(license_) if license_ else None,
        is_foundation_model=False,
    )]
    if base_model:
        models.append(ModelRef(
            name=str(base_model),
            is_foundation_model=True,
            provider=str(base_model).split("/")[0] if "/" in str(base_model) else None,
            source_url=f"https://huggingface.co/{base_model}",
        ))

    datasets = [
        DatasetRef(
            name=str(ds),
            role="training",
            source=f"declared in model card: {ds}",
            # provenance deliberately None -> manual-input-required gap
        )
        for ds in (fm.get("datasets") or [])
    ]

    return SystemRecord(
        name=system_name or str(model_name),
        description=f"{AUTOFILL_MARK} Ingested from {Path(path).name}. "
                    "Classification inputs, questionnaire evidence and data "
                    "provenance require human completion.",
        is_llm_based=any(
            t in {"text-generation", "conversational", "text2text-generation"}
            for t in (fm.get("pipeline_tag"), *(fm.get("tags") or []))
            if t
        ),
        models=models,
        datasets=datasets,
        evaluations=_evaluations_from_model_index(fm),
    )
