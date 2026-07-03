"""SystemRecord -> SPDX 3.0.1 AI Profile (JSON-LD).

Built on the official generated bindings (spdx-python-model), which enforce
the SHACL-derived type model at assignment time. Serialized output is
additionally validated in validate.py against the official JSON schema and
round-tripped through the official deserializer.

Element IDs are deterministic (urn:aigov:<system>:<kind>:<name>) so repeated
runs diff cleanly.
"""

from __future__ import annotations

import datetime as dt
import io
import json
import re

from spdx_python_model import v3_0_1 as spdx

from aigov import __version__
from aigov.record import SystemRecord

_SPDX_ID_RE = re.compile(r"^[A-Za-z0-9.\-]+$")


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _license_expression(text: str) -> str:
    """Valid SPDX ids pass through; anything else becomes a LicenseRef-."""
    if _SPDX_ID_RE.match(text):
        return text
    return "LicenseRef-" + _slug(text)


def build_spdx(record: SystemRecord, created: dt.datetime | None = None) -> dict:
    base = f"urn:aigov:{_slug(record.name)}"
    created = created or dt.datetime.now(dt.timezone.utc)
    elements: list = []

    ci = spdx.CreationInfo()
    ci.specVersion = "3.0.1"
    ci.created = created

    tool = spdx.Tool()
    tool.set_id(f"{base}:tool:aigov")
    tool.name = f"aigov {__version__}"
    tool.creationInfo = ci
    ci.createdUsing.append(tool)
    elements.append(tool)

    provider = spdx.Agent()
    provider.set_id(f"{base}:agent:provider")
    provider.name = record.provider or "NOASSERTION"
    provider.creationInfo = ci
    ci.createdBy.append(provider)
    elements.append(provider)

    def _new(cls, eid: str):
        el = cls()
        el.set_id(eid)
        el.creationInfo = ci
        elements.append(el)
        return el

    rel_count = 0

    def _rel(from_el, rel_type, to_els):
        nonlocal rel_count
        rel_count += 1
        r = _new(spdx.Relationship, f"{base}:rel:{rel_count}")
        r.from_ = from_el
        r.relationshipType = rel_type
        for t in to_els:
            r.to.append(t)
        return r

    def _declare_license(el, license_text: str | None):
        if not license_text:
            return  # absence is reported via gaps.py, never invented
        lic = _new(spdx.simplelicensing_LicenseExpression,
                   f"{base}:license:{_slug(license_text)}-{rel_count}")
        lic.simplelicensing_licenseExpression = _license_expression(license_text)
        _rel(el, spdx.RelationshipType.hasDeclaredLicense, [lic])

    # --- the AI system itself -------------------------------------------
    system = _new(spdx.ai_AIPackage, f"{base}:system")
    system.name = record.name
    system.software_packageVersion = record.version
    system.description = record.description or None
    system.software_primaryPurpose = spdx.software_SoftwarePurpose.application
    system.suppliedBy = provider
    if record.known_limitations:
        system.ai_limitation = " | ".join(record.known_limitations)
    if record.intended_purpose:
        system.ai_informationAboutApplication = (
            f"Intended purpose: {record.intended_purpose} "
            f"Restrictions: {record.use_restrictions or 'NOASSERTION'}"
        )
    if record.datasets:
        trained_on = [d.name for d in record.datasets if d.role in ("training", "fine-tuning")]
        system.ai_informationAboutTraining = (
            f"Trained/fine-tuned on declared dataset(s): {', '.join(trained_on)}."
            if trained_on else "MANUAL INPUT REQUIRED: no training datasets declared."
        )
    personal = [d.contains_personal_data for d in record.datasets]
    if any(personal):
        system.ai_useSensitivePersonalInformation = spdx.PresenceType.NAMED_INDIVIDUALS["yes"]
    elif all(p is False for p in personal) and personal:
        system.ai_useSensitivePersonalInformation = spdx.PresenceType.NAMED_INDIVIDUALS["no"]
    else:
        system.ai_useSensitivePersonalInformation = spdx.PresenceType.NAMED_INDIVIDUALS["noAssertion"]
    for ev in record.evaluations:
        entry = spdx.DictionaryEntry()
        entry.key = ev.name
        entry.value = ev.value
        system.ai_metric.append(entry)

    # --- model components -------------------------------------------------
    model_pkgs = []
    for m in record.models:
        pkg = _new(spdx.ai_AIPackage, f"{base}:model:{_slug(m.name)}")
        pkg.name = m.name
        pkg.software_packageVersion = m.version or None
        pkg.software_primaryPurpose = spdx.software_SoftwarePurpose.model
        if m.architecture_family:
            pkg.ai_typeOfModel.append(m.architecture_family)
        if m.source_url:
            pkg.software_downloadLocation = m.source_url
        if m.provider:
            supplier = _new(spdx.Agent, f"{base}:agent:{_slug(m.provider)}")
            supplier.name = m.provider
            pkg.suppliedBy = supplier
        else:
            pkg.suppliedBy = provider
        _declare_license(pkg, m.license)
        model_pkgs.append(pkg)
    if model_pkgs:
        _rel(system, spdx.RelationshipType.contains, model_pkgs)

    # --- datasets ----------------------------------------------------------
    trained, tested, inputs = [], [], []
    for d in record.datasets:
        ds = _new(spdx.dataset_DatasetPackage, f"{base}:dataset:{_slug(d.name)}")
        ds.name = d.name
        ds.dataset_datasetType.append(spdx.dataset_DatasetType.noAssertion)
        ds.software_primaryPurpose = spdx.software_SoftwarePurpose.data
        ds.software_downloadLocation = d.source or None
        ds.dataset_intendedUse = f"Role in this system: {d.role}."
        if d.provenance:
            ds.dataset_dataCollectionProcess = d.provenance
        else:
            ds.comment = ("MANUAL INPUT REQUIRED: data collection process and "
                          "origin (provenance) not documented.")
        if d.preparation:
            ds.dataset_dataPreprocessing.append(d.preparation)
        if d.known_gaps:
            ds.dataset_datasetNoise = d.known_gaps
        if d.bias_assessment:
            ds.dataset_knownBias.append(d.bias_assessment)
        if d.contains_personal_data is True:
            ds.dataset_hasSensitivePersonalInformation = spdx.PresenceType.NAMED_INDIVIDUALS["yes"]
        elif d.contains_personal_data is False:
            ds.dataset_hasSensitivePersonalInformation = spdx.PresenceType.NAMED_INDIVIDUALS["no"]
        else:
            ds.dataset_hasSensitivePersonalInformation = spdx.PresenceType.NAMED_INDIVIDUALS["noAssertion"]
        _declare_license(ds, d.license)
        if d.role in ("training", "fine-tuning"):
            trained.append(ds)
        elif d.role in ("validation", "testing"):
            tested.append(ds)
        else:
            inputs.append(ds)
    if trained:
        _rel(system, spdx.RelationshipType.trainedOn, trained)
    if tested:
        _rel(system, spdx.RelationshipType.testedOn, tested)
    if inputs:
        _rel(system, spdx.RelationshipType.hasInput, inputs)

    # --- software dependencies ---------------------------------------------
    dep_pkgs = []
    for dep in record.dependencies:
        pkg = _new(spdx.software_Package, f"{base}:dependency:{_slug(dep.name)}")
        pkg.name = dep.name
        pkg.software_packageVersion = dep.version or None
        pkg.software_primaryPurpose = spdx.software_SoftwarePurpose.library
        pkg.description = dep.purpose or None
        _declare_license(pkg, dep.license)
        dep_pkgs.append(pkg)
    if dep_pkgs:
        _rel(system, spdx.RelationshipType.dependsOn, dep_pkgs)

    # --- document wrapper ----------------------------------------------------
    doc = _new(spdx.SpdxDocument, f"{base}:document")
    doc.name = f"{record.name} AI-BOM (SPDX 3.0.1 AI Profile)"
    doc.rootElement.append(system)
    for pi in ("core", "software", "simpleLicensing", "ai", "dataset"):
        doc.profileConformance.append(getattr(spdx.ProfileIdentifierType, pi))
    for el in elements:
        if el is not doc:
            doc.element.append(el)

    objset = spdx.SHACLObjectSet()
    for el in elements:
        objset.add(el)
    objset.link()

    buf = io.BytesIO()
    spdx.JSONLDSerializer().write(objset, buf)
    return json.loads(buf.getvalue().decode("utf-8"))
