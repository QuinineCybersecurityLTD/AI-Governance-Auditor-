"""SystemRecord -> CycloneDX 1.7 ML-BOM (JSON).

cyclonedx-python-lib (11.x) emits 1.7 documents but has no modelCard model
classes, so the document is constructed as a plain dict against the 1.7
schema and validated with the library's bundled official schema validator
(validate.py). The serial number is a UUIDv5 of name+version, so repeated
runs on the same record are reproducible.
"""

from __future__ import annotations

import datetime as dt
import uuid

from aigov import __version__
from aigov.record import DatasetRef, ModelRef, SystemRecord

_NS = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")  # RFC 4122 DNS ns


def _licenses(text: str | None) -> list | None:
    # "name" (not "id") keeps non-SPDX strings like "proprietary" schema-valid.
    return [{"license": {"name": text}}] if text else None


def _dataset_bom_ref(d: DatasetRef) -> str:
    return f"dataset:{d.name}"


def _dataset_component(d: DatasetRef) -> dict:
    classification = (
        "personal-data" if d.contains_personal_data
        else "public" if d.contains_personal_data is False
        else "unclassified"
    )
    data_entry: dict = {
        "type": "dataset",
        "name": d.name,
        "classification": classification,
    }
    if d.provenance:
        data_entry["description"] = d.provenance
    comp: dict = {
        "type": "data",
        "bom-ref": _dataset_bom_ref(d),
        "name": d.name,
        "data": [data_entry],
        "properties": [{"name": "aigov:role", "value": d.role}],
    }
    if d.source:
        comp["description"] = f"Source: {d.source}"
    if lic := _licenses(d.license):
        comp["licenses"] = lic
    for field, label in (("provenance", "provenance"),
                         ("license", "license"),
                         ("bias_assessment", "bias_assessment"),
                         ("known_gaps", "known_gaps")):
        if not getattr(d, field):
            comp["properties"].append(
                {"name": "aigov:manual_input_required", "value": label})
    if d.known_gaps:
        comp["properties"].append({"name": "aigov:known_gaps", "value": d.known_gaps})
    if d.bias_assessment:
        comp["properties"].append({"name": "aigov:bias_assessment", "value": d.bias_assessment})
    return comp


def _model_component(m: ModelRef, record: SystemRecord) -> dict:
    model_params: dict = {}
    if m.architecture_family:
        model_params["architectureFamily"] = m.architecture_family
    dataset_refs = [{"ref": _dataset_bom_ref(d)} for d in record.datasets]
    if dataset_refs and not m.is_foundation_model:
        # only own-trained components are linked to the declared datasets;
        # a third-party foundation model's training data is NOT ours to claim
        model_params["datasets"] = dataset_refs

    considerations: dict = {}
    if not m.is_foundation_model:
        if record.known_limitations:
            considerations["technicalLimitations"] = list(record.known_limitations)
        if record.intended_users:
            considerations["users"] = [record.intended_users]
        if record.intended_purpose:
            considerations["useCases"] = [record.intended_purpose]
        bias_notes = [d.bias_assessment for d in record.datasets if d.bias_assessment]
        if bias_notes:
            considerations["ethicalConsiderations"] = [
                {"name": "dataset bias", "mitigationStrategy": note} for note in bias_notes
            ]

    model_card: dict = {}
    if model_params:
        model_card["modelParameters"] = model_params
    if considerations:
        model_card["considerations"] = considerations
    if not m.is_foundation_model and record.evaluations:
        model_card["quantitativeAnalysis"] = {
            "performanceMetrics": [
                {"type": ev.name, "value": ev.value} for ev in record.evaluations
            ]
        }

    comp: dict = {
        "type": "machine-learning-model",
        "bom-ref": f"model:{m.name}",
        "name": m.name,
    }
    if m.version:
        comp["version"] = m.version
    if m.provider:
        comp["supplier"] = {"name": m.provider}
    if m.source_url:
        comp["externalReferences"] = [{"type": "distribution", "url": m.source_url}]
    if lic := _licenses(m.license):
        comp["licenses"] = lic
    if model_card:
        comp["modelCard"] = model_card
    props = []
    if m.is_foundation_model:
        props.append({"name": "aigov:foundation_model", "value": "true"})
        props.append({"name": "aigov:manual_input_required",
                      "value": "training-data provenance (third-party model)"})
    if props:
        comp["properties"] = props
    return comp


def build_cdx(record: SystemRecord, timestamp: dt.datetime | None = None) -> dict:
    timestamp = timestamp or dt.datetime.now(dt.timezone.utc)
    serial = uuid.uuid5(_NS, f"aigov:{record.name}:{record.version}")

    components: list[dict] = []
    components += [_model_component(m, record) for m in record.models]
    components += [_dataset_component(d) for d in record.datasets]
    components += [
        {
            "type": "library",
            "bom-ref": f"dependency:{d.name}",
            "name": d.name,
            **({"version": d.version} if d.version else {}),
            **({"licenses": _licenses(d.license)} if d.license else {}),
            **({"description": d.purpose} if d.purpose else {}),
        }
        for d in record.dependencies
    ]

    root_ref = f"system:{record.name}"
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.7",
        "serialNumber": f"urn:uuid:{serial}",
        "version": 1,
        "metadata": {
            "timestamp": timestamp.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "tools": {"components": [
                {"type": "application", "name": "aigov", "version": __version__}
            ]},
            "component": {
                "type": "application",
                "bom-ref": root_ref,
                "name": record.name,
                "version": record.version,
                **({"description": record.description} if record.description else {}),
                **({"supplier": {"name": record.provider}} if record.provider else {}),
            },
        },
        "components": components,
        "dependencies": [
            {
                "ref": root_ref,
                "dependsOn": [c["bom-ref"] for c in components],
            }
        ],
    }
