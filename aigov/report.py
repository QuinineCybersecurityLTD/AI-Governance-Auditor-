"""Report generation: Markdown (Jinja2) -> HTML, plus crosswalk CSV/JSON export."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import markdown as md
from jinja2 import Environment, FileSystemLoader

from aigov.assess import AuditResult
from aigov.knowledge import KnowledgeBase

TEMPLATE_DIR = Path(__file__).parent / "templates"

_HTML_SHELL = """<!doctype html><html><head><meta charset="utf-8">
<title>{title}</title><style>
body{{font-family:Segoe UI,system-ui,sans-serif;max-width:960px;margin:2rem auto;
padding:0 1rem;line-height:1.5;color:#1a1a1a}}
table{{border-collapse:collapse;width:100%;font-size:.9rem}}
th,td{{border:1px solid #ccc;padding:.4rem .6rem;text-align:left;vertical-align:top}}
th{{background:#f0f2f5}}
code{{background:#f4f4f4;padding:0 .25rem}}
.status-Gap{{color:#b00020;font-weight:600}}
.status-Partial{{color:#b36b00;font-weight:600}}
.status-Compliant{{color:#1a7f37;font-weight:600}}
blockquote{{border-left:4px solid #ccc;margin-left:0;padding-left:1rem;color:#444}}
</style></head><body>{body}</body></html>"""


def render_markdown(result: AuditResult) -> str:
    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR), trim_blocks=True, lstrip_blocks=True)
    gaps = sorted(
        (f for f in result.findings if f.priority_score > 0),
        key=lambda f: f.priority_score,
        reverse=True,
    )
    return env.get_template("report.md.j2").render(r=result, gaps=gaps)


def write_reports(result: AuditResult, out_dir: str | Path) -> list[Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    written = []

    md_text = render_markdown(result)
    md_path = out / "audit_report.md"
    md_path.write_text(md_text, encoding="utf-8")
    written.append(md_path)

    body = md.markdown(md_text, extensions=["tables"])
    html_path = out / "audit_report.html"
    html_path.write_text(
        _HTML_SHELL.format(title=f"AI Act audit - {result.system_name}", body=body),
        encoding="utf-8",
    )
    written.append(html_path)
    return written


def export_crosswalk(kb: KnowledgeBase, out_dir: str | Path) -> list[Path]:
    """Export the full crosswalk matrix as CSV and JSON."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for article in kb.articles:
        for ob in article.obligations:
            for fw, maps in ob.mappings.items():
                for m in maps:
                    rows.append({
                        "eu_ai_act_article": article.article,
                        "clause": ob.clause,
                        "obligation_id": ob.id,
                        "framework": fw,
                        "mapped_ref": m.ref,
                        "condition": m.when or "",
                        "rationale": " ".join(m.rationale.split()),
                    })
    csv_path = out / "crosswalk.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    json_path = out / "crosswalk.json"
    json_path.write_text(
        json.dumps({"knowledge_version": kb.version, "mappings": rows}, indent=2),
        encoding="utf-8",
    )
    return [csv_path, json_path]
