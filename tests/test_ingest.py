from pathlib import Path

import pytest

from aigov.bom import manual_input_gaps
from aigov.ingest import AUTOFILL_MARK, parse_frontmatter, record_from_model_card

CARD = Path(__file__).parent.parent / "examples" / "model_card_mistral.md"


@pytest.fixture(scope="module")
def record():
    return record_from_model_card(CARD)


def test_models_extracted_with_base_model_as_foundation(record):
    names = {m.name: m for m in record.models}
    assert names["cv-parser-ft"].license == "apache-2.0"
    base = names["mistralai/Mistral-7B-v0.3"]
    assert base.is_foundation_model is True
    assert base.provider == "mistralai"
    assert base.source_url.endswith("Mistral-7B-v0.3")


def test_datasets_named_but_provenance_left_manual(record):
    assert record.datasets[0].name == "internal/cv-parsing-corpus"
    assert record.datasets[0].provenance is None
    gaps = manual_input_gaps(record)
    assert any(g.field == "provenance" for g in gaps)


def test_evaluations_from_model_index(record):
    by_name = {e.name: e for e in record.evaluations}
    assert by_name["field-extraction-f1"].value == "0.91"
    assert by_name["exact-match"].dataset == "internal/cv-eval-set"
    assert all(AUTOFILL_MARK in (e.notes or "") for e in record.evaluations)


def test_llm_detected_from_pipeline_tag(record):
    assert record.is_llm_based is True


def test_autofill_is_marked_not_disguised(record):
    assert AUTOFILL_MARK in record.description


def test_no_frontmatter_raises(tmp_path):
    p = tmp_path / "plain.md"
    p.write_text("# just a readme", encoding="utf-8")
    with pytest.raises(ValueError, match="frontmatter"):
        parse_frontmatter(p.read_text(encoding="utf-8"))
