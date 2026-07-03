"""Streamlit front end - the client-facing questionnaire over the same engine.

Run: streamlit run aigov/ui.py

Design rules:
- The questionnaire is GENERATED from the knowledge base: every non-auto
  evidence key in the crosswalk becomes a form item, grouped by article and
  showing the obligation text it evidences. Adding an article to the YAML
  adds it to the form - no UI changes.
- The UI never computes anything itself; it builds a SystemRecord and calls
  the same classify/audit/bom functions as the CLI and API.
- Nothing is persisted server-side; state lives in the browser session.
"""

from __future__ import annotations

import datetime as dt
import json

import streamlit as st
import yaml

from aigov import __version__, knowledge
from aigov.assess import audit as run_audit
from aigov.bom import build_cdx, build_spdx, manual_input_gaps, validate_cdx, validate_spdx
from aigov.classify import classify as run_classify
from aigov.record import SystemRecord
from aigov.report import render_markdown

st.set_page_config(page_title="AI Governance Auditor", page_icon="🛡️", layout="wide")

kb = knowledge.load()

ANSWER_OPTIONS = ["unanswered", "yes", "partial", "no", "not_applicable"]
STATUS_ICONS = {"Compliant": "✅", "Partial": "🟠", "Gap": "🔴", "Not Applicable": "⚪"}


def _default_record() -> dict:
    return SystemRecord(name="").model_dump(mode="json")


if "record" not in st.session_state:
    st.session_state.record = _default_record()


def _questionnaire_items() -> list[tuple[str, str, str, str]]:
    """(article, clause, obligation_text, evidence_key) for every manual key."""
    items = []
    for article in kb.articles:
        for ob in article.obligations:
            for key in ob.evidence_keys:
                if not key.startswith("auto."):
                    items.append((article.article, ob.clause, ob.text.strip(), key))
    return items


# ---------------------------------------------------------------- sidebar --
with st.sidebar:
    st.title("🛡️ AI Governance Auditor")
    st.caption(f"engine v{__version__} · knowledge base v{kb.version}")
    st.markdown(
        "EU AI Act (Arts 6, 9–15) ✕ ISO/IEC 42001 ✕ NIST AI RMF ✕ OWASP LLM "
        "Top 10 — plus SPDX 3.0.1 / CycloneDX 1.7 AI-BOMs."
    )
    st.divider()

    uploaded = st.file_uploader("Load a SystemRecord (YAML)", type=["yaml", "yml"])
    if uploaded is not None:
        try:
            record = SystemRecord.model_validate(yaml.safe_load(uploaded))
            st.session_state.record = record.model_dump(mode="json")
            st.success(f"Loaded: {record.name}")
        except Exception as e:
            st.error(f"Invalid record: {e}")

    if st.button("Load demo system (CandidateRank)"):
        from pathlib import Path
        demo = Path(__file__).parent.parent / "examples" / "resume_screener.yaml"
        st.session_state.record = SystemRecord.from_yaml(demo).model_dump(mode="json")
        st.rerun()

    st.divider()
    st.download_button(
        "⬇️ Download current record (YAML)",
        data=yaml.safe_dump(st.session_state.record, sort_keys=False, allow_unicode=True),
        file_name="system_record.yaml",
        mime="application/yaml",
    )
    with st.expander("Regulatory timeline status"):
        st.write(kb.meta["frameworks"]["eu_ai_act"]["omnibus_status"])

rec = st.session_state.record

tab_system, tab_evidence, tab_audit, tab_bom, tab_xw = st.tabs(
    ["1 · System record", "2 · Questionnaire", "3 · Audit", "4 · AI-BOM", "Crosswalk"]
)

# ------------------------------------------------------------ system tab --
with tab_system:
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Identity")
        rec["name"] = st.text_input("System name*", rec.get("name", ""))
        rec["version"] = st.text_input("Version", rec.get("version", "0.1"))
        rec["provider"] = st.text_input("Provider organisation", rec.get("provider", ""))
        rec["description"] = st.text_area("Description", rec.get("description", ""), height=80)
        rec["intended_purpose"] = st.text_area("Intended purpose", rec.get("intended_purpose", ""), height=80)
        rec["intended_users"] = st.text_input("Intended users", rec.get("intended_users", ""))
        rec["use_restrictions"] = st.text_input("Use restrictions", rec.get("use_restrictions", ""))
        rec["is_llm_based"] = st.checkbox("LLM-based system", rec.get("is_llm_based", False),
                                          help="Enables the OWASP LLM Top 10 side of the crosswalk.")
    with c2:
        st.subheader("Article 6 classification inputs")
        ci = rec.setdefault("classification", {})
        all_tags = sorted({t for c in kb.annex_iii_categories for t in c.tags})
        ci["use_case_tags"] = st.multiselect(
            "Use-case tags (Annex III matching)", all_tags, ci.get("use_case_tags", []))
        ci["performs_profiling"] = st.checkbox(
            "Performs profiling of natural persons", ci.get("performs_profiling", False),
            help="Profiling defeats every Art 6(3) derogation.")
        ci["interacts_with_natural_persons"] = st.checkbox(
            "Interacts with natural persons (chatbot etc.)",
            ci.get("interacts_with_natural_persons", False))
        ci["generates_synthetic_content"] = st.checkbox(
            "Generates synthetic content", ci.get("generates_synthetic_content", False))
        ci["annex_i_product_area"] = st.text_input(
            "Annex I product area (blank if none)", ci.get("annex_i_product_area") or "") or None
        if ci["annex_i_product_area"]:
            ci["is_safety_component"] = st.checkbox(
                "Is a safety component", ci.get("is_safety_component", False))
            ci["failure_endangers_health_or_safety"] = st.checkbox(
                "Failure could endanger health or safety (post-Omnibus test)",
                ci.get("failure_endangers_health_or_safety", False))
        dero_ids = [d.id for d in kb.derogations]
        claimed = st.multiselect(
            "Art 6(3) derogation claims", dero_ids,
            [k for k in (ci.get("derogation_claims") or {}) if k in dero_ids])
        claims = {}
        for d in claimed:
            label = next(x.label for x in kb.derogations if x.id == d)
            claims[d] = st.text_input(
                f"Justification for {d} ({label})",
                (ci.get("derogation_claims") or {}).get(d, ""))
        ci["derogation_claims"] = claims

    st.subheader("Composition (feeds both the audit and the AI-BOM)")
    st.caption("These tables are Article 10/11 evidence AND BOM content — one record, two consumers.")
    for field, cols in (
        ("models", ["name", "version", "architecture_family", "provider", "license",
                    "is_foundation_model", "source_url"]),
        ("datasets", ["name", "role", "source", "provenance", "license",
                      "contains_personal_data", "preparation", "known_gaps", "bias_assessment"]),
        ("dependencies", ["name", "version", "license", "purpose"]),
        ("evaluations", ["name", "value", "dataset", "notes"]),
    ):
        st.markdown(f"**{field.capitalize()}**")
        rows = rec.get(field) or []
        edited = st.data_editor(
            rows if rows else [{c: None for c in cols}],
            num_rows="dynamic", use_container_width=True, key=f"editor_{field}",
        )
        rec[field] = [r for r in edited if r.get("name")]

    limitations_text = st.text_area(
        "Known limitations (one per line)",
        "\n".join(rec.get("known_limitations") or []))
    rec["known_limitations"] = [l.strip() for l in limitations_text.splitlines() if l.strip()]

# --------------------------------------------------------- evidence tab --
with tab_evidence:
    st.subheader("Compliance questionnaire")
    st.caption(
        "Generated from the crosswalk knowledge base — every question cites the "
        "obligation it evidences. Your notes are quoted verbatim in the report "
        "rationale: no note, weaker defensibility."
    )
    evidence = rec.setdefault("evidence", {})
    current_article = None
    for article, clause, text, key in _questionnaire_items():
        if article != current_article:
            current_article = article
            title = next(a.title for a in kb.articles if a.article == article)
            st.markdown(f"### Article {article} — {title}")
        with st.container(border=True):
            st.markdown(f"**{clause}** — {text}")
            existing = evidence.get(key) or {}
            c1, c2 = st.columns([1, 3])
            with c1:
                answer = st.selectbox(
                    "Status", ANSWER_OPTIONS,
                    ANSWER_OPTIONS.index(existing.get("answer", "unanswered"))
                    if existing.get("answer") in ANSWER_OPTIONS else 0,
                    key=f"ans_{key}", label_visibility="collapsed")
            with c2:
                note = st.text_input(
                    "Evidence note", existing.get("note", ""),
                    key=f"note_{key}", label_visibility="collapsed",
                    placeholder="Evidence note (quoted in the report rationale)")
            if answer != "unanswered":
                evidence[key] = {"answer": answer, "note": note}
            else:
                evidence.pop(key, None)

# ------------------------------------------------------------- audit tab --
with tab_audit:
    col_a, col_b = st.columns([1, 3])
    with col_a:
        assessment_date = st.date_input("Assessment date", dt.date.today())
        run = st.button("▶ Run audit", type="primary", disabled=not rec.get("name"))
    if not rec.get("name"):
        st.info("Give the system a name on tab 1 first.")
    if run:
        record = SystemRecord.model_validate(rec)
        classification = run_classify(record, kb)
        result = run_audit(record, kb, classification, assessment_date)
        st.session_state.audit_result = result
    if "audit_result" in st.session_state:
        result = st.session_state.audit_result
        st.subheader(f"Classification: `{result.classification.tier.value}`")
        with st.expander("Article 6 reasoning", expanded=True):
            for i, line in enumerate(result.classification.reasoning, 1):
                st.markdown(f"{i}. {line}")
        if result.findings:
            counts = {}
            for f in result.findings:
                counts[f.status.value] = counts.get(f.status.value, 0) + 1
            cols = st.columns(4)
            for col, status in zip(cols, ["Compliant", "Partial", "Gap", "Not Applicable"]):
                col.metric(f"{STATUS_ICONS[status]} {status}", counts.get(status, 0))
            st.info(result.timeline_note)
            st.dataframe(
                [{
                    "Clause": f.clause,
                    "Status": f"{STATUS_ICONS[f.status.value]} {f.status.value}",
                    "Applies from": f.applies_from.isoformat(),
                    "Severity": f.severity,
                    "Priority": f.priority_score,
                    "Rationale": f.rationale,
                } for f in sorted(result.findings, key=lambda x: -x.priority_score)],
                use_container_width=True, height=420)
            md = render_markdown(result)
            d1, d2 = st.columns(2)
            d1.download_button("⬇️ Report (Markdown)", md, "audit_report.md")
            d2.download_button(
                "⬇️ Findings (JSON)",
                result.model_dump_json(indent=2), "audit_findings.json")
        else:
            st.success("No high-risk obligations apply to this classification.")

# --------------------------------------------------------------- BOM tab --
with tab_bom:
    st.caption(
        "Both formats are generated from the record above and validated against "
        "the real schemas on every run. Missing provenance/licensing is flagged, "
        "never invented."
    )
    if st.button("⚙ Generate AI-BOMs", type="primary", disabled=not rec.get("name")):
        record = SystemRecord.model_validate(rec)
        spdx_doc = build_spdx(record)
        cdx_doc = build_cdx(record)
        st.session_state.bom = {
            "spdx": spdx_doc, "cdx": cdx_doc,
            "spdx_errors": validate_spdx(spdx_doc),
            "cdx_errors": validate_cdx(cdx_doc),
            "gaps": manual_input_gaps(record),
        }
    if "bom" in st.session_state:
        b = st.session_state.bom
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**SPDX 3.0.1 AI Profile** — "
                        + ("✅ schema + round-trip PASS" if not b["spdx_errors"] else "🔴 FAIL"))
            for e in b["spdx_errors"]:
                st.error(e)
            st.download_button("⬇️ bom.spdx3.json",
                               json.dumps(b["spdx"], indent=2), "bom.spdx3.json")
        with c2:
            st.markdown("**CycloneDX 1.7 ML-BOM** — "
                        + ("✅ strict schema PASS" if not b["cdx_errors"] else "🔴 FAIL"))
            for e in b["cdx_errors"]:
                st.error(e)
            st.download_button("⬇️ bom.cdx.json",
                               json.dumps(b["cdx"], indent=2), "bom.cdx.json")
        if b["gaps"]:
            st.warning(f"{len(b['gaps'])} manual-input-required item(s):")
            for g in b["gaps"]:
                st.markdown(f"- **{g.component}** `{g.field}` — {g.hint}")
        else:
            st.success("No manual-input-required items.")

# --------------------------------------------------------- crosswalk tab --
with tab_xw:
    st.caption(f"The full mapping with rationales — knowledge base v{kb.version}.")
    for article in kb.articles:
        with st.expander(f"Article {article.article} — {article.title}"):
            for ob in article.obligations:
                st.markdown(f"**{ob.clause}** ({ob.severity}) — {ob.text.strip()}")
                for fw, maps in ob.mappings.items():
                    for m in maps:
                        cond = f" *({m.when})*" if m.when else ""
                        st.markdown(f"- `{fw}` → **{m.ref}**{cond}: {' '.join(m.rationale.split())}")
                st.divider()
