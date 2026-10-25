"""Codes as FHIR writes them: an IRI the model binds a value to, as a (system, code) pair FHIR's Coding takes.

A model binds an enumerated value to its definition (`rdfs:isDefinedBy`) and a component to concepts (`skos:exactMatch`,
`dcterms:subject`). Where such an IRI names one concept of a code system FHIR knows, the pair below is that concept as a
FHIR Coding; an IRI that names a whole system, or a page that defines a variable rather than one answer, gives none.
"""
from __future__ import annotations

import re

LOINC = "http://loinc.org"
SNOMED = "http://snomed.info/sct"
NCIT = "http://ncicb.nci.nih.gov/xml/owl/EVS/Thesaurus.owl"
UCUM = "http://unitsofmeasure.org"

_PATTERNS = [
    (re.compile(r"^https?://loinc\.org/((?:LA|LP|LG)?[0-9]+-[0-9])/?$"), LOINC),
    (re.compile(r"^https?://snomed\.info/id/([0-9]+)$"), SNOMED),
    (re.compile(r"^https?://purl\.obolibrary\.org/obo/NCIT_(C[0-9]+)$"), NCIT),
]
_FRAGMENT = re.compile(r"^(https?://(?:hl7\.org/fhir|terminology\.hl7\.org/CodeSystem)/[A-Za-z0-9./-]+)#([^#\s]+)$")


def coding(iri: str | None) -> tuple[str, str] | None:
    """The (system, code) an IRI names, or None."""
    if not iri:
        return None
    for pattern, system in _PATTERNS:
        m = pattern.match(iri)
        if m:
            return system, m.group(1)
    m = _FRAGMENT.match(iri)
    if m:
        return m.group(1), m.group(2)
    return None


def bound_codes(value) -> set[str]:
    """Every code the model binds a resolved value to: its enumeration value's definition, and the component's
    exact matches and subjects. A target code that is one of these comes from the model: a lookup."""
    iris = []
    if value.code and value.code.defined_by:
        iris.append(value.code.defined_by)
    for predicate, targets in (value.links or {}).items():
        if predicate.endswith(("#exactMatch", "/subject")):
            iris.extend(targets)
    return {c[1] for c in map(coding, iris) if c}


#: The Default library's unit symbols that are not already UCUM codes.
UCUM_CODES = {"mmHg": "mm[Hg]"}

#: ISO 21090 null flavors as FHIR R4 writes them. Where the data-absent-reason code system has the same concept, it is
#: written (as Observation.dataAbsentReason, or the data-absent-reason extension on any other element); every other
#: code is written exactly, from v3 NullFlavor, with the iso21090-nullFlavor extension (or as a v3 NullFlavor coding of
#: dataAbsentReason, whose binding is extensible). v3 NullFlavor has no Asked and Refused; data-absent-reason does.
DATA_ABSENT_REASON = "http://terminology.hl7.org/CodeSystem/data-absent-reason"
V3_NULL_FLAVOR = "http://terminology.hl7.org/CodeSystem/v3-NullFlavor"
DAR_EXTENSION = "http://hl7.org/fhir/StructureDefinition/data-absent-reason"
NULL_FLAVOR_EXTENSION = "http://hl7.org/fhir/StructureDefinition/iso21090-nullFlavor"
DAR = {"UNK": "unknown", "ASKU": "asked-unknown", "NAV": "temp-unknown", "NASK": "not-asked", "ASKR": "asked-declined",
       "MSK": "masked", "NA": "not-applicable", "NINF": "negative-infinity", "PINF": "positive-infinity"}
V3_ONLY = ("NI", "INV", "DER", "OTH", "UNC", "QS", "TRC")


def absent(code: str) -> tuple[str, str, str]:
    """(code system, code, extension url) FHIR writes for an ISO 21090 code."""
    if code in DAR:
        return DATA_ABSENT_REASON, DAR[code], DAR_EXTENSION
    return V3_NULL_FLAVOR, code, NULL_FLAVOR_EXTENSION
