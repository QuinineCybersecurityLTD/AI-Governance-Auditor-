# aigov — AI Governance Auditor & AI-BOM Generator

Audits an AI system against **EU AI Act Arts 6, 9–15**, **ISO/IEC 42001 Annex A**,
**NIST AI RMF 1.0**, and **OWASP LLM Top 10 (2025)** through one unified
crosswalk — and (Part 2, in progress) exports the same system record as an
**SPDX 3.0 AI Profile** and **CycloneDX 1.7 ML-BOM**.

## Status

**Both parts functional.** Part 1: Article 6 classification + full depth on
Articles 9, 10, 11, 13, 14, 15 (32 assessable obligations, 99 crosswalk
links). Part 2: SPDX 3.0.1 AI Profile (JSON-LD, official bindings) and
CycloneDX 1.7 ML-BOM (with modelCard) generated from the same SystemRecord —
both validated against the real schemas at generation time, with
manual-input-required gaps reported instead of invented values.

## Design in one paragraph

One **SystemRecord** (YAML) describes the AI system — identity, Article 6
facts, models, datasets, dependencies, evaluations, questionnaire evidence.
The **knowledge base** (`aigov/knowledge/data/`) is versioned YAML: the
EU-article→ISO/NIST/OWASP crosswalk with a written rationale on every link,
plus the regulatory timeline (post-Digital-Omnibus dates) as data. The engine
classifies first (Art 6 gates everything), then assesses each obligation from
evidence — questionnaire answers, or fields derived automatically from the
BOM-facing dataset metadata (`auto.*` evidence keys). Verdicts are
Compliant / Partial / Gap / Not Applicable, each with a rationale citing the
clause, and each flagged **in force now vs. applies from a future date**.

## Quick start

```bash
pip install -e ".[dev]"
pytest                                        # 12 tests

aigov classify examples/resume_screener.yaml  # Article 6 only
aigov audit examples/resume_screener.yaml --out out --date 2026-07-03
aigov bom examples/resume_screener.yaml --out out   # SPDX 3.0.1 + CDX 1.7
aigov crosswalk --out out                     # export matrix (CSV/JSON)
```

Outputs: `out/audit_report.md`, `out/audit_report.html`, `out/bom.spdx3.json`,
`out/bom.cdx.json`, `out/bom_gaps.md`, `out/crosswalk.csv`, `out/crosswalk.json`.

## How the BOM is validated (not asserted)

- **CycloneDX 1.7**: `cyclonedx-python-lib`'s `JsonStrictValidator` with the
  bundled official schema. The library has no modelCard classes yet, so the
  document is built as a dict against the 1.7 schema — the strict validator
  is what makes that safe.
- **SPDX 3.0.1**: built with the official generated bindings
  (`spdx-python-model`, which type-check on assignment), then validated two
  ways: against the official JSON schema vendored from
  spdx.org/schema/3.0.1, and by round-tripping through the official
  JSON-LD deserializer.
- **Honesty rule**: fields that can't be automated (training-data provenance,
  dataset licensing, personal-data status) are flagged in `bom_gaps.md` and
  marked `MANUAL INPUT REQUIRED` / `aigov:manual_input_required` in the BOMs.
  A third-party foundation model is never linked to our declared datasets.

## Regulatory timeline handling

The Digital Omnibus on AI (Council final approval 29 Jun 2026; OJ publication
pending as of 2026-07-03) deferred Annex III high-risk obligations to
**2 Dec 2027** and Annex I to **2 Aug 2028**; Art 50 general transparency still
applies from **2 Aug 2026**, with a marking grace period to **2 Dec 2026** for
systems already on the market. All of this lives in
`aigov/knowledge/data/timeline.yaml` — a date change is a data edit plus a
`knowledge_version` bump, and every report cites the version it was assessed
under.

## Why the crosswalk is defensible

Every mapping in `aigov/knowledge/data/crosswalk/*.yaml` carries a `rationale`
field (enforced by test). See `docs/mapping_rationale.md` for methodology,
including what is anchored on NIST's published crosswalk vs. our own
derivation.

## Layout

```
aigov/
├── record.py              # SystemRecord — the one shared record (audit + BOM)
├── classify.py            # Art 6 decision tree (post-Omnibus rules)
├── assess.py              # evidence -> verdict + rationale + timeline flag
├── report.py              # Markdown/HTML report, crosswalk CSV/JSON
├── knowledge/             # loader + versioned YAML data (the IP)
│   └── data/{meta,timeline,classification}.yaml, crosswalk/article_*.yaml
├── bom/                   # Part 2: spdx_gen, cdx_gen, validate, gaps
│   └── schemas/spdx-3.0.1-schema.json   # vendored official schema
├── templates/report.md.j2
└── cli.py                 # aigov classify | audit | bom | crosswalk
```
