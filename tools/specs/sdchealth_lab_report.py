"""The SDCHealth Laboratory Report model as a FHIR R4 document Bundle, following the HL7 Europe Laboratory Report guide.

Guide: HL7 Europe Laboratory Report 2.1.0, `hl7.fhir.eu.laboratory#2.1.0` (FHIR 4.0.1), https://hl7.eu/fhir/laboratory/2.1.0/
Each rule's target comes from the element's Xt-EHR 1.0.0 link and the guide's map of the Xt-EHR Laboratory Report model,
https://hl7.eu/fhir/laboratory/2.1.0/map-ehdslaboratoryreport.html (cited below as MAP), with HL7 Europe Base 2.0.1's
maps for the parts the lab map leaves to it (https://hl7.eu/fhir/base/2.0.1/, cited as BASE) and the R5 model map's
document maps (https://build.fhir.org/ig/hl7-eu/base-r5/map-ehdsdocument.html, cited as DOC).

The record's subject (the Patient), provider (the Author), its four Participations (attester, custodian, intended
recipient, order placer), its Attestation (the legal authentication) and its workflow (the document's status) are the
SDC4 reference model's DM-level parts, outside the data cluster. sdcreader 4.5.0 and sdc-mapper 4.4.0 read and place
them when the mapping says `reference_model: true` (REFERENCE_MODEL below). Their paths are absolute, from /Bundle.

Resources:
- the Composition (Composition-eu-lab) and the DiagnosticReport (DiagnosticReport-eu-lab);
- the Patient (patient-eu-core), the record's subject, which also carries the sex for clinical use;
- a Practitioner (practitioner-eu-core) for each of the author, the attester, the legal authenticator and the order
  placer;
- the custodian Organization (organization-eu-core);
- the intended recipient, a Patient: the model's intended recipient is a person of the Patient cluster;
- the ServiceRequest (ServiceRequest-eu-lab) that carries the order placer.
Several entries share a resource type, so each is tagged (`entry#author`) and referenced by its tag (`{entry#author}`,
sdc-gdr2fhir's writer).
"""
from common import C, OMIT_C, V, coded

TITLE = "SDCHealth Laboratory Report to HL7 FHIR R4 document Bundle (HL7 Europe Laboratory Report 2.1.0)"
ID = "sdchealth-lab-report-fhir-r4"
VERSION = 1
AUTHOR = "Axius SDC, Inc."
DATE = "2026-11-20"
DESCRIPTION = ("The SDCHealth Laboratory Report model in a FHIR R4 document Bundle that claims the HL7 Europe Laboratory "
               "Report 2.1.0 profiles (Bundle, Composition, DiagnosticReport, ServiceRequest; Patient, Practitioner and "
               "Organization from HL7 Europe Base 2.0.1), with the record's parties, attestation and workflow "
               "(reference_model). Resources and places are declared; codes the model binds are the model's own.")
#: Read the record's reference-model parts (sdc-mapper 4.4.0 `reference_model: true`).
REFERENCE_MODEL = True
#: Which Party fills the DM's base-typed `subject` and `provider` slots, as sdcreader joins them (by the record's
#: label). build_mapping uses it to check that every part's value reaches a rule.
PARTIES = {"subject": "Patient", "provider": "Author"}

LAB = "http://hl7.eu/fhir/laboratory/StructureDefinition/"
EU_BASE = "http://hl7.eu/fhir/base/StructureDefinition/"
COMP = "=entry#comp/=resource"
DR = "=entry#dr/=resource"
PAT = "=entry#patient/=resource"
#: Composition.extension:diagnosticReport (Composition-eu-lab): the DiagnosticReport the Composition goes with.
COMPOSITION_DR = "http://hl7.eu/fhir/extensions/StructureDefinition/composition-diagnosticReportReference"
#: DiagnosticReport.extension:DiagnosticReportCompositionR5 (DiagnosticReport-eu-lab, required 1..1).
DR_COMPOSITION = "http://hl7.org/fhir/5.0/StructureDefinition/extension-DiagnosticReport.composition"
#: Composition.extension:version (Composition-eu-lab; MAP header.version).
COMPOSITION_VERSION = "http://hl7.org/fhir/5.0/StructureDefinition/extension-Composition.version"
#: PatientEuCore's extension:sex-for-clinical-use (MAP body.supportingInformation.sexForClinicalUse), whose `value`
#: part is a CodeableConcept bound (required) to HL7's sex-parameter-for-clinical-use value set.
SEX_FOR_CLINICAL_USE = "http://hl7.org/fhir/StructureDefinition/patient-sexParameterForClinicalUse"
#: Composition.extension:informationRecipient (Composition-eu-lab; MAP header.intendedRecipient).
INFORMATION_RECIPIENT = "http://hl7.eu/fhir/StructureDefinition/information-recipient"
V2_0203 = "http://terminology.hl7.org/CodeSystem/v2-0203"
PRACTITIONER = {"resourceType": "Practitioner", "meta/profile": f"{EU_BASE}practitioner-eu-core"}
B = "/Bundle"
SR = "/Bundle/=entry#sr/=resource"
ACOMP = f"{B}/{COMP}"


def k(path, value):
    return {"to": path, "transform": "constant", "value": value}


def E(element, to, transform="copy", **kw):
    """A reference-model element that holds a plain value (`start`, `committed`, `pending`; sdc-mapper 4.4.0)."""
    return {"element": element, "to": to, "transform": transform, **kw}


def coded_type(label):
    """An identifier's type token as a CodeableConcept: the token as text, the code the model binds it to (v2-0203)."""
    return V(label, "type/text", derive=coded("type/coding"))


def states(also_to):
    """derive: a workflow state (an ordinal) as the composition-status code the model defines it by, by a table copied
    from the model's schema, written here and at `also_to`."""
    def derive(_component, enums):
        table = {v: iri.split("#", 1)[1] for v, iri in enums if iri.startswith("http://hl7.org/fhir/composition-status#")}
        return {"transform": "code", "table": table, "also": [{"to": also_to, "transform": "code", "table": dict(table)}]}
    return derive


def coded_text(label, to, **kw):
    """A token as a CodeableConcept: the token as text, and the code the model binds it to as the Coding."""
    at = to.rsplit("/", 1)[0]
    return V(label, to, derive=coded(f"{at}/coding"), **kw)


RULES = [
    # ---------------------------------------------------------------- the Bundle (BundleLabReportEu)
    # identifier: the writer's own, the record's instance id (bdl-9). MAP sends header.identifier to Bundle.identifier
    # too, but the record's identifier has no system (its issuer is a name), and bdl-9 requires one.
    C("Laboratory Report", "Bundle", attributes={
        "resourceType": "Bundle", "type": "document", "meta/profile": f"{LAB}Bundle-eu-lab",
        "@first": "Composition DiagnosticReport Patient"}),

    # ---------------------------------------------------------------- the Composition (CompositionLabReportEu)
    # MAP header.documentTitle -> Composition.title. The Composition's constant members ride on this rule: the model
    # requires the title (an assertion on the data cluster), so every record has the Composition.
    # The subject (MAP header.subject, also the DiagnosticReport's: dr-comp-subj) and the author (MAP header.author)
    # are references to the entries the record's subject and provider make.
    V("Document Header Title", f"{COMP}/title", attributes={
        "resourceType": "Composition", "meta/profile": f"{LAB}Composition-eu-lab",
        "extension#dr/url": COMPOSITION_DR, "extension#dr/valueReference/reference": "{DiagnosticReport}",
        "subject/reference": "{entry#patient}", "author/reference": "{entry#author}",
        # the record's language (its dm-language, fixed by the model): what its text is written in
        "language": "{record:dm-language}"},
      # the DiagnosticReport's constant members: written with the Composition, so the two always go together
      also=[k(f"{DR}/resourceType", "DiagnosticReport"), k(f"{DR}/meta/profile", f"{LAB}DiagnosticReport-eu-lab"),
            k(f"{DR}/extension#comp/url", DR_COMPOSITION),
            k(f"{DR}/extension#comp/valueReference/reference", "{Composition}"),
            k(f"{DR}/subject/reference", "{entry#patient}"), k(f"{DR}/language", "{record:dm-language}")]),
    # MAP header.date -> Composition.date; DOC (report) header.date -> DiagnosticReport.issued; the document's time is
    # the Bundle's timestamp (bdl-10). An instant needs a time and a zone: a record dated by day alone is refused.
    V("Authored Date", "timestamp", also=[{"to": f"{COMP}/date", "transform": "copy"},
                                          {"to": f"{DR}/issued", "transform": "copy"}]),
    # MAP header.identifier -> Composition.identifier and DiagnosticReport.identifier (the guide's dr-comp-identifier:
    # the same value in both). The issuer is a name, so it is the identifier's assigner, by display.
    C("Record Identifier", "."),
    V("Identifier Value", f"{COMP}/identifier/value", within=["Record Identifier"],
      also=[{"to": f"{DR}/identifier/value", "transform": "copy"}]),
    V("Issuing Authority", f"{COMP}/identifier/assigner/display", within=["Record Identifier"],
      also=[{"to": f"{DR}/identifier/assigner/display", "transform": "copy"}]),
    # MAP header.version -> Composition extension:version
    V("Version", f"{COMP}/extension#version/valueString", also=[k(f"{COMP}/extension#version/url", COMPOSITION_VERSION)]),
    # MAP header.documentType -> Composition.type and DiagnosticReport.code (the guide's dr-comp-type: the same
    # system and code in both). The model does not bind the code (any LOINC code), so it is the record's: declared. The
    # record's display text is the CodeableConcept's text (a Coding's display is the code system's).
    C("Document Type (LOINC)", "."),
    V("Code System: LOINC", f"{COMP}/type/coding/system", also=[{"to": f"{DR}/code/coding/system", "transform": "copy"}]),
    V("Document Type Code (LOINC)", f"{COMP}/type/coding/code",
      also=[{"to": f"{DR}/code/coding/code", "transform": "copy"}]),
    V("Code Display Text", f"{COMP}/type/text", within=["Document Type (LOINC)"],
      also=[{"to": f"{DR}/code/text", "transform": "copy"}]),
    # MAP header.eventType -> Composition category:studyType, whose binding (required) is the guide's LOINC study
    # types; the model codes the event in SNOMED CT, which that value set does not hold. DOC: "eventType -> category
    # (or event.code in R4)": Composition.event.code. MAP header.period -> Composition.event.period, the same event.
    C("Document Event Type (SNOMED CT)", "."),
    V("Code System: SNOMED CT", f"{COMP}/=event/code/coding/system", within=["Document Event Type (SNOMED CT)"]),
    V("Document Event Type Code (SNOMED CT)", f"{COMP}/=event/code/coding/code"),
    V("Code Display Text", f"{COMP}/=event/code/text", within=["Document Event Type (SNOMED CT)"]),
    # MAP header.period -> Composition.event.period; DOC (report) header.period -> DiagnosticReport.effectivePeriod
    C("Document Period", "."),
    V("Document Period Start", f"{COMP}/=event/period/start", also=[{"to": f"{DR}/effectivePeriod/start", "transform": "copy"}]),
    V("Document Period End", f"{COMP}/=event/period/end", also=[{"to": f"{DR}/effectivePeriod/end", "transform": "copy"}]),
    # MAP header.practiceSetting: no row. The guide's specialty category (category:specialty, bound (required) to
    # lab-specialty-eu-lab, SNOMED CT laboratory specialties) is header.serviceSpecialty's, which the model does not
    # have; the practice setting is not the service's specialty.
    OMIT_C("Practice Setting (SNOMED CT)",
           "the HL7 Europe Laboratory Report guide 2.1.0's map has no row for header.practiceSetting; its specialty "
           "category (lab-specialty-eu-lab, SNOMED CT laboratory specialties) is header.serviceSpecialty's, which "
           "the model does not have"),
    # The record this one belongs to (PRD decision 12: an entry's document, a reaction's allergy). A report belongs to
    # no other record; Composition.relatesTo is a document's relation to another document (replaces, appends,
    # transforms, signs), not belonging, so it is not that.
    V("Parent Record Identifier", "-", "omit",
      reason="FHIR's Composition has no element for the record a document belongs to (relatesTo is a relation "
             "between documents: replaces, appends, transforms, signs)"),

    # ---------------------------------------------------------------- the DiagnosticReport (DiagnosticReportLabEu)
    # MAP presentedForm -> DiagnosticReport.presentedForm; EHDSAttachment's elements map one to one (map-ehdsattachment)
    C("Attachment", "."),
    V("Document Title", f"{DR}/presentedForm/title"),
    V("Document URL", f"{DR}/presentedForm/url"),
    V("Media Type", f"{DR}/presentedForm/contentType"),
    V("Document Size", f"{DR}/presentedForm/size"),
    V("Attachment Data", "-", "omit",
      reason="EHDSAttachment.data and FHIR's Attachment.data are the bytes, base64-encoded; the record's XdFile gives "
             "its content by URI, which is not the bytes (the report's address is Document URL, Attachment.url)"),
    C("Lab Report Body", "."),
    C("Lab Report Result Data Section", "."),
    # MAP body.resultData.commentsInterpretationAndRecommendations -> Composition section:text, and/or
    # DiagnosticReport.conclusion: both. The section is Composition-eu-lab's `annotations` slice: "narrative
    # expression of comments accompanying the report, such as suggestions for evaluation", no entries, its code the
    # slice's pattern, LOINC 48767-8 (Annotation comment [Interpretation] Narrative; LOINC 2.83, looked up on
    # tx.fhir.org 20 November 2026). Its text is the comment, escaped, as XHTML (the writer); `additional`, since the
    # section has no entries the text could be generated from. A comment the record does not have (an Exceptional
    # Value) writes no section: the reason is on the conclusion.
    V("Lab Report Result Data Comments Interpretation And Recommendations", f"{DR}/conclusion",
      also=[{"to": f"{COMP}/section#notes/text/div", "transform": "copy"},
            k(f"{COMP}/section#notes/text/status", "additional"),
            k(f"{COMP}/section#notes/title", "Comments, interpretation and recommendations"),
            k(f"{COMP}/section#notes/code/coding/system", "http://loinc.org"),
            k(f"{COMP}/section#notes/code/coding/code", "48767-8"),
            k(f"{COMP}/section#notes/code/coding/display", "Annotation comment [Interpretation] Narrative")]),
    C("Lab Report Supporting Information Section", "."),
    # MAP body.supportingInformation.sexForClinicalUse -> Patient extension:sex-for-clinical-use (PatientEuCore), on
    # the Patient the record's subject makes (=entry#patient).
    coded_text("Sex For Clinical Use", f"{PAT}/extension#sex/extension#value/valueCodeableConcept/text",
               attributes={"resourceType": "Patient", "meta/profile": f"{EU_BASE}patient-eu-core"},
               # the URLs ride with the value, so they join the extension it is written in
               also=[k(f"{PAT}/extension#sex/url", SEX_FOR_CLINICAL_USE),
                     k(f"{PAT}/extension#sex/extension#value/url", "value")]),
    # MAP body.supportingInformation.otherSupportingInformation -> ServiceRequest.supportingInfo, a list of references
    # to resources. The record holds the IRIs of other records, as one whitespace-delimited list value (PRD decision
    # 12): none is a resource in the Bundle, and the mapping does not split the list.
    V("Lab Report Supporting Information Other Supporting Information Reference", "-", "omit",
      reason="the guide puts other supporting information in ServiceRequest.supportingInfo, references to resources; "
             "the record holds the IRIs of other records as one list value, none of them a resource in the Bundle"),

    # ================================================================ the reference-model parts (absolute paths)
    # ---------------------------------------------------------------- whose entry each party makes
    # MAP header.subject -> Composition.subject: the Patient (BASE map-ehdspatient)
    C("subject", f"{B}/{PAT}", attributes={"resourceType": "Patient", "meta/profile": f"{EU_BASE}patient-eu-core"}),
    # MAP header.author -> Composition.author: a Practitioner (BASE map-ehdshealthprofessional: name, identifier,
    # address, telecom -> Practitioner)
    C("provider", f"{B}/=entry#author/=resource", attributes=PRACTITIONER),
    # MAP header.attestation.attester -> Composition.attester.party (slice validator, mode professional)
    C("performer", f"{B}/=entry#attester/=resource", within=["Attester Participation"], attributes=PRACTITIONER),
    # MAP header.custodian -> Composition.custodian: an Organization (BASE map-ehdsorganisation)
    C("performer", f"{B}/=entry#custodian/=resource", within=["Custodian Participation"],
      attributes={"resourceType": "Organization", "meta/profile": f"{EU_BASE}organization-eu-core"}),
    # MAP header.intendedRecipient -> Composition extension:informationRecipient. The model's intended recipient is a
    # person of the Patient cluster: a Patient of its own (the extension allows Patient)
    C("performer", f"{B}/=entry#recipient/=resource", within=["Intended Recipient Participation"],
      attributes={"resourceType": "Patient", "meta/profile": f"{EU_BASE}patient-eu-core"}),
    # MAP body.orderInformation.orderPlacer -> ServiceRequest.requester (ServiceRequest-eu-lab)
    C("performer", f"{B}/=entry#placer/=resource", within=["Order Placer Participation"], attributes=PRACTITIONER),
    # MAP header.legalAuthentication.legalAuthenticator -> Composition.attester.party (slice legalAuthenticator)
    C("committer", f"{B}/=entry#legal/=resource", attributes=PRACTITIONER),
    C("party-details", "."),

    # ---------------------------------------------------------------- what a party's details hold (any party)
    # BASE map-ehdshumanname: given, family, prefix, suffix, text, use one to one
    C("Human Name", "name"),
    V("Given Name (Person)", "given"),
    V("Surname (Person)", "family"),
    V("Name Prefix", "prefix"),
    V("Name Suffix", "suffix"),
    V("Name As Written", "text"),
    V("Name Use", "use", "binding", prefix="http://hl7.org/fhir/name-use"),
    # BASE map-ehdsaddress. Its street, house number and post box go in extensions of a line, which this mapping does
    # not write: the model's thoroughfare, premises and delivery service are lines of their own (declared).
    C("Address", "address"),
    V("Address (Line 1)", "+line"),
    V("Thoroughfare", "+line"),
    V("Premises Identifier", "+line"),
    V("Delivery Service", "+line"),
    V("City Name", "city"),
    V("Postal Code", "postalCode"),
    V("Address Use", "use", "binding", prefix="http://hl7.org/fhir/address-use"),
    V("Address Type", "type", "binding", prefix="http://hl7.org/fhir/address-type"),
    C("Country", "."),
    # BASE map-ehdsaddress: country -> Address.country (a name) or a country-code extension. Address.country is one
    # string: the ISO 3166 code is written there (FHIR R4 recommends the ISO 3166 code); the name has no second place.
    V("Country Code ISO 3166", "country"),
    V("Country Name", "-", "omit",
      reason="FHIR's Address.country is one string, which holds the record's ISO 3166 code; the country's name has no "
             "second place (HL7 Europe Base's country-code extension is not written here)"),
    # BASE map-ehdstelecom: type -> system, use and value one to one. An email beside a phone is a second ContactPoint.
    C("Telecom", "telecom"),
    V("Phone Number", "value"),
    V("Email Address", "../+telecom/value", also=[k("../+telecom/system", "email")]),
    V("Contact Method", "system", "binding", prefix="http://hl7.org/fhir/contact-point-system"),
    V("Contact Use", "use", "binding", prefix="http://hl7.org/fhir/contact-point-use"),
    # BASE map-ehdspatient / map-ehdshealthprofessional: identifier -> identifier. The issuer is a name: assigner.
    C("Person Identifier", "identifier"),
    V("Identifier Value", "value"),
    V("Issuing Authority", "assigner/display"),
    coded_type("Person Identifier Type"),
    # a driver's licence, passport or social security number: an identifier of its own, typed by the v2-0203 code the
    # model links the component to (a lookup)
    *[V(label, "../+identifier/value", also=[k("../+identifier/type/coding/system", V2_0203),
                                             {"to": "../+identifier/type/coding/code", "transform": "link",
                                              "system": V2_0203}])
      for label in ("Driver License Number", "Passport Number", "Social Security Number")],
    V("Country Code ISO 3166", "-", "omit", within=["Person Identifier"],
      reason="FHIR's Identifier has no element for the country that issued it"),
    C("Organization Identifier", "identifier"),
    coded_type("Organization Identifier Type"),
    # BASE map-ehdspatient: administrativeGender, dateOfBirth, deceased[x] one to one
    V("Administrative Gender", "gender", "binding", prefix="http://hl7.org/fhir/administrative-gender"),
    V("Date of Birth", "birthDate"),
    V("Deceased Indicator", "deceasedBoolean"),
    V("Deceased Date", "deceasedDateTime"),
    # BASE map-ehdsorganisation: name, type, partOf (here a name: partOf by display)
    V("Organization Name", "name"),
    coded_text("Organization Type", "type/text"),
    V("Organisation Part Of", "partOf/display"),

    # ---------------------------------------------------------------- each Participation's function, times
    # The function is fixed to the role name; the role is where the party goes. Each function places its party's
    # reference, so a record without the Participation writes no dangling reference.
    # Attester: Composition.attester, slice validator (mode professional), time from the Participation's start
    V("Participation Function (Attester)", f"{ACOMP}/attester#professional/mode", "code",
      table={"attester": "professional"},
      also=[k(f"{ACOMP}/attester#professional/party/reference", "{entry#attester}")]),
    E("start", f"{ACOMP}/attester#professional/time", within=["Attester Participation"]),
    E("end", "-", "omit", within=["Attester Participation"],
      reason="a Composition attester has one time, the Participation's start"),
    V("Participation Function (Custodian)", f"{ACOMP}/custodian/reference", "code",
      table={"custodian": "{entry#custodian}"}),
    *[E(t, "-", "omit", within=["Custodian Participation"], reason="FHIR's Composition.custodian has no time")
      for t in ("start", "end")],
    V("Participation Function (Intended Recipient)", f"{ACOMP}/extension#recipient/valueReference/reference", "code",
      table={"intended recipient": "{entry#recipient}"},
      also=[k(f"{ACOMP}/extension#recipient/url", INFORMATION_RECIPIENT)]),
    *[E(t, "-", "omit", within=["Intended Recipient Participation"],
        reason="the information-recipient extension is a reference alone, with no time") for t in ("start", "end")],
    # Order placer: the ServiceRequest the DiagnosticReport is based on (MAP body.serviceRequest -> basedOn). FHIR
    # requires a ServiceRequest's status and intent, which the record does not give (declared): status `unknown`
    # (request-status: the source does not say), intent `order` (the Participation is the order's placer).
    V("Participation Function (Order Placer)", f"{SR}/requester/reference", "code",
      table={"order placer": "{entry#placer}"},
      attributes={"resourceType": "ServiceRequest", "meta/profile": f"{LAB}ServiceRequest-eu-lab",
                  "status": "unknown", "intent": "order", "subject/reference": "{entry#patient}"},
      also=[k(f"{B}/{DR}/basedOn/reference", "{entry#sr}")]),
    # MAP body.orderInformation.orderDateAndTime -> ServiceRequest.authoredOn: when the placer placed the order
    E("start", f"{SR}/authoredOn", within=["Order Placer Participation"]),
    E("end", "-", "omit", within=["Order Placer Participation"],
      reason="a ServiceRequest has one authored time, the Participation's start"),

    # ---------------------------------------------------------------- the legal authentication (Attestation)
    # MAP header.legalAuthentication -> Composition.attester, slice legalAuthenticator: mode legal, time, party. A
    # pending attestation is not yet an authentication: the mode is written only when pending is false, so a pending
    # one leaves an attester without its mode, which HL7's validator reports.
    E("committed", f"{ACOMP}/attester#legal/time",
      also=[k(f"{ACOMP}/attester#legal/party/reference", "{entry#legal}")]),
    E("pending", f"{ACOMP}/attester#legal/mode", "code", table={"false": "legal"}, on_miss="omit"),
    V("Attestation Reason", "-", "omit", reason="FHIR's Composition.attester has no reason"),

    # ---------------------------------------------------------------- the workflow: the document's status
    # MAP header.status -> DiagnosticReport.status, aligned with Composition.status. The state's code is the one the
    # model binds it to (composition-status, a lookup); FHIR R4's diagnostic-report-status has the same four codes.
    # sdcreader 4.5.0 reads no definition for an ordinal's states (SDCStudio writes their rdfs:isDefinedBy without the
    # rdfs:Class it reads), so the code is copied from the schema into a table here (`states`): declared at run time.
    *[V(f"Clinical Document: {path} states", f"{ACOMP}/status", derive=states(f"{B}/{DR}/status"))
      for path in ("Main path", "amended entered in error", "final entered in error", "preliminary entered in error")],
]


# ================================================================ the 2026-11-21 revision
#: The library's requiredness and units revision (PRD decision 22) published a new Laboratory Report,
#: `rguwjl3y1d2cxmcv7vooocji`. Its members and parts are the first revision's, with fewer of them required (the
#: Attachment, the body, the event type, the period and the practice setting are optional; Patient's Date of Birth is
#: required), so the same rules map it.
REVISED = "rguwjl3y1d2cxmcv7vooocji"


def configure(ct_id):
    global DATE
    if ct_id == REVISED:
        DATE = "2026-11-21"
