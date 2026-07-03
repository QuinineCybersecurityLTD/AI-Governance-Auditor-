"""Render tests for the Streamlit front end via streamlit's AppTest harness -
executes the actual script, so widget/label errors fail here, not in a demo.
"""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

UI = str(Path(__file__).parent.parent / "aigov" / "ui.py")


@pytest.fixture()
def at():
    app = AppTest.from_file(UI, default_timeout=30)
    app.run()
    return app


def test_ui_renders_without_exception(at):
    assert not at.exception


def test_questionnaire_is_generated_from_knowledge_base(at):
    # every manual evidence key in the crosswalk must have a selectbox
    from aigov import knowledge
    kb = knowledge.load()
    manual_keys = {
        k for a in kb.articles for ob in a.obligations
        for k in ob.evidence_keys if not k.startswith("auto.")
    }
    select_keys = {s.key for s in at.selectbox if s.key and s.key.startswith("ans_")}
    assert {f"ans_{k}" for k in manual_keys} == select_keys


def test_audit_runs_from_ui_state(at):
    # fill the minimum: a name; then trigger the audit button
    name_input = next(t for t in at.text_input if t.label == "System name*")
    name_input.set_value("UI Smoke System").run()
    run_button = next(b for b in at.button if "Run audit" in b.label)
    run_button.click().run()
    assert not at.exception
    # minimal record with no Annex III tags -> minimal risk, no findings
    assert any("minimal_risk" in str(md.value) for md in at.subheader)
