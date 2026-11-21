"""SDCHealth Order Information (`l6m7g3jk6y6tvnisd35l16pw`), a record chained to a Laboratory Report, in the report's
FHIR R4 document Bundle (HL7 Europe Laboratory Report 2.1.0).

The guide's map of the Xt-EHR Laboratory Report (`map-ehdslaboratoryreport.html`) makes each order a
ServiceRequestLabEu that DiagnosticReport.basedOn references, with body.orderInformation's children as its elements.
The report's mapping already writes that ServiceRequest (`entry#sr`) from its Order Placer Participation; Order
Information fills in the rest of it: the order's identifier (which ServiceRequest-eu-lab requires), when it was
placed, why, and the clinical question. A report has one such ServiceRequest, so it takes one Order Information; a
second one's identifier is a second value for the same element, and the chain is refused.

Targets are the guide's map rows (MAP below). The ServiceRequest's constant members are the report mapping's, written
here too (joined, so the same value twice), so a report without an order placer still has a whole ServiceRequest.
"""
from common import C, V
from sdchealth_parties import DR, LAB, LAB_REPORT, ORDER, PATIENT, SUBJECT_REASON, k

TITLE = "SDCHealth Order Information, chained to a Laboratory Report, in its FHIR R4 document Bundle"
ID = "sdchealth-order-information-fhir-r4"
VERSION = 1
AUTHOR = "Axius SDC, Inc."
DATE = "2026-11-20"
DESCRIPTION = ("An SDCHealth Order Information record chained to a Laboratory Report (library decision 12), written "
               "into the report's ServiceRequest (ServiceRequest-eu-lab, HL7 Europe Laboratory Report 2.1.0). It maps "
               "only with its report (sdc-gdr2fhir's map_chain).")
REFERENCE_MODEL = True
PARTIES = {"subject": "Patient"}

RULES = [
    # the record's own Bundle rule: it chains to the Laboratory Report, and writes into the report's entry#sr
    C("Order Information", "Bundle", attributes={"@chained-to": f"{LAB_REPORT} sr"}),
    # MAP body.orderInformation.orderId -> ServiceRequest.identifier (ServiceRequest-eu-lab: 1..*). The issuer is a
    # name: the identifier's assigner, by display (HL7 Europe Base's identifier map). The ServiceRequest's constant
    # members are the report mapping's, joined.
    C("Order Identifier", "."),
    V("Identifier Value", f"{ORDER}/identifier/value", within=["Order Identifier"],
      also=[k(f"{ORDER}/=resourceType", "ServiceRequest"), k(f"{ORDER}/=meta/=profile", f"{LAB}ServiceRequest-eu-lab"),
            k(f"{ORDER}/=status", "unknown"), k(f"{ORDER}/=intent", "order"),
            k(f"{ORDER}/=subject/=reference", PATIENT)]),
    V("Issuing Authority", f"{ORDER}/identifier/assigner/display", within=["Order Identifier"]),
    # MAP body.orderInformation.orderDateAndTime -> ServiceRequest.authoredOn. The report's Order Placer
    # Participation writes its start there too: the two must agree, or the chain is refused (two values).
    V("Order Authored Date", f"{ORDER}/=authoredOn"),
    # MAP body.orderInformation.orderReason[x] -> ServiceRequest.reasonCode / reasonReference: coded, a reasonCode
    C("Order Reason (SNOMED CT)", f"{ORDER}/reasonCode"),
    V("Code System: SNOMED CT", "coding/system", within=["Order Reason (SNOMED CT)"]),
    V("Order Reason Code (SNOMED CT)", "coding/code"),
    V("Code Display Text", "text", within=["Order Reason (SNOMED CT)"]),
    V("Order Reason Reference", "-", "omit",
      reason="the IRIs of other records, as one list value; ServiceRequest.reasonReference takes references to "
             "resources, and the records are not in the chain"),
    # MAP body.orderInformation.clinicalQuestion -> ServiceRequest.note
    V("Clinical Question", f"{ORDER}/+note/text"),
    # the chain itself: the parent and the order of the record among its siblings
    V("Parent Record Identifier", "-", "omit",
      reason="the chain's join: the report this record belongs to, which is the Bundle it is written in"),
    V("Sequence In Parent", "-", "omit",
      reason="the record's place among the report's orders; a report takes one Order Information, and FHIR's "
             "ServiceRequest has no element for it"),
    # the subject: the report's
    C("subject", "-", transform="omit", reason=SUBJECT_REASON),
]


# ================================================================ the 2026-11-21 revision
#: Order Information `zfh7quqpqxk176c2j4gdestb` (PRD decision 22: the clinical question is optional) chains to the
#: revised Laboratory Report; the rules are otherwise the first revision's.
REVISED = "zfh7quqpqxk176c2j4gdestb"


def configure(ct_id):
    global DATE, RULES
    from sdchealth_parties import LAB_REPORT_2, REVISION_DATE, chained_to
    if ct_id == REVISED:
        DATE, RULES = REVISION_DATE, chained_to(RULES, LAB_REPORT_2)
