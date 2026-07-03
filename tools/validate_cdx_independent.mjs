// Independent CycloneDX validation: the OFFICIAL JavaScript implementation
// (@cyclonedx/cyclonedx-library) validating a BOM produced by our Python
// pipeline. Different codebase, same spec - if both accept it, the BOM is
// conformant, not just self-consistent.
//
// Usage: node tools/validate_cdx_independent.mjs out/bom.cdx.json

import { readFileSync } from "node:fs";
import { Validation } from "@cyclonedx/cyclonedx-library";

const path = process.argv[2] ?? "out/bom.cdx.json";
const raw = readFileSync(path, "utf-8");
const specVersion = JSON.parse(raw).specVersion;

const validator = new Validation.JsonStrictValidator(specVersion);
try {
  const errors = await validator.validate(raw);
  if (errors === null) {
    console.log(`PASS: ${path} is valid CycloneDX ${specVersion} (JS implementation)`);
    process.exit(0);
  }
  console.error(`FAIL: ${JSON.stringify(errors, null, 2)}`);
  process.exit(1);
} catch (e) {
  if (e instanceof Validation.MissingOptionalDependencyError) {
    console.error("Missing optional dep: install ajv + ajv-formats next to the library");
    process.exit(2);
  }
  throw e;
}
