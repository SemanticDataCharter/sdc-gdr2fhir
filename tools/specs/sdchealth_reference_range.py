"""SDCHealth Reference Range (`yg61wcme1sjlnezxh0ho6nh0`), a record chained to a Laboratory Observation
(`ojjr56tqlxk808lqq8ig8vg0`), written into that Observation's referenceRange in the report's FHIR R4 document Bundle
(HL7 Europe Laboratory Report 2.1.0).

The library models a result's reference ranges as records of their own (Xt-EHR EHDSLaboratoryObservation.referenceRange,
0..*), each chained to its observation by Parent Record Identifier, which holds the observation's Record Identifier
(library decisions 12 and 22). Each record is one `Observation.referenceRange` of the Observation that observation
writes (sdc-gdr2fhir's chain: `=entry#obs` is the entry of the record it is chained to). Targets are the guide's map of
the Xt-EHR Laboratory Observation (`map-ehdslaboratoryobservation.html`, MAP below): every referenceRange row is
"equivalent", except normalValue (no map: R5 only).

The data cluster's rule carries the `@chained-to` directive and places the record: every value below writes in the
record's own referenceRange (keyed apart from its siblings' by the chain).
"""
from common import C, OMIT_C, V
from sdchealth_parties import REVISION_DATE, SUBJECT_REASON, UCUM, k

TITLE = "SDCHealth Reference Range, chained to a Laboratory Observation, in its FHIR R4 document Bundle"
ID = "sdchealth-reference-range-fhir-r4"
VERSION = 1
AUTHOR = "Axius SDC, Inc."
DATE = REVISION_DATE
DESCRIPTION = ("An SDCHealth Reference Range record chained to a Laboratory Observation (library decisions 12 and 22): "
               "one referenceRange of that Observation (ObservationResultsLaboratoryEu, HL7 Europe Laboratory Report "
               "2.1.0) in the report's Bundle. It maps only with its observation and report (sdc-gdr2fhir's "
               "map_chain).")
REFERENCE_MODEL = True
PARTIES = {"subject": "Patient"}

LAB_OBSERVATION = "ojjr56tqlxk808lqq8ig8vg0"
RANGE = "/Bundle/=entry#obs/=resource/referenceRange"


def quantity(label, at):
    """A bound: its value, its UCUM code (the Quantity's code; the writer adds `unit`) and the system UCUM."""
    return V(label, f"{at}/value", units={"to": "@code", "transform": "copy"}, also=[k(f"{at}/system", UCUM)])


RULES = [
    # the record is one referenceRange of the Observation of the record it is chained to (MAP referenceRange ->
    # referenceRange)
    C("Reference Range", RANGE, attributes={"@chained-to": f"{LAB_OBSERVATION} obs"}),
    # MAP referenceRange.low / .high -> referenceRange.low / .high (inclusive bounds: no comparator is written)
    quantity("Reference Range Low", "low"),
    quantity("Reference Range High", "high"),
    # MAP referenceRange.type -> referenceRange.type (referencerange-meaning, the code the model binds: a lookup)
    V("Observation Reference Range Type", "type/coding/code", "binding",
      prefix="http://terminology.hl7.org/CodeSystem/referencerange-meaning",
      also=[k("type/coding/system", "http://terminology.hl7.org/CodeSystem/referencerange-meaning")]),
    # MAP referenceRange.appliesTo -> referenceRange.appliesTo (a CodeableConcept; the record's display text is its
    # text: a Coding's display is the code system's)
    C("Reference Range Applies To (SNOMED CT)", "+appliesTo"),
    V("Code System: SNOMED CT", "coding/system", within=["Reference Range Applies To (SNOMED CT)"]),
    V("Reference Range Applies To Code (SNOMED CT)", "coding/code"),
    V("Code Display Text", "text", within=["Reference Range Applies To (SNOMED CT)"]),
    # MAP referenceRange.age -> referenceRange.age (a Range of two quantities, in UCUM: `a` for years)
    C("Observation Reference Range Age", "age"),
    quantity("Observation Reference Range Age Low", "low"),
    quantity("Observation Reference Range Age High", "high"),
    # MAP referenceRange.text -> referenceRange.text
    V("Observation Reference Range Text", "text"),
    # MAP referenceRange.normalValue: no map ("R4 Observation has no such element ... exists only in R5")
    OMIT_C("Observation Reference Range Normal Value (SNOMED CT)",
           "the guide's map: R4 Observation has no such element (Observation.referenceRange.normalValue exists only in "
           "R5)"),
    # the chain itself
    V("Parent Record Identifier", "-", "omit",
      reason="the chain's join: the observation this range belongs to, whose referenceRange it is written in"),
    V("Sequence In Parent", "-", "omit",
      reason="the range's place among its observation's ranges: the order of Observation.referenceRange, which the "
             "chain gives in the order the records are given"),
    C("subject", "-", transform="omit", reason=SUBJECT_REASON),
]
