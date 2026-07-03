# AI Governance Auditor & AI-BOM Generator — Build Brief

You're acting as a senior AI-governance engineer helping me actually build this — not just describe it. It needs to hold up in a technical interview: if I say I designed and built it, I need to defend every design decision under follow-up questions. Prioritize correctness and defensibility over polish.

## What I'm building

**Part 1 — Automated AI-Governance Auditor.** Takes information about an AI system and produces a compliance assessment against:
- EU AI Act Articles 6 (high-risk classification), 9 (risk management system), 10 (data & data governance), 11 (technical documentation), 13 (transparency to deployers), 14 (human oversight), 15 (accuracy, robustness & cybersecurity)
- ISO/IEC 42001 (Annex A — 38 controls across 9 control objectives, A.2–A.10)
- NIST AI RMF (Govern / Map / Measure / Manage and their subcategories)
- OWASP Top 10 for LLM Applications (2025 edition, LLM01–LLM10), for systems that are LLM-based

Each article should cross-map to the relevant control(s) in the other three frameworks, so this produces one coherent crosswalk, not four separate checklists.

**Part 2 — AI Bill-of-Materials (AI-BOM) generator.** Takes metadata about a model/AI system and outputs a standards-conformant BOM in both SPDX 3.0's AI Profile and CycloneDX's ML-BOM (v1.6/1.7) — for AI supply-chain transparency: models, datasets, dependencies, provenance, licenses.

## Before writing any code: verify current state

These frameworks move fast, and some of this may be stale in your training data. Search and confirm before building the mapping logic:

- **EU AI Act timeline.** A "Digital Omnibus on AI" recently moved through political agreement and formal EU adoption that *defers* the high-risk obligations — standalone Annex III systems now apply from roughly December 2027, not August 2026, and Annex I embedded systems from around August 2028. Confirm exactly where this stands (published in the Official Journal yet?) and build the tool to track *when* each obligation actually takes effect, not just whether a system meets it today. Article 50's general transparency duties are on a separate, largely unaffected timeline — check the current status of the watermarking sub-obligation specifically.
- **ISO/IEC 42001** — confirm the current Annex A control list and clause structure (4–10) from ISO or a solid secondary source.
- **NIST AI RMF** — confirm current categories/subcategories under each function. NIST publishes its own AI RMF ↔ EU AI Act crosswalk on airc.nist.gov — use it as your starting anchor rather than inventing the mapping yourself. Check whether the in-progress AI RMF revision or the Generative AI Profile (AI 600-1) affects anything relevant here.
- **OWASP LLM Top 10** — confirm the current list (LLM01:2025 through LLM10:2025) at genai.owasp.org.
- **SPDX/CycloneDX** — confirm current spec versions, and look at what already exists (spdx-tools, cyclonedx-python, cdxgen's AI-BOM mode, the OWASP AIBOM Project) before deciding whether to build on an existing library or hand-roll serialization. A BOM that doesn't validate against the real schema isn't a real BOM.

## Part 1 requirements

- **Unified control taxonomy as structured data** (JSON/YAML, not hardcoded prose) — one internal model mapping each EU AI Act article to its ISO 42001 control(s), NIST subcategory(ies), and OWASP item(s) where relevant. This crosswalk is the core IP of the tool.
- **Article 6 classification first.** Before anything else, determine whether a system is even in scope — Annex I product-safety route, Annex III use-case list, or out of scope — since that gates everything downstream.
- **Evidence-based verdicts, not checkboxes.** For each in-scope article: a status (Compliant / Partial / Gap / Not Applicable) plus a short rationale citing the specific clause/control it was assessed against. No rationale, no defensibility.
- **Regulatory-timeline awareness.** Distinguish "doesn't meet the requirement" from "not legally required yet, but build it anyway" — given how much these deadlines have already moved, this is a genuinely useful, differentiated feature.
- **Output:** a structured report (Markdown/HTML/PDF, your call, but shareable) with per-article findings, overall classification, a prioritized gap list, and the crosswalk matrix exportable as CSV/JSON.
- **Input:** a structured questionnaire needs to work standalone. If partial auto-fill from uploaded docs (model cards, DPIAs, architecture docs) seems realistic without overclaiming, propose it as a stretch goal.

## Part 2 requirements

- **Input schema:** model/system name & version, architecture family, training/fine-tuning data sources & provenance, licenses (model + data + dependencies), key dependencies with versions, third-party pretrained/foundation components used, evaluation results & known limitations, intended use & restrictions.
- **Output:** SPDX 3.0 AI Profile *and* CycloneDX ML-BOM from the same underlying metadata — one system record, two export formats, not two independently maintained pipelines.
- **Actually validate** what you generate against the real schemas via an existing library/validator — don't just assert it's valid.
- **Be honest about automation limits.** Dependency versions and some license data can be pulled automatically. Training-data provenance and most governance narrative generally can't — flag those as manual-input-required instead of leaving them blank or inventing plausible values.

## How the two parts connect

The BOM's metadata (data provenance, dependency list, documented limitations) should feed directly into the Auditor's Article 10 and Article 11 assessments — one shared system record behind both tools, not two disconnected outputs. That's what makes this "AI-governance tooling" in the fullest sense, rather than two unrelated scripts.

## Process

1. **Don't write implementation code yet.** First give me a proposed architecture — tech stack, input/output formats, how the two parts share data — and ask whatever you need to confirm. My default lean: Python (a real SPDX/CycloneDX generator needs to be code either way), with a thin CLI or Streamlit front end rather than a full web app — but push back if you disagree. For reference, I previously built a related audit tool as a scored Excel workbook (33 controls across 8 layers, live formulas, conditional formatting) for a RAG-security consulting engagement — tell me if any of that pattern is worth carrying over, or if a clean code-first rebuild is the better call.
2. Once we've agreed the shape, start narrow: build the crosswalk data model plus full depth on two or three articles (say, 9 and 10) so we can validate the pattern before scaling to all seven.
3. Expand to the remaining articles, then build Part 2, then wire them together.
4. Give me a runnable end-to-end demo on one fictional example system (a resume-screening tool is a clean Annex III example) — output, not just source.
5. Include a README and a short "mapping rationale" doc explaining *why* each crosswalk link exists — that's what lets me defend this in an interview instead of reciting it.

## Definition of done

I should be able to walk a technical interviewer through the classification logic for a specific system, justify any single crosswalk entry on request, and produce a BOM they could open in a real SPDX/CycloneDX viewer — and have all of it hold up.
