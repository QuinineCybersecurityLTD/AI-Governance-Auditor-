"""aigov CLI: classify | audit | crosswalk"""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Optional

import typer

from aigov import knowledge
from aigov.assess import audit as run_audit
from aigov.classify import classify as run_classify
from aigov.record import SystemRecord
from aigov.report import export_crosswalk, write_reports

app = typer.Typer(help="AI Governance Auditor - EU AI Act / ISO 42001 / NIST AI RMF / OWASP LLM")


@app.command()
def classify(record_path: Path):
    """Run Article 6 classification only."""
    kb = knowledge.load()
    record = SystemRecord.from_yaml(record_path)
    result = run_classify(record, kb)
    typer.echo(f"System: {record.name}")
    typer.echo(f"Tier:   {result.tier.value}")
    for i, line in enumerate(result.reasoning, 1):
        typer.echo(f"  {i}. {line}")


@app.command()
def audit(
    record_path: Path,
    out: Path = typer.Option(Path("out"), help="Output directory"),
    date: Optional[str] = typer.Option(None, help="Assessment date YYYY-MM-DD (default: today)"),
):
    """Full audit: classification + per-obligation findings + report."""
    kb = knowledge.load()
    record = SystemRecord.from_yaml(record_path)
    classification = run_classify(record, kb)
    assessment_date = dt.date.fromisoformat(date) if date else None
    result = run_audit(record, kb, classification, assessment_date)
    written = write_reports(result, out)
    typer.echo(f"Classification: {classification.tier.value}")
    gaps = [f for f in result.findings if f.priority_score > 0]
    typer.echo(f"Findings: {len(result.findings)} assessed, {len(gaps)} gaps/partials")
    for p in written:
        typer.echo(f"Wrote {p}")


@app.command()
def bom(
    record_path: Path,
    out: Path = typer.Option(Path("out"), help="Output directory"),
):
    """Generate SPDX 3.0.1 AI Profile + CycloneDX 1.7 ML-BOM, validated."""
    import json

    from aigov.bom import build_cdx, build_spdx, manual_input_gaps, validate_cdx, validate_spdx

    record = SystemRecord.from_yaml(record_path)
    out.mkdir(parents=True, exist_ok=True)

    spdx_doc = build_spdx(record)
    cdx_doc = build_cdx(record)

    spdx_path = out / "bom.spdx3.json"
    cdx_path = out / "bom.cdx.json"
    spdx_path.write_text(json.dumps(spdx_doc, indent=2), encoding="utf-8")
    cdx_path.write_text(json.dumps(cdx_doc, indent=2), encoding="utf-8")

    spdx_errors = validate_spdx(spdx_doc)
    cdx_errors = validate_cdx(cdx_doc)
    typer.echo(f"Wrote {spdx_path}  [SPDX 3.0.1 schema + round-trip: "
               f"{'PASS' if not spdx_errors else 'FAIL'}]")
    typer.echo(f"Wrote {cdx_path}  [CycloneDX 1.7 strict schema: "
               f"{'PASS' if not cdx_errors else 'FAIL'}]")
    for e in spdx_errors + cdx_errors:
        typer.echo(f"  ERROR: {e}", err=True)

    gaps = manual_input_gaps(record)
    if gaps:
        gaps_path = out / "bom_gaps.md"
        lines = ["# BOM manual-input-required items", ""]
        lines += [f"- **{g.component}** `{g.field}` — {g.hint}" for g in gaps]
        gaps_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        typer.echo(f"Wrote {gaps_path}  ({len(gaps)} manual-input-required item(s))")
    else:
        typer.echo("No manual-input-required items.")

    if spdx_errors or cdx_errors:
        raise typer.Exit(code=1)


@app.command()
def ingest(
    model_card: Path,
    out: Path = typer.Option(Path("system_record.yaml"), help="Output record path"),
    name: Optional[str] = typer.Option(None, help="System name (default: model name)"),
):
    """Pre-fill a partial SystemRecord from a HuggingFace-style model card.

    Fills what a card can reliably state (model, license, base model, dataset
    ids, eval metrics); everything else is left for human completion and
    will surface as gaps - by design."""
    import yaml as _yaml

    from aigov.bom import manual_input_gaps
    from aigov.ingest import record_from_model_card

    record = record_from_model_card(model_card, system_name=name)
    out.write_text(
        _yaml.safe_dump(record.model_dump(mode="json"), sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    gaps = manual_input_gaps(record)
    typer.echo(f"Wrote {out} (partial record: {len(record.models)} model(s), "
               f"{len(record.datasets)} dataset(s), {len(record.evaluations)} evaluation(s))")
    typer.echo(f"{len(gaps)} field(s) still require manual input - run "
               f"'aigov bom {out}' to see them, or complete the record in the UI.")


@app.command()
def crosswalk(out: Path = typer.Option(Path("out"), help="Output directory")):
    """Export the full crosswalk matrix (CSV + JSON)."""
    kb = knowledge.load()
    for p in export_crosswalk(kb, out):
        typer.echo(f"Wrote {p}")


if __name__ == "__main__":
    app()
