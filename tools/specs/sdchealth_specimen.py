"""SDCHealth Specimen (`qws8pcquvnqc55okidyqll83`), a record chained to a Laboratory Report by reference, in the
report's FHIR R4 document Bundle (HL7 Europe Laboratory Report 2.1.0).

A specimen carries no Record or Parent Record Identifier (as in the Xt-EHR model): the report's observations and
requests name it, and it is identified by its accession identifier. It is a Specimen claiming the guide's SpecimenEu
profile, which the report's DiagnosticReport lists (MAP body.specimen -> DiagnosticReport.specimen). Targets are the
guide's map of the Xt-EHR Specimen (`map-ehdsspecimen.html`, MAP below).
"""
from common import C, V
from sdchealth_parties import DR, LAB, LAB_REPORT, PARTY_DETAILS, PATIENT, PRACTITIONER, SUBJECT_REASON, E, k

TITLE = "SDCHealth Specimen, chained to a Laboratory Report, in its FHIR R4 document Bundle"
ID = "sdchealth-specimen-fhir-r4"
VERSION = 1
AUTHOR = "Axius SDC, Inc."
DATE = "2026-11-20"
DESCRIPTION = ("An SDCHealth Specimen record chained to a Laboratory Report by reference (library decision 12): a "
               "Specimen (SpecimenEu, HL7 Europe Laboratory Report 2.1.0) in the report's Bundle, listed by its "
               "DiagnosticReport. It maps only with its report (sdc-gdr2fhir's map_chain).")
REFERENCE_MODEL = True
PARTIES = {"subject": "Patient"}

SPEC = "/Bundle/=entry#spec/=resource"

RULES = [
    C("Specimen", "Bundle", attributes={"@chained-to": f"{LAB_REPORT} spec"}),
    # MAP receivedDate -> Specimen.receivedTime. The Specimen's constant members, and the report's reference to it
    # (DiagnosticReport.specimen), ride on the accession identifier, by which the other records name the specimen.
    # MAP identifier -> the accession identifier (the identifier the laboratory gives the specimen)
    V("Accession Identifier", f"{SPEC}/accessionIdentifier/value",
      attributes={"resourceType": "Specimen", "meta/profile": f"{LAB}Specimen-eu-lab", "subject/reference": PATIENT},
      also=[k(f"{DR}/+specimen/reference", "{entry#spec}")]),
    V("Received Date Time", f"{SPEC}/receivedTime"),
    # MAP status -> Specimen.status (specimen-status, the code the model binds: a lookup)
    V("Specimen Status", f"{SPEC}/status", "binding", prefix="http://hl7.org/fhir/specimen-status"),
    # MAP type -> Specimen.type
    C("Specimen Type (SNOMED CT)", f"{SPEC}/type"),
    V("Code System: SNOMED CT", "coding/system", within=["Specimen Type (SNOMED CT)"]),
    V("Specimen Type Code (SNOMED CT)", "coding/code"),
    V("Code Display Text", "text", within=["Specimen Type (SNOMED CT)"]),
    # MAP condition -> Specimen.condition (v2-0493, the code the model binds: a lookup)
    V("Specimen Condition", f"{SPEC}/condition/coding/code", "binding",
      prefix="http://terminology.hl7.org/CodeSystem/v2-0493",
      also=[k(f"{SPEC}/condition/coding/system", "http://terminology.hl7.org/CodeSystem/v2-0493")]),
    # MAP combined: no target ("R4 Specimen has no such element; Specimen.combined exists only in R5")
    V("Specimen Combined", "-", "omit",
      reason="the guide's map: R4 Specimen has no such element (Specimen.combined exists only in R5)"),
    # MAP note -> Specimen.note
    V("Note", f"{SPEC}/+note/text"),
    # MAP request -> Specimen.request, MAP parentSpecimen -> Specimen.parent: IRIs of records of the chain, written as
    # references to their entries (sdc-gdr2fhir's chain), one per IRI
    V("Specimen Request Reference", f"{SPEC}/+request#record/reference"),
    V("Specimen Parent Specimen Reference", f"{SPEC}/+parent#record/reference"),
    # MAP specimenSource[x] -> Specimen.subject: the report's patient, written above; the Source Participation names
    # the same person (below), and an IRI of another source is not a resource of the Bundle
    V("Specimen Source Reference", "-", "omit",
      reason="Specimen.subject is the report's patient (the chain's subject); the IRI of another source record is "
             "not a resource of the Bundle"),

    # ================================================================ the reference-model parts
    C("subject", "-", transform="omit", reason=SUBJECT_REASON),
    # MAP collection.performer[x] -> collection.collector (a health professional: a Practitioner of its own);
    # MAP collection.collected[x] -> collection.collectedDateTime: the collector Participation's start
    C("performer", "/Bundle/=entry#collector/=resource", within=["Specimen Collector Participation"],
      attributes=PRACTITIONER),
    V("Participation Function (Specimen Collector)", f"{SPEC}/collection/collector/reference", "code",
      table={"specimen collector": "{entry#collector}"}),
    E("start", f"{SPEC}/collection/collectedDateTime", within=["Specimen Collector Participation"]),
    E("end", "-", "omit", within=["Specimen Collector Participation"],
      reason="the collection's time is the collector Participation's start (collectedDateTime)"),
    # MAP specimenSource[x] -> Specimen.subject: the source Participation is the patient the specimen is from, the
    # report's
    C("performer", "-", within=["Specimen Source Participation"], transform="omit", reason=SUBJECT_REASON),
    V("Participation Function (Specimen Source)", "-", "omit",
      reason="the source is the report's patient, Specimen.subject (written with the accession identifier)"),
    *[E(t, "-", "omit", within=["Specimen Source Participation"],
        reason="Specimen.subject is a reference alone, with no time") for t in ("start", "end")],
    C("party-details", "."),
    *PARTY_DETAILS,
]
