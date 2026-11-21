"""SDCHealth Laboratory Observation (`d5b3007cqbmejx7xgs7i484r`), a record chained to a Laboratory Report, in the
report's FHIR R4 document Bundle (HL7 Europe Laboratory Report 2.1.0).

Each record is one result: an Observation claiming the guide's ObservationResultsLaboratoryEu profile, which the
report's DiagnosticReport lists (`result`) and the Composition's results section lists (`section.entry`; MAP
body.resultData.laboratoryTestResults -> DiagnosticReport.result and Composition section.entry). Targets are the guide's
map of the Xt-EHR Laboratory Observation (`map-ehdslaboratoryobservation.html`, MAP below).

The section: the guide's top-level sections are laboratory specialties (its study-type codes). The model gives an
observation no specialty or study type, so every result goes in one section coded with the study type that covers them
all, LOINC 26436-6 Laboratory studies (set) (in the guide's lab-studyType-eu-lab; LOINC 2.83, looked up on tx.fhir.org
20 November 2026). Its narrative is generated from its entries (the writer).
"""
from common import C, OMIT_C, V
from sdchealth_parties import (COMP, DR, EU_BASE, LAB, LAB_REPORT, PARTY_DETAILS, PATIENT, PRACTITIONER, SUBJECT_REASON,
                               E, k)

TITLE = "SDCHealth Laboratory Observation, chained to a Laboratory Report, in its FHIR R4 document Bundle"
ID = "sdchealth-lab-observation-fhir-r4"
VERSION = 1
AUTHOR = "Axius SDC, Inc."
DATE = "2026-11-20"
DESCRIPTION = ("An SDCHealth Laboratory Observation record chained to a Laboratory Report (library decision 12): an "
               "Observation (ObservationResultsLaboratoryEu, HL7 Europe Laboratory Report 2.1.0) in the report's "
               "Bundle, listed by its DiagnosticReport and its results section. It maps only with its report "
               "(sdc-gdr2fhir's map_chain).")
REFERENCE_MODEL = True
PARTIES = {"subject": "Patient", "provider": "Author"}

OBS = "/Bundle/=entry#obs/=resource"
LOINC = "http://loinc.org"
UCUM = "http://unitsofmeasure.org"
CATEGORY = "http://terminology.hl7.org/CodeSystem/observation-category"
#: The model's quantity units hold one text, "UCUM Units" (each schema enumerates it), not a UCUM code: it is the
#: quantity's `unit` (the unit as written), with no `system` or `code`, so no UCUM code is claimed.
UNITS = {"to": "@unit", "transform": "copy"}


def quantity(label, at, **kw):
    """A quantity: its value and the unit as the record writes it."""
    return V(label, f"{at}/value", units=UNITS, **kw)


RULES = [
    C("Laboratory Observation", "Bundle", attributes={"@chained-to": f"{LAB_REPORT} obs"}),
    # MAP header.status -> Observation.status (observation-status, the code the model binds: a lookup). FHIR and the
    # profile require it, so the Observation's constant members ride on it, and so do the report's references to it:
    # DiagnosticReport.result and an entry of the results section.
    # - category: the profile's laboratory slice (pattern observation-category `laboratory`);
    # - performer: the record's author (MAP header.author -> performer: "usually the performer is also the author");
    # - the section: title, code (study type 26436-6) joined, so every result shares it.
    V("Observation Status", f"{OBS}/status", "binding", prefix="http://hl7.org/fhir/observation-status",
      attributes={"resourceType": "Observation", "meta/profile": f"{LAB}Observation-resultslab-eu-lab",
                  "category/coding/system": CATEGORY, "category/coding/code": "laboratory",
                  "subject/reference": PATIENT, "performer#author/reference": "{entry#obsauthor}"},
      also=[k(f"{DR}/+result/reference", "{entry#obs}"),
            k(f"{COMP}/=section#results/+entry/reference", "{entry#obs}"),
            k(f"{COMP}/=section#results/=title", "Laboratory studies"),
            k(f"{COMP}/=section#results/=code/=coding/=system", LOINC),
            k(f"{COMP}/=section#results/=code/=coding/=code", "26436-6"),
            k(f"{COMP}/=section#results/=code/=coding/=display", "Laboratory studies (set)")]),
    # MAP header.identifier -> Observation.identifier; the issuer is a name: assigner, by display
    C("Record Identifier", f"{OBS}/identifier"),
    V("Identifier Value", "value", within=["Record Identifier"]),
    V("Issuing Authority", "assigner/display", within=["Record Identifier"]),
    # MAP type -> Observation.code: the LOINC result code, and the NPU and SNOMED CT observation types, each a coding
    # of the one code (codings of the same concept in other systems). The record's display texts are the codings'
    # displays. MAP originalName -> code.text.
    C("Result Code (LOINC)", f"{OBS}/code/coding#loinc"),
    V("Code System: LOINC", "system", within=["Result Code (LOINC)"]),
    V("Result Code Code (LOINC)", "code"),
    V("Code Display Text", "display", within=["Result Code (LOINC)"]),
    C("Observation Type (NPU)", f"{OBS}/code/coding#npu"),
    V("Code System: NPU", "system", within=["Observation Type (NPU)"]),
    V("Observation Type Code (NPU)", "code"),
    V("Code Display Text", "display", within=["Observation Type (NPU)"]),
    C("Observation Type (SNOMED CT)", f"{OBS}/code/coding#sct"),
    V("Code System: SNOMED CT", "system", within=["Observation Type (SNOMED CT)"]),
    V("Observation Type Code (SNOMED CT)", "code"),
    V("Code Display Text", "display", within=["Observation Type (SNOMED CT)"]),
    V("Observation Original Name", f"{OBS}/code/text"),
    # MAP observationDate[x] -> effective[x] (the profile requires one): a time, or a period
    V("Observation Date Time", f"{OBS}/effectiveDateTime"),
    C("Observation Period", f"{OBS}/effectivePeriod"),
    V("Period Start (DateTime)", "start", within=["Observation Period"]),
    V("Period End (DateTime)", "end", within=["Observation Period"]),
    # MAP header.date -> Observation.issued, an instant: a time and a zone. The model's Authored Date is a date.
    V("Authored Date", "-", "omit",
      reason="Observation.issued is an instant (a time and a zone), and the model's Authored Date is a date"),
    # MAP result.value[x] -> value[x]: the record holds one of a quantity, a coded value, a text, a ratio or a range
    C("Observation Result", "."),
    quantity("Result Quantity", f"{OBS}/valueQuantity"),
    C("Result Coded (SNOMED CT)", f"{OBS}/valueCodeableConcept"),
    V("Code System: SNOMED CT", "coding/system", within=["Result Coded (SNOMED CT)"]),
    V("Result Coded Code (SNOMED CT)", "coding/code"),
    V("Code Display Text", "text", within=["Result Coded (SNOMED CT)"]),
    V("Result Value Text", f"{OBS}/valueString"),
    C("Result Ratio", f"{OBS}/valueRatio"),
    quantity("Result Ratio Numerator", "numerator"),
    quantity("Result Ratio Denominator", "denominator"),
    C("Result Range", f"{OBS}/valueRange"),
    quantity("Result Range Low", "low"),
    quantity("Result Range High", "high"),
    # MAP result.dataAbsentReason -> dataAbsentReason (data-absent-reason, the code the model binds: a lookup)
    # joined: a result value that is an Exceptional Value writes the same dataAbsentReason (the writer), and the two
    # must agree
    V("Data Absent Reason", f"{OBS}/=dataAbsentReason/=coding/=code", "binding",
      prefix="http://terminology.hl7.org/CodeSystem/data-absent-reason",
      also=[k(f"{OBS}/=dataAbsentReason/=coding/=system", "http://terminology.hl7.org/CodeSystem/data-absent-reason")]),
    # MAP result.uncertainty -> the quantity's iso21090-uncertainty and -uncertaintyType extensions
    C("Observation Result Uncertainty", "."),
    V("Observation Result Uncertainty Value", f"{OBS}/valueQuantity/extension#uncertainty/valueDecimal",
      also=[k(f"{OBS}/valueQuantity/extension#uncertainty/url",
              "http://hl7.org/fhir/StructureDefinition/iso21090-uncertainty")]),
    V("Observation Result Uncertainty Type", f"{OBS}/valueQuantity/extension#utype/valueCode", "binding",
      prefix="http://terminology.hl7.org/CodeSystem/v3-ProbabilityDistributionType",
      also=[k(f"{OBS}/valueQuantity/extension#utype/url",
              "http://hl7.org/fhir/StructureDefinition/iso21090-uncertaintyType")]),
    # MAP interpretation -> Observation.interpretation: the v3 ObservationInterpretation code the model binds (a
    # lookup) and the SNOMED CT one, two codings of the one interpretation
    V("Interpretation Code", f"{OBS}/interpretation/coding#v3/code", "binding",
      prefix="http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation",
      also=[k(f"{OBS}/interpretation/coding#v3/system",
              "http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation")]),
    C("Interpretation (SNOMED CT)", f"{OBS}/interpretation/coding#sct"),
    V("Code System: SNOMED CT", "system", within=["Interpretation (SNOMED CT)"]),
    V("Interpretation Code (SNOMED CT)", "code"),
    V("Code Display Text", "display", within=["Interpretation (SNOMED CT)"]),
    # MAP method -> Observation.method
    C("Observation Method (SNOMED CT)", f"{OBS}/method"),
    V("Code System: SNOMED CT", "coding/system", within=["Observation Method (SNOMED CT)"]),
    V("Observation Method Code (SNOMED CT)", "coding/code"),
    V("Code Display Text", "text", within=["Observation Method (SNOMED CT)"]),
    # MAP bodySite -> Observation.bodySite (a CodeableConcept in R4): the site's code; laterality, location qualifier
    # and morphology are BodyStructure's (the R5 bodyStructure extension takes a reference), not written here
    C("Body Structure", "."),
    C("Body Site (SNOMED CT)", f"{OBS}/bodySite"),
    V("Code System: SNOMED CT", "coding/system", within=["Body Site (SNOMED CT)"]),
    V("Body Site Code (SNOMED CT)", "coding/code"),
    V("Code Display Text", "text", within=["Body Site (SNOMED CT)"]),
    *[OMIT_C(c, "R4's Observation.bodySite is one CodeableConcept, the site; laterality, location qualifier and "
                "morphology are a BodyStructure's, which the guide references by an R5 extension not written here")
      for c in ("Body Structure Laterality (SNOMED CT)", "Body Structure Location Qualifier (SNOMED CT)",
                "Body Structure Morphology (SNOMED CT)")],
    V("Body Structure Description", "-", "omit",
      reason="a BodyStructure's description; R4's Observation.bodySite is a CodeableConcept, the site's code"),
    # MAP note -> Observation.note
    V("Note", f"{OBS}/+note/text"),
    # MAP specimen -> Observation.specimen; MAP order -> Observation.basedOn: the IRI of a record of the chain,
    # written as the reference to its entry (sdc-gdr2fhir's chain)
    V("Observation Specimen Reference", f"{OBS}/specimen#record/reference"),
    V("Observation Order Reference", f"{OBS}/+basedOn#record/reference"),
    # MAP header.source: no target ("Observation has no element for the source of the information")
    OMIT_C("Information Source (Coded, System Stated)",
           "the guide's map gives header.source no target: Observation has no element for the source of the "
           "information"),
    # the references to records outside the chain (other observations, test kits): IRIs, not resources of the Bundle
    *[V(label, "-", "omit", reason="the IRIs of other records, which are not in the chain; FHIR's references name "
                                   "resources")
      for label in ("Lab Observation Previous Results Reference", "Lab Observation Triggered By Reference",
                    "Observation Derived From Reference", "Observation Has Member Reference",
                    "Lab Observation Test Kit Reference")],
    # MAP accredited -> the profile's accredited extension; the point-of-care flag and the calibrator have no element
    # in R4 or the guide's profile that this mapping writes
    V("Lab Observation Accreditation Status", "-", "omit",
      reason="the guide's accredited extension is not written here: its definition was not checked for this mapping"),
    V("Lab Observation Point Of Care Test", "-", "omit",
      reason="FHIR R4's Observation and the guide's profile have no element for a point-of-care test"),
    OMIT_C("Lab Observation Calibrator",
           "the guide's certified reference material extension is not written here: its definition was not checked "
           "for this mapping"),
    V("Parent Record Identifier", "-", "omit",
      reason="the chain's join: the report this record belongs to, which is the Bundle it is written in"),

    # ================================================================ the reference-model parts
    C("subject", "-", transform="omit", reason=SUBJECT_REASON),
    # MAP header.author -> Observation.performer (a Practitioner of its own; the Observation Status rule writes the
    # reference)
    C("provider", "/Bundle/=entry#obsauthor/=resource", attributes=PRACTITIONER),
    # MAP performer[x] -> Observation.performer: the performing laboratory, an Organization
    C("performer", "/Bundle/=entry#obsorg/=resource", within=["Performer Participation"],
      attributes={"resourceType": "Organization", "meta/profile": f"{EU_BASE}organization-eu-core"}),
    V("Participation Function (Performer)", f"{OBS}/performer#org/reference", "code",
      table={"performer": "{entry#obsorg}"}),
    *[E(t, "-", "omit", within=["Performer Participation"],
        reason="Observation.performer is a reference alone, with no time") for t in ("start", "end")],
    # MAP header.directSubject -> Observation.focus: the direct subject, a Patient of its own
    C("performer", "/Bundle/=entry#obsfocus/=resource", within=["Direct Subject Participation"],
      attributes={"resourceType": "Patient", "meta/profile": f"{EU_BASE}patient-eu-core"}),
    V("Participation Function (Direct Subject)", f"{OBS}/focus/reference", "code",
      table={"direct subject": "{entry#obsfocus}"}),
    *[E(t, "-", "omit", within=["Direct Subject Participation"],
        reason="Observation.focus is a reference alone, with no time") for t in ("start", "end")],
    C("party-details", "."),
    *PARTY_DETAILS,
]
