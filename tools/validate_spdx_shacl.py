"""Independent SPDX validation: pyshacl conformance check of our JSON-LD
against the OFFICIAL SPDX 3.0.1 SHACL model (spdx-model.ttl) - the normative
machine-readable definition of the spec, evaluated by a generic SHACL engine
that knows nothing about our generator.

Usage: python tools/validate_spdx_shacl.py out/bom.spdx3.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from pyshacl import validate
from rdflib import Graph

HERE = Path(__file__).parent
MODEL_TTL = HERE / "spdx-model-3.0.1.ttl"
LOCAL_CONTEXT = HERE / "spdx-context-3.0.1.jsonld"


def main(bom_path: str) -> int:
    payload = json.loads(Path(bom_path).read_text(encoding="utf-8"))
    # swap the remote @context for the vendored copy: offline + reproducible
    payload["@context"] = json.loads(LOCAL_CONTEXT.read_text(encoding="utf-8"))["@context"]

    data = Graph().parse(data=json.dumps(payload), format="json-ld")
    shacl = Graph().parse(MODEL_TTL, format="turtle")

    # Matches the SPDX project's documented invocation:
    #   pyshacl -s spdx-model.ttl -e spdx-model.ttl data.jsonld
    # No inference: RDFS materialization would add abstract superclass types
    # (AIPackage -> SoftwareArtifact) and falsely trip the abstract-class
    # shapes. SHACL does subclass targeting natively via the ontology graph.
    conforms, _, results_text = validate(
        data_graph=data,
        shacl_graph=shacl,
        ont_graph=shacl,
        inference="none",
        abort_on_first=False,
    )
    if conforms:
        print(f"PASS: {bom_path} conforms to the official SPDX 3.0.1 SHACL model "
              f"({len(data)} triples checked)")
        return 0
    print(results_text)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "out/bom.spdx3.json"))
