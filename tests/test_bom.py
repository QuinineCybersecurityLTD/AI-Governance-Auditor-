import datetime as dt
from pathlib import Path

import pytest

from aigov.bom import build_cdx, build_spdx, manual_input_gaps, validate_cdx, validate_spdx
from aigov.record import SystemRecord

EXAMPLE = Path(__file__).parent.parent / "examples" / "resume_screener.yaml"
FIXED = dt.datetime(2026, 7, 3, tzinfo=dt.timezone.utc)


@pytest.fixture(scope="module")
def record():
    return SystemRecord.from_yaml(EXAMPLE)


@pytest.fixture(scope="module")
def spdx_doc(record):
    return build_spdx(record, created=FIXED)


@pytest.fixture(scope="module")
def cdx_doc(record):
    return build_cdx(record, timestamp=FIXED)


def test_spdx_validates_against_official_schema_and_roundtrip(spdx_doc):
    assert validate_spdx(spdx_doc) == []


def test_cdx_validates_against_official_17_schema(cdx_doc):
    assert validate_cdx(cdx_doc) == []


def test_spdx_contains_ai_and_dataset_profile_elements(spdx_doc):
    types = [el.get("type") for el in spdx_doc["@graph"]]
    assert types.count("ai_AIPackage") == 3  # system + 2 model components
    assert types.count("dataset_DatasetPackage") == 2
    assert spdx_doc["@context"] == "https://spdx.org/rdf/3.0.1/spdx-context.jsonld"


def test_spdx_flags_missing_provenance_not_invents(spdx_doc):
    ds = [el for el in spdx_doc["@graph"] if el.get("type") == "dataset_DatasetPackage"]
    corpus = next(el for el in ds if el["name"] == "cv-parsing-corpus")
    assert "MANUAL INPUT REQUIRED" in corpus.get("comment", "")
    assert "dataset_dataCollectionProcess" not in corpus


def test_spdx_training_relationships(spdx_doc):
    rels = [el for el in spdx_doc["@graph"] if el.get("type") == "Relationship"]
    rel_types = {r["relationshipType"] for r in rels}
    assert {"trainedOn", "contains", "dependsOn", "hasDeclaredLicense"} <= rel_types


def test_cdx_model_card_present_with_metrics(cdx_doc):
    ranker = next(c for c in cdx_doc["components"] if c["name"] == "cr-ranker")
    metrics = ranker["modelCard"]["quantitativeAnalysis"]["performanceMetrics"]
    assert any(m["type"] == "shortlist precision@10" for m in metrics)
    # own-trained model links to the declared datasets
    refs = {d["ref"] for d in ranker["modelCard"]["modelParameters"]["datasets"]}
    assert "dataset:historic-hiring-outcomes" in refs


def test_cdx_foundation_model_does_not_claim_our_datasets(cdx_doc):
    mistral = next(c for c in cdx_doc["components"] if "Mistral" in c["name"])
    assert "datasets" not in mistral.get("modelCard", {}).get("modelParameters", {})
    props = {p["name"]: p["value"] for p in mistral["properties"]}
    assert props["aigov:foundation_model"] == "true"


def test_cdx_personal_data_classification(cdx_doc):
    hho = next(c for c in cdx_doc["components"] if c["name"] == "historic-hiring-outcomes")
    assert hho["data"][0]["classification"] == "personal-data"


def test_cdx_reproducible_serial_number(record):
    a = build_cdx(record, timestamp=FIXED)
    b = build_cdx(record, timestamp=FIXED)
    assert a["serialNumber"] == b["serialNumber"]


def test_gaps_flag_missing_provenance_and_license(record):
    gaps = manual_input_gaps(record)
    keyed = {(g.component, g.field) for g in gaps}
    assert ("dataset:cv-parsing-corpus", "provenance") in keyed
    assert ("dataset:cv-parsing-corpus", "license") in keyed
    # complete components produce no gap entries
    assert not any(g.component == "dataset:historic-hiring-outcomes" for g in gaps)
