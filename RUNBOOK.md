# Runbook — how to run everything

Everything below assumes you are in the project root with Python 3.11+.
One-time setup:

```bash
pip install -e ".[dev,api,ui]"
```

## 1 · CLI (the core workflow)

```bash
# Article 6 classification only (fast pre-check, prints its reasoning)
aigov classify examples/resume_screener.yaml

# Full audit -> out/audit_report.md + .html
aigov audit examples/resume_screener.yaml --out out --date 2026-07-03

# Both AI-BOMs, schema-validated -> out/bom.spdx3.json, out/bom.cdx.json,
# out/bom_gaps.md (manual-input-required list). Exit code 1 if invalid.
aigov bom examples/resume_screener.yaml --out out

# Pre-fill a partial record from a HuggingFace-style model card
aigov ingest examples/model_card_mistral.md --out my_record.yaml

# Export the crosswalk matrix -> out/crosswalk.csv + .json
aigov crosswalk --out out
```

To audit your own system: copy `examples/resume_screener.yaml`, edit it
(or start from `aigov ingest`), and run the same commands against it.

## 2 · Web UI (client-facing questionnaire)

```bash
streamlit run aigov/ui.py
```

Opens at http://localhost:8501. Sidebar: load the demo system or upload a
record YAML. Tabs: edit the record → answer the questionnaire → run the
audit → generate BOMs → browse the crosswalk. Download buttons everywhere;
nothing is stored server-side.

## 3 · API (SaaS mode)

```bash
uvicorn aigov.api:app --port 8000          # open dev mode (warns)
# interactive docs: http://localhost:8000/docs
```

Locked-down mode:

```bash
export AIGOV_API_KEYS="sk-client-a,sk-client-b"
export AIGOV_RATE_LIMIT=60                  # req/min per key
uvicorn aigov.api:app --port 8000
```

```bash
curl http://localhost:8000/health           # always open
curl -X POST http://localhost:8000/v1/audit?include_report=true \
     -H "X-API-Key: sk-client-a" -H "Content-Type: application/json" \
     -d @record.json                        # record as JSON (same schema as the YAML)
```

Convert a YAML record to JSON for the API:

```bash
python -c "import json,yaml;print(json.dumps(yaml.safe_load(open('examples/resume_screener.yaml'))))" > record.json
```

## 4 · Docker

```bash
docker build -t aigov .
docker run -p 8000:8000 -e AIGOV_API_KEYS=sk-demo aigov
```

## 5 · Deploy (pick one)

- **Fly.io**: `fly launch --copy-config --no-deploy` →
  `fly secrets set AIGOV_API_KEYS=sk-...` → `fly deploy` (uses `fly.toml`)
- **Render**: connect the repo in the dashboard (uses `render.yaml`),
  set `AIGOV_API_KEYS` in the dashboard.

## 6 · Tests & validation

```bash
pytest                                       # full suite
python tools/validate_spdx_shacl.py out/bom.spdx3.json      # official SHACL model
cd tools && npm ci && node validate_cdx_independent.mjs ../out/bom.cdx.json
```

The last two are the independent cross-implementation checks; CI runs all of
this (plus a Docker build/boot probe) on every PR.

## 7 · Updating the regulatory knowledge base

When a date or mapping changes: edit the YAML under `aigov/knowledge/data/`,
bump `knowledge_version` in `meta.yaml`, add the source, run `pytest`.
Reports cite the knowledge version they were assessed under.
