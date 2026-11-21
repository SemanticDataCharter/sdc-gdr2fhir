"""SDCHealth Service Request (`nz971o74u4kuk3ifcxc2llq2`), a record chained to a Laboratory Report, in the report's
FHIR R4 document Bundle (HL7 Europe Laboratory Report 2.1.0).

Each record is one requested service: a ServiceRequest claiming the guide's ServiceRequestLabEu profile, which the
report's DiagnosticReport is based on (MAP body.serviceRequest -> DiagnosticReport.basedOn). Targets are the guide's
map of the Xt-EHR Service Request (`map-ehdsservicerequest.html`, MAP below).
"""
from common import C, OMIT_C, V
from sdchealth_parties import DR, LAB, LAB_REPORT, PARTY_DETAILS, PATIENT, PRACTITIONER, SUBJECT_REASON, k

TITLE = "SDCHealth Service Request, chained to a Laboratory Report, in its FHIR R4 document Bundle"
ID = "sdchealth-service-request-fhir-r4"
VERSION = 1
AUTHOR = "Axius SDC, Inc."
DATE = "2026-11-20"
DESCRIPTION = ("An SDCHealth Service Request record chained to a Laboratory Report (library decision 12): a "
               "ServiceRequest (ServiceRequestLabEu, HL7 Europe Laboratory Report 2.1.0) in the report's Bundle, which "
               "its DiagnosticReport is based on. It maps only with its report (sdc-gdr2fhir's map_chain).")
REFERENCE_MODEL = True
PARTIES = {"subject": "Patient", "provider": "Author"}

REQ = "/Bundle/=entry#req/=resource"
UCUM = "http://unitsofmeasure.org"

RULES = [
    C("Service Request", "Bundle", attributes={"@chained-to": f"{LAB_REPORT} req"}),
    # MAP header.status -> ServiceRequest.status (request-status, the code the model binds: a lookup). FHIR requires it,
    # so the ServiceRequest's constant members ride on it, and so does the report's reference to it (basedOn):
    # - intent: FHIR requires one and the record gives none (declared): `order`, a request the report answers;
    # - requester: the record's author (MAP header.author -> requester).
    V("Request Status", f"{REQ}/status", "binding", prefix="http://hl7.org/fhir/request-status",
      attributes={"resourceType": "ServiceRequest", "meta/profile": f"{LAB}ServiceRequest-eu-lab", "intent": "order",
                  "subject/reference": PATIENT, "requester/reference": "{entry#reqauthor}"},
      also=[k(f"{DR}/+basedOn/reference", "{entry#req}")]),
    # MAP header.identifier -> ServiceRequest.identifier (ServiceRequest-eu-lab: 1..*); the issuer: assigner, by display
    C("Record Identifier", f"{REQ}/identifier"),
    V("Identifier Value", "value", within=["Record Identifier"]),
    V("Issuing Authority", "assigner/display", within=["Record Identifier"]),
    # MAP header.date -> ServiceRequest.authoredOn (a dateTime: a date is one)
    V("Authored Date", f"{REQ}/authoredOn"),
    # MAP priority -> ServiceRequest.priority (request-priority, a lookup)
    V("Request Priority", f"{REQ}/priority", "binding", prefix="http://hl7.org/fhir/request-priority"),
    # MAP code -> ServiceRequest.code: the LOINC order code, the NPU and SNOMED CT service codes, codings of one code
    C("Order (LOINC)", f"{REQ}/code/coding#loinc"),
    V("Code System: LOINC", "system", within=["Order (LOINC)"]),
    V("Order Code (LOINC)", "code"),
    V("Code Display Text", "display", within=["Order (LOINC)"]),
    C("Service Request (NPU)", f"{REQ}/code/coding#npu"),
    V("Code System: NPU", "system", within=["Service Request (NPU)"]),
    V("Service Request Code (NPU)", "code"),
    V("Code Display Text", "display", within=["Service Request (NPU)"]),
    C("Service Request (SNOMED CT)", f"{REQ}/code/coding#sct"),
    V("Code System: SNOMED CT", "system", within=["Service Request (SNOMED CT)"]),
    V("Service Request Code (SNOMED CT)", "code"),
    V("Code Display Text", "display", within=["Service Request (SNOMED CT)"]),
    # MAP quantity -> ServiceRequest.quantityQuantity
    # the model's quantity units hold one text, "UCUM Units", not a UCUM code: the quantity's `unit`, no system or code
    V("Service Request Quantity", f"{REQ}/quantityQuantity/value", units={"to": "@unit", "transform": "copy"}),
    # MAP occurrence[x] -> occurrencePeriod
    C("Service Request Occurrence Period", f"{REQ}/occurrencePeriod"),
    V("Period Start (DateTime)", "start", within=["Service Request Occurrence Period"]),
    V("Period End (DateTime)", "end", within=["Service Request Occurrence Period"]),
    V("Order Requested Date", "-", "omit",
      reason="ServiceRequest.occurrence[x] holds the occurrence period; the requested date has no second place"),
    # MAP reason[x] -> reasonCode (coded): each diagnosis a reasonCode of its own
    *[x for label, system_label in (("Diagnosis (ICD-10)", "Code System: ICD-10"),
                                    ("Diagnosis (ORPHAcode)", "Code System: ORPHAcode"),
                                    ("Diagnosis (SNOMED CT)", "Code System: SNOMED CT"))
      for x in (C(label, f"{REQ}/+reasonCode"),
                V(system_label, "coding/system", within=[label]),
                V("Code Display Text", "text", within=[label]))],
    V("Diagnosis Code (ICD-10)", "coding/code"),
    V("Diagnosis Code (ORPHAcode)", "coding/code"),
    V("Diagnosis Code (SNOMED CT)", "coding/code"),
    V("Service Request Reason", "-", "omit",
      reason="the IRIs of other records, as one list value; ServiceRequest.reasonReference takes references to "
             "resources, and the records are not in the chain"),
    # MAP bodySite -> ServiceRequest.bodySite (a CodeableConcept): the site's code
    C("Body Structure", "."),
    C("Body Site (SNOMED CT)", f"{REQ}/bodySite"),
    V("Code System: SNOMED CT", "coding/system", within=["Body Site (SNOMED CT)"]),
    V("Body Site Code (SNOMED CT)", "coding/code"),
    V("Code Display Text", "text", within=["Body Site (SNOMED CT)"]),
    *[OMIT_C(c, "R4's ServiceRequest.bodySite is a CodeableConcept, the site; laterality, location qualifier and "
                "morphology are a BodyStructure's")
      for c in ("Body Structure Laterality (SNOMED CT)", "Body Structure Location Qualifier (SNOMED CT)",
                "Body Structure Morphology (SNOMED CT)")],
    V("Body Structure Description", "-", "omit",
      reason="a BodyStructure's description; R4's ServiceRequest.bodySite is a CodeableConcept, the site's code"),
    # MAP specimen -> ServiceRequest.specimen: IRIs of records of the chain, one reference each
    V("Service Request Specimen Reference", f"{REQ}/+specimen#record/reference"),
    # MAP supportingInformation[x], encounter: references to resources; the record holds IRIs of records not in the
    # chain
    V("Service Request Supporting Information Reference", "-", "omit",
      reason="the IRIs of other records, as one list value; ServiceRequest.supportingInfo takes references to "
             "resources, and the records are not in the chain"),
    V("Service Request Encounter Reference", "-", "omit",
      reason="the IRI of an encounter record, which is not in the chain; ServiceRequest.encounter takes a reference "
             "to a resource"),
    # MAP patientInstructions -> patientInstruction; a note -> note
    V("Patient Instructions", f"{REQ}/patientInstruction"),
    V("Request Note", f"{REQ}/+note/text"),
    # MAP header.source: no target ("ServiceRequest has no element for the source of the information")
    OMIT_C("Information Source (Coded, System Stated)",
           "the guide's map gives header.source no target: ServiceRequest has no element for the source of the "
           "information"),
    V("Parent Record Identifier", "-", "omit",
      reason="the chain's join: the report this record belongs to, which is the Bundle it is written in"),

    # ================================================================ the reference-model parts
    C("subject", "-", transform="omit", reason=SUBJECT_REASON),
    # MAP header.author -> ServiceRequest.requester (a Practitioner of its own; the status rule writes the reference)
    C("provider", "/Bundle/=entry#reqauthor/=resource", attributes=PRACTITIONER),
    C("party-details", "."),
    *PARTY_DETAILS,
]


# ================================================================ the 2026-11-21 revision
#: Service Request `i1jm5rf4ooomt8tbys75o017` (PRD decision 22) chains to the revised Laboratory Report, and its
#: quantity's units are a UCUM code (any, by the pattern `[!-~]{1,60}`): the Quantity's code, with the system UCUM.
REVISED = "i1jm5rf4ooomt8tbys75o017"


def configure(ct_id):
    global DATE, RULES
    from sdchealth_parties import LAB_REPORT_2, REVISION_DATE, chained_to, ucum
    if ct_id == REVISED:
        DATE, RULES = REVISION_DATE, ucum(chained_to(RULES, LAB_REPORT_2))
