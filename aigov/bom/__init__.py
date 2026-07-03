"""AI-BOM generation (Part 2): one SystemRecord, two standards-conformant
export formats - SPDX 3.0.1 AI Profile (JSON-LD) and CycloneDX 1.7 ML-BOM
(JSON) - both validated against the real schemas, never just asserted.
"""

from aigov.bom.gaps import manual_input_gaps
from aigov.bom.spdx_gen import build_spdx
from aigov.bom.cdx_gen import build_cdx
from aigov.bom.validate import validate_cdx, validate_spdx

__all__ = ["manual_input_gaps", "build_spdx", "build_cdx", "validate_cdx", "validate_spdx"]
