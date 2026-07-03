# Mapping rationale — how the crosswalk was built and why it holds up

This document explains the *method* behind the crosswalk in
`aigov/knowledge/data/crosswalk/`. The per-link rationales live next to the
links themselves in the YAML (a test fails if any link lacks one); this file
covers the questions an interviewer would ask about the mapping as a whole.

## 1. What is anchored on published sources vs. our own derivation

**Be precise about this — it is the most likely challenge question.**

- **NIST's own EU AI Act crosswalk** (airc.nist.gov, Jan 2023) maps only the
  seven **trustworthiness characteristics** to the *proposed* Act (e.g.
  "Valid and Reliable" ↔ robustness/accuracy, "Safe" ↔ safety). It contains
  **no article→subcategory mapping**. We use it as a sanity anchor at
  characteristic level; every article→subcategory link in this repo is **our
  derivation from the subcategory text of AI 100-1**, and each one carries a
  written rationale so it can be challenged individually.
- **ISO/IEC 42001 Annex A** links are derived from the control statements
  (38 controls, objectives A.2–A.10). Where an Act obligation spans both a
  management-clause requirement and an Annex A control (Art 9's continuous
  RMS), we cite both (`Clause 6.1 / 8` + `A.5.2`).
- **OWASP LLM Top 10 (2025)** links are conditional (`when: llm_based`):
  OWASP is a threat catalogue, not a legal framework, so its items map to
  obligations as *state-of-the-art evidence* (what a credible risk analysis
  or data-governance process must have considered for an LLM system), never
  as legal equivalence.

## 2. Mapping principles

1. **Direction:** EU AI Act obligation → other frameworks. The Act is the
   binding instrument; ISO/NIST/OWASP tell you *how to satisfy or evidence*
   it. We never claim the reverse (ISO certification ≠ Act compliance).
2. **Granularity:** we map at the *assessable obligation* level (e.g. Art
   10(2)(b), not "Article 10"), because verdicts and rationales only make
   sense at the level where evidence exists.
3. **No rationale, no link.** Enforced by
   `tests/test_assess.py::test_knowledge_base_loads_and_validates`.
4. **Conditional links are explicit.** OWASP links carry `when: llm_based`;
   obligations with applicability conditions (Art 10(5) requires personal
   data) declare them in `applicability`.
5. **One-to-many is expected; many-to-nothing is honest.** Some obligations
   have no OWASP counterpart (Art 9(9) vulnerable groups). We leave those
   empty rather than force a link.

## 3. Worked example: Art 10(2)(b) — the densest node in the graph

Data collection/origin documentation maps to:

- **ISO A.7.3 + A.7.5** — acquisition and provenance are two separate ISO
  controls covering the two halves of the clause ("collection processes" /
  "origin of data").
- **NIST MAP 2.3** — the subcategory that names data collection and
  selection documentation.
- **OWASP LLM03 + LLM04** (LLM systems) — undocumented dataset origin is
  simultaneously a supply-chain exposure and the enabling condition for
  data poisoning.
- **The AI-BOM** — `DatasetRef.provenance` is exported into the BOM and
  auto-assessed here (`auto.dataset_provenance`). One missing field produces
  a legal finding, a security finding, and an incomplete BOM entry — the
  concrete demonstration that Part 1 and Part 2 share one record.
- **Art 11 (Annex IV 2(d)) deliberately reuses this same evidence**: the
  datasheet the technical file must contain is compiled from the provenance
  record, so a missing provenance field also yields a documentation finding.
  Cross-article evidence reuse is intentional and documented per obligation
  (`note:` fields in the YAML), not double counting: the *facts* are shared,
  the *legal duties* are distinct.

## 3a. Second worked example: Art 15(5) — where OWASP earns its place

Art 15(5) names data poisoning, model poisoning, adversarial examples/model
evasion and confidentiality attacks *verbatim*. For LLM systems these
instantiate as LLM04 (poisoning), LLM01 (prompt injection = model evasion at
the input layer), LLM02 (confidentiality/extraction), and LLM10 (resource
exhaustion altering performance). This is the strongest article-level
justification for including a threat catalogue alongside three governance
frameworks: the Act's own text describes OWASP's attack classes.

## 4. Timeline as part of the mapping

Each article declares a `regime` (e.g. `high_risk_annex_iii`) rather than a
date. Regimes live in `timeline.yaml` with post-Digital-Omnibus dates, the
original dates, and a source note. Verdicts distinguish "gap now" from
"upcoming gap (from 2027-12-02)" — the deferral is treated as runway, not
exemption, and the report says so.

## 5. Known limitations (say these before the interviewer does)

- NIST subcategory links are defensible readings, not official positions —
  the official crosswalk isn't granular enough to settle them.
- ISO 42001 Annex A control titles are paraphrased from secondary sources;
  a certification-grade deployment should verify wording against the
  purchased standard.
- The Art 6 classifier consumes *declared* facts (tags, profiling flag).
  It cannot detect a mis-declared system; that is inherent to any
  self-assessment tool and is why derogation claims require justifications
  and are echoed into the report.
- Evidence quality is asserted by the respondent. The tool makes verdicts
  *traceable*, not *audited* — it is a governance instrument, not a
  conformity assessment body.
