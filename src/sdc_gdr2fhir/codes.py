"""Codes as FHIR writes them: an IRI the model names a concept by, as the (system, code) a FHIR Coding takes.

The model binds an enumerated value to its definition (`rdfs:isDefinedBy`) and a component to concepts
(`skos:exactMatch`, `dcterms:subject`). sdc-mapper (4.3.0) reads those IRIs as a code system and a code; FHIR adds one
rule: a Coding names a code system, so only a concept of LOINC, SNOMED CT or the NCI Thesaurus, or an entry of an HL7
code system, is one. A page that defines a variable (an NHANES documentation page's `#SEQN`) or an ontology term
(`prov#Agent`) is read by the core but is not a Coding.
"""
from __future__ import annotations

import re

from sdc_mapper.codes import CONCEPT_LINKS, LOINC, NCIT, CodeRef, code_of
from sdc_mapper.codes import SNOMED_CT as SNOMED

UCUM = "http://unitsofmeasure.org"
_HL7_CODE_SYSTEM = re.compile(r"^https?://(?:hl7\.org/fhir|terminology\.hl7\.org/CodeSystem)/[A-Za-z0-9./-]+$")


def coding(iri: str | None) -> CodeRef | None:
    """The code an IRI names, when it is one a FHIR Coding can carry."""
    ref = code_of(iri)
    if ref and (ref.system in (LOINC, SNOMED, NCIT) or _HL7_CODE_SYSTEM.match(ref.system)):
        return ref
    return None


def model_codes(value) -> set[str]:
    """Every code the model names for a resolved value that a FHIR Coding can carry: its enumeration value's
    definition and the component's concept links. A code written that is one of these came from the model: a lookup."""
    iris = [value.code.defined_by] if value.code and value.code.defined_by else []
    iris += [i for p in CONCEPT_LINKS for i in (value.links or {}).get(p, [])]
    return {r.code for r in map(coding, iris) if r}


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
