"""SDCHealth Specimen Collection (`idprzkpm6sdqgib5w5wzc3ys`), a record chained to a Specimen
(`dkzoy1j9aw2u7i7x5lseo7ro`), written into that Specimen's collection in the report's FHIR R4 document Bundle
(HL7 Europe Laboratory Report 2.1.0).

Xt-EHR's EHDSSpecimen.collection is a record of its own in the library, chained to its specimen by Parent Record
Identifier (library decisions 12 and 22). A Specimen has no Record Identifier, so the Parent Record Identifier holds
the specimen's Accession Identifier (sdc-gdr2fhir's chain matches either). The record is the `Specimen.collection` of
the Specimen that specimen writes (`=entry#spec` is the entry of the record it is chained to). FHIR R4's
Specimen.collection is one element, so a specimen takes one collection: a second one's values are second values for
the same elements, and the chain is refused. Targets are the guide's map of the Xt-EHR Specimen (`map-ehdsspecimen.html`,
MAP below).
"""
from common import C, OMIT_C, V
from sdchealth_parties import (PARTY_DETAILS, PRACTITIONER, REVISION_DATE, SUBJECT_REASON, UCUM, E, k)

TITLE = "SDCHealth Specimen Collection, chained to a Specimen, in its FHIR R4 document Bundle"
ID = "sdchealth-specimen-collection-fhir-r4"
VERSION = 1
AUTHOR = "Axius SDC, Inc."
DATE = REVISION_DATE
DESCRIPTION = ("An SDCHealth Specimen Collection record chained to a Specimen (library decisions 12 and 22): the "
               "collection of that Specimen (SpecimenEu, HL7 Europe Laboratory Report 2.1.0) in the report's Bundle, "
               "with its collector. It maps only with its specimen and report (sdc-gdr2fhir's map_chain).")
REFERENCE_MODEL = True
PARTIES = {"subject": "Patient"}

SPECIMEN = "dkzoy1j9aw2u7i7x5lseo7ro"
COLLECTION = "/Bundle/=entry#spec/=resource/collection"

RULES = [
    # MAP collection -> Specimen.collection
    C("Specimen Collection", COLLECTION, attributes={"@chained-to": f"{SPECIMEN} spec"}),
    # MAP collection.collected[x] -> collection.collected[x]: a time, or a period. The model asks for one of them (an
    # assertion) and allows both; FHIR's collected[x] takes one, so a record with both makes a Specimen HL7's validator
    # refuses (a library finding).
    V("Collected Date Time", "collectedDateTime"),
    C("Specimen Collection Period", "collectedPeriod"),
    V("Period Start (DateTime)", "start", within=["Specimen Collection Period"]),
    V("Period End (DateTime)", "end", within=["Specimen Collection Period"]),
    # MAP collection.quantity -> collection.quantity (a SimpleQuantity: value, UCUM code and system)
    V("Specimen Collection Quantity", "quantity/value", units={"to": "@code", "transform": "copy"},
      also=[k("quantity/system", UCUM)]),
    # MAP collection.method -> collection.method
    C("Specimen Collection Method (SNOMED CT)", "method"),
    V("Code System: SNOMED CT", "coding/system", within=["Specimen Collection Method (SNOMED CT)"]),
    V("Specimen Collection Method Code (SNOMED CT)", "coding/code"),
    V("Code Display Text", "text", within=["Specimen Collection Method (SNOMED CT)"]),
    # MAP collection.bodySite -> collection.bodySite's R5 bodySite extension (a reference to a BodyStructure). R4's
    # collection.bodySite is a CodeableConcept: the site's code is written there, as for Observation.bodySite;
    # laterality, location qualifier and morphology are a BodyStructure's, not written here.
    C("Body Structure", "."),
    C("Body Site (SNOMED CT)", "bodySite"),
    V("Code System: SNOMED CT", "coding/system", within=["Body Site (SNOMED CT)"]),
    V("Body Site Code (SNOMED CT)", "coding/code"),
    V("Code Display Text", "text", within=["Body Site (SNOMED CT)"]),
    *[OMIT_C(c, "R4's Specimen.collection.bodySite is one CodeableConcept, the site; laterality, location qualifier "
                "and morphology are a BodyStructure's, which the guide references by an R5 extension not written here")
      for c in ("Body Structure Laterality (SNOMED CT)", "Body Structure Location Qualifier (SNOMED CT)",
                "Body Structure Morphology (SNOMED CT)")],
    V("Body Structure Description", "-", "omit",
      reason="a BodyStructure's description; R4's Specimen.collection.bodySite is a CodeableConcept, the site's code"),
    # MAP collection.device: no map ("R4 Specimen has no such element ... exists only in R5")
    V("Specimen Collection Device Reference", "-", "omit",
      reason="the guide's map: R4 Specimen has no such element (Specimen.collection.device exists only in R5)"),
    # the chain itself
    V("Parent Record Identifier", "-", "omit",
      reason="the chain's join: the specimen this collection belongs to, whose collection it is written in"),
    V("Sequence In Parent", "-", "omit",
      reason="the collection's place among its specimen's collections; FHIR R4's Specimen has one collection"),

    # ================================================================ the reference-model parts
    C("subject", "-", transform="omit", reason=SUBJECT_REASON),
    # MAP collection.performer[x] -> collection.collector: a health professional, a Practitioner of its own
    C("performer", "/Bundle/=entry#collector/=resource", within=["Specimen Collector Participation"],
      attributes=PRACTITIONER),
    V("Participation Function (Specimen Collector)", "/Bundle/=entry#spec/=resource/=collection/collector/reference",
      "code", table={"specimen collector": "{entry#collector}"}),
    # the collection's time is the record's own (Collected Date Time or the period); the Participation's times would be
    # a second value for collected[x]
    *[E(t, "-", "omit", within=["Specimen Collector Participation"],
        reason="the collection's time is the record's Collected Date Time or Specimen Collection Period "
               "(collection.collected[x]); Specimen.collection.collector is a reference alone, with no time")
      for t in ("start", "end")],
    C("party-details", "."),
    *PARTY_DETAILS,
]
