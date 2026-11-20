# sdc-gdr2fhir

Governed Data Records as HL7 FHIR R4 Bundles. A target mapper for
[sdc-mapper](https://github.com/SemanticDataCharter/sdc-mapper): the core validates the record, resolves every value
against its model and reports each one; this package says which FHIR resource and element each value goes in and
writes the Bundle. Outbound only. Apache 2.0.

**Status:** 4.1.0. Models so far, from the FAIR Data Demo:

| Model | ct_id | Resources | Rules |
|---|---|---|---|
| NHANES Participant 4.3.1 | `fafj69kdii37997sy7dpsz13` | Patient, Observation, QuestionnaireResponse | 112 |
| NHANES Participant 4.3.0 (retired) | `drjvqb171q9pqwcdq6nxxrr4` | Patient, Observation, QuestionnaireResponse | 112 |
| NHANES Medication 4.3.0 | `plc9gto1kzy244g1r2op257f` | Patient, MedicationStatement, QuestionnaireResponse | 21 |
| NHANES Participant 4.2.4 (retired) | `tp5pg0u4dasqarie0b3ujn2u` | Patient, Observation, QuestionnaireResponse | 112 |
| NHANES Participant 4.2.3 (retired) | `eehpfapwgvxtzdrofgstdcfs` | Patient, Observation, QuestionnaireResponse | 112 |
| NHANES Participant 4.2.0 (retired) | `xy8upneajsb8vdcmnve01g6g` | Patient, Observation, QuestionnaireResponse | 112 |
| NHANES Medication (retired) | `epbdfmvxc3gbh5f66hhb3o2m` | Patient, MedicationStatement, QuestionnaireResponse | 18 |

And the first SDCHealth model, mapped but failing HL7's validator with its guide on what the model lacks (see "SDCHealth Laboratory Report"
below):

| Model | ct_id | Resources | Rules |
|---|---|---|---|
| SDCHealth Laboratory Report | `zptekdommw56yiz9lqjy5dga` | Composition, DiagnosticReport, Patient, Practitioner, Organization, ServiceRequest (a document Bundle) | 100 |

## Use

```python
from sdc_mapper import Engine, load_mapping
from sdc_gdr2fhir import FHIRMapper, mapping_path

result = Engine().map_record(xml, FHIRMapper(), load_mapping(mapping_path("fafj69kdii37997sy7dpsz13")))
result.files["Bundle.json"]     # a FHIR R4 Bundle of the type the mapping gives (these: collection)
result.report                   # every value: lookup, declared or not representable; every Exceptional Value
```

`FHIRMapper()` writes FHIR R4; `FHIRMapper.for_mapping(mapping)` gives the mapper for the version the mapping's
`target.version` names, and a version this package does not ship is refused.

Through sdc-mapper's CLI and MCP server the mapper is the target `fhir`.

## The target

**HL7 FHIR Release 4 (4.0.1)**, JSON. The specification is © HL7 and licensed under Creative Commons "No Rights
Reserved" (CC0); its terms allow redistribution and implementation-related products, so long as no one claims HL7's
endorsement and no altered specification is published as FHIR. HL7® and FHIR® are HL7's trademarks. This package
carries the FHIR R4 JSON schema unmodified (see `NOTICE`) and ships no terminology: LOINC, SNOMED CT, ICD-10-CM and NCI
Thesaurus codes appear only as the models bind them and the records carry them.

R4 is the one version this package ships. The writer takes its schema from the mapping's `target.version` (the table
`VERSIONS` in `writer.py`), so another version would be a second schema there, not a second writer.

Every Bundle this package writes is valid against the FHIR R4 JSON schema, resource by resource and as a Bundle, or is
not written. The schema checks structure, types, required members and code patterns; it does not check FHIR's
invariants or terminology bindings. HL7's FHIR validator does (`validator_cli.jar`, which checks codes and displays
against HL7's terminology server): `tests/` runs it where Java and the validator are installed (`FHIR_VALIDATOR_JAR`).
The schema cannot check a profile either. `tests/` also runs the validator with an implementation guide's package
loaded (`-ig`, the package named by `FHIR_VALIDATOR_IG`, by default `hl7.fhir.eu.laboratory#2.1.0`), on a synthetic
document Bundle that claims only FHIR's own profiles: it checks that the path works, not that any mapping conforms to
the guide.

**HL7's FHIR validator, 7.0.3, on all 400 sample Bundles (25 October 2026):** no errors in any Participant Bundle; 9
errors in 9 Medication Bundles, every one a reason code the record gives as ICD-10-CM that ICD-10-CM does not have
(`I51.9P`, `D75.9P`, `E11.P` and others: NHANES's own codes, carried as the record holds them). The warnings are best
practice, not conformance: no narrative, no performer, NCI Thesaurus codes the terminology server checks only in part,
the NHANES drug code system it does not know, and one UCUM annotation.

## Mapping options

A mapping file is sdc-mapper's, whose schema is closed, so the options below are written in the Bundle rule's
`attributes` and in each resource's attributes. FHIR's own elements (`type`, `timestamp`, `meta/profile`) are written
as given. Keys starting with `@` are directives to the writer. It reads them and never writes them; no FHIR element name
starts with `@`.

- **Bundle type** (`type`): `collection`, the default when the mapping gives none, or `document`. The writer refuses
  any other type. For a `document` it requires what FHIR R4 asks of one and refuses a Bundle that breaks it:
  - bdl-9, an `identifier` with a system and a value: the mapping's own, or the record's instance id, which the writer
    adds as it does for a collection;
  - bdl-10, a `timestamp`: the mapping places it, since the writer does not make one up;
  - bdl-11, a Composition as the first entry.
- **Entry order** (`@first`): the resource types whose entries come first, in order, space-separated. The default is
  `Patient` for a collection and `Composition Patient` for a document. Every other entry keeps the record's order. For a
  document, `@first` must start with `Composition`.
- **Profiles** (`meta/profile` among a resource's attributes): the canonical URL of each profile the entry claims. A
  tag gives a second one (`meta/profile#1`, `meta/profile#2`). The JSON schema checks only the URL's form; whether an
  entry meets the profile is for HL7's validator with the guide's package (above).
- **Observation rules** (`@observation`): what the writer adds to or removes from an Observation beyond what the
  record says, space-separated. A rule applies only when the mapping names it:
  - `date-time-over-period`: an Observation dated both ways keeps the record's `effectiveDateTime`, and the
    `effectivePeriod` the mapping gave every Observation is dropped;
  - `blood-pressure-components`: a blood pressure panel (LOINC 85354-9) gets a systolic and a diastolic component, in
    that order, and the one the record lacks is written with `dataAbsentReason` `unknown`.

  The NHANES Participant mappings name both. The NHANES Medication mappings write no Observation and name neither.
- **FHIR version** (`target.version`): `R4`.

## Where values go

The NHANES mappings write each record as one Bundle of type `collection`, identified by the record's instance id
(`https://semanticdatacharter.com/ns/sdc4/instance`). Entry ids and `urn:uuid` fullUrls are derived from the instance
id, so the same record gives the same bytes.

- **Patient**: the respondent sequence number as an identifier, and the administrative gender.
- **Observation**: each blood pressure reading (the vital signs blood pressure panel, LOINC 85354-9, with systolic and
  diastolic as components, body site and status), the heart rate and each laboratory result, with the LOINC code the
  model binds and UCUM units; smoking status, with the model's LOINC code and the answer's LOINC answer code; each
  chronic condition indicator, with the SNOMED CT concept the model names as its subject and the Yes or No answer's
  LOINC answer code. A condition indicator is the answer to "has a doctor ever told you", so it is an Observation of
  the answer, not a Condition.
- **MedicationStatement**: the NHANES generic drug code and name, the ICD-10-CM reasons, and the status from "taken in
  the past month" (Yes is active, No not-taken).
- **QuestionnaireResponse**: every other survey answer, an item each, linkId the component's identifier and text its
  label; a Coding where the model binds each of the answer's values to its own code, else the answer as recorded.

**Lookup or declared.** Where the model binds the code FHIR needs (a laboratory result's LOINC code, a condition's
SNOMED CT subject, an answer's LOINC answer code, an administrative gender, an observation status), the code written
is the model's own and the value is a **lookup**; `tools/build_mapping.py` copies those bindings from the model into
the mapping file, and the mapper checks at run time that the code it writes is one the model binds. Which resource and
element a value goes in is **declared**, one mapping file per model.

**What FHIR asks that the record does not say (declared).** The first two are the NHANES Participant mappings'
`@observation` rules (above). No other mapping gets them unless it names them.

- An Observation's effective time. NHANES records carry no examination date, and FHIR R4's vital signs profiles require
  one, so every Observation is dated by the survey cycle it was collected in: `effectivePeriod` 2017-01-01 to
  2018-12-31 (NHANES 2017-2018). A record that carries its own date keeps it.
- Both readings of a blood pressure panel. The vital signs profile requires a systolic and a diastolic component; where
  the record holds only one, the other is written with `dataAbsentReason` `unknown`, since the record does not say why.
- A Quantity's `unit`, beside its UCUM `code`: the model's unit symbol (`mmHg` beside `mm[Hg]`).
- A Coding's `display` is the code system's, which this package does not ship, so it is never written. The model's
  label for a value is the CodeableConcept's `text`; a QuestionnaireResponse answer, which FHIR gives no text, is the
  code the model binds.
- A value the model defines by an agency's codebook rather than a code ("Not a citizen of the US", defined by the
  NHANES documentation's `DMDCITZN`) is never a Coding: a codebook page is not a code system. It is the
  CodeableConcept's `text` alone, or a QuestionnaireResponse `valueString`, while the same list's coded values stay
  Codings.

For the 200 sample records of each model:

| Model | lookup | declared | not representable |
|---|---|---|---|
| NHANES Participant 4.3.1 | 9,883 (73.5% of the data values) | 3,559 | 5,400 (provenance and audit) |
| NHANES Participant 4.3.0 | 9,883 (73.5% of the data values) | 3,559 | 5,400 (provenance and audit) |
| NHANES Medication 4.3.0 | 0 | 1,537 (100% of the data values) | 5,400 (provenance and audit) |
| NHANES Participant 4.2.4 | 10,215 (73.3% of the data values) | 3,719 | 5,400 (provenance and audit) |
| NHANES Participant 4.2.3 | 9,645 (66.5% of the data values) | 4,868 | 5,400 (provenance and audit) |
| NHANES Participant 4.2.0 | 9,093 (65.8% of the data values) | 4,733 | 5,400 (provenance and audit) |
| NHANES Medication | 0 | 1,591 (100% of the data values) | 5,400 (provenance and audit) |

Each sample has 200 records. The 4.3.0 samples are drawn to include Exceptional Values and, for medication, NHANES
prevention codes; their Exceptional Values are counted apart from the data values: 53 preserved in the participant
sample (13 ASKR, 40 ASKU) and 46 in the medication sample (36 ASKU, 6 UNK, 4 ASKR), each written as FHIR's
data-absent-reason.

The medication model binds its ICD-10-CM and drug code components to their code systems, not each value to a code,
so its codes are written as the record holds them: declared.

## SDCHealth Laboratory Report

The mapping targets the HL7 Europe Laboratory Report guide, **version 2.1.0, package `hl7.fhir.eu.laboratory#2.1.0`**
(FHIR 4.0.1, https://hl7.eu/fhir/laboratory/2.1.0/).
- **What it writes:** a `document` Bundle. Its entries claim the guide's Bundle, Composition, DiagnosticReport and
  ServiceRequest profiles, and HL7 Europe Base 2.0.1's Patient, Practitioner and Organization profiles.
- **Where each target comes from:** the element's Xt-EHR 1.0.0 link and the guide's map of the Xt-EHR Laboratory
  Report model (`map-ehdslaboratoryreport.html`). Where the lab map leaves an element to HL7 Europe Base, Base's maps
  decide. The spec cites the map for each rule (`tools/specs/sdchealth_lab_report.py`).

**HL7's FHIR validator 7.0.6, `-version 4.0.1 -ig hl7.fhir.eu.laboratory#2.1.0`, on the 15 sample Bundles
(20 November 2026): every Bundle fails, with 75 errors in all, 5 in each.** All of them come from what the model does
not hold. The Bundles pass the FHIR R4 JSON schema.

| Errors | What the validator reports | Cause |
|---|---|---|
| 45 | `Composition.section`: minimum 1, found 0. The DiagnosticReport's link to the Composition then matches neither Composition-eu-lab nor R5's Composition profile (15 each). | The model has no results, so no section (below). Validating the Composition alone against R5's profile gives only the section error. |
| 30 | `ServiceRequest.identifier`: minimum 1, found 0. `DiagnosticReport.basedOn` then matches no ServiceRequest-eu-lab (15 each). | The model holds no order identifier. |

Warnings: no narrative in any resource (dom-6), v2-0203 `NI` is not in R4's extensible identifier-type value set, and
the attachment's content could not be checked (its URL is a URN).

The first run found 124 errors. The 49 on this side are fixed:
- **The recipient's birth date** (30 errors): the samples gave none, and PatientEuCore requires one. They do now.
- **The attachment URLs** (15 errors): the validator refuses `example.org`. The samples now use URNs (`urn:uuid:`).
- **The ASKU on sex for clinical use** (4 errors): the extension's CodeableConcept had data-absent-reason only on its
  text, and the value set's binding is required. An Exceptional Value on the text of an extension's CodeableConcept
  now also writes the coding data-absent-reason `unknown`, which the value set includes and which subsumes
  asked-unknown, not-asked, asked-declined and temp-unknown. The extension on the text keeps the exact code.

**Needs unreleased versions.** The mapping says `reference_model: true`: it reads the record's reference-model parts
as well as its data cluster. Those are the subject, the provider, the four Participations, the Attestation and the
workflow. This needs **sdcreader 4.5.0 and sdc-mapper 4.4.0**, which are not released.

**The samples** (`samples/sdchealth-lab-report/`) are 15 synthetic records: no person, professional, organisation or
report in them is real.
- Each validates against the model's XSD 1.1 schema.
- They carry five Exceptional Values: ASKU, NAV, UNK and ASKR (twice: a patient's birth date, as subject and as
  recipient).
- Every LOINC and SNOMED CT code in them was looked up on HL7's terminology server, not written from memory, and is
  used only where the model allows a code of that system. The sample README lists them.

**Value counts** for the 15 samples (1,898 values):

| lookup | declared | not representable | Exceptional Values |
|---|---|---|---|
| 359 | 1,380 | 154 | 5, all preserved (ASKU, NAV, UNK, ASKR twice) |

The lookups are the codes the model binds: administrative gender; name, address and contact uses; the contact
system; v2-0203 identifier types; organization type; sex for clinical use. Everything else written is declared.

**Where the values go.**
- **Composition:**
  - title, date, status;
  - identifier (the issuer as `assigner.display`);
  - type: the record's LOINC code, also the DiagnosticReport's code (the guide's `dr-comp-type`);
  - version (extension);
  - event code (the document event type, SNOMED CT) and event period;
  - subject (the Patient) and author (a Practitioner);
  - attester twice: mode `professional` (the Attester Participation, at its start) and mode `legal` (the Attestation,
    at its `committed` time);
  - custodian (the Organization);
  - the information recipient (extension);
  - the link to the DiagnosticReport (extension).
- **DiagnosticReport:**
  - identifier, code, subject and status, as the Composition's;
  - `issued` and `effectivePeriod`;
  - the presented form: title, URL, media type, size;
  - `conclusion`: the result comments;
  - `basedOn` the ServiceRequest;
  - the link to the Composition (extension).
- **Patient** (the subject): name, identifiers, gender, birth date, deceased, address, telecom, and the sex for
  clinical use (PatientEuCore's extension).
- **Practitioner**, one per party: author, attester, legal authenticator, order placer. Each holds name, identifiers,
  address and telecom.
- **Organization** (the custodian): name, type, identifier, address, telecom, part-of.
- **Patient** (the intended recipient): the model's intended recipient is a person of the Patient cluster, so it is
  a Patient entry of its own.
- **ServiceRequest:** the order placer as `requester`, the Participation's start as `authoredOn`.
- **Bundle:** `timestamp` from the authored date, and the record's instance id as identifier.

Several entries share a resource type, so each is tagged in the mapping (`entry#author`) and referenced by its tag
(`{entry#author}`, new in the writer).

**Declared choices.**
- **ServiceRequest status and intent:** FHIR requires both and the record gives neither. Status is `unknown` (the
  source does not say) and intent is `order` (the Participation names the order's placer).
- **Document event type:** it is coded in SNOMED CT, and the guide's study-type category is bound (required) to LOINC
  codes. So it goes in `Composition.event.code`, as HL7 Europe Base's document map allows for R4.
- **Result comments:** they go in `DiagnosticReport.conclusion`, which the guide's map allows. A section's text is
  XHTML narrative, which this mapping does not write from plain text.
- **Bundle identifier:** the record's identifier has no system (its issuer is a name), and bdl-9 needs one. The Bundle
  carries the record's instance id instead.
- **Document status:** the workflow's state is the Composition's status, and the same code is the DiagnosticReport's
  status (FHIR R4's diagnostic-report-status has all four codes). sdcreader 4.5.0 reads no definition for an ordinal's
  states: SDCStudio writes them without the `rdfs:Class` it reads. So the codes are copied from the model's schema
  into a table in the mapping, and the value is declared, not a lookup.
- **Legal authentication:** the legal attester's mode is written only when the Attestation is not pending. A pending
  one leaves an attester without its mode, which HL7's validator reports.
- **Addresses:** a thoroughfare, premises identifier or delivery service is a line of its own. HL7 Europe Base puts
  street parts in line extensions, which are not written here. The country is the ISO 3166 code in `Address.country`.
- **Email:** an email beside a phone number is a second ContactPoint.

**What FHIR or the guide cannot hold** (omitted, each with its reason in the mapping; 154 values in the samples):
- the practice setting: the guide has no element for it, and its specialty category is bound to LOINC codes;
- a Participation's second time: the custodian and the information recipient have no time, and an attester and a
  ServiceRequest have one;
- the Attestation's reason: `Composition.attester` has none;
- other supporting information: the guide puts it in `ServiceRequest.supportingInfo`, which takes references to
  resources, and the record holds IRIs of other records;
- the attachment's data: the model gives the content by URI, and `Attachment.data` is the bytes;
- the Parent Record Identifier (the record this one belongs to): a Composition has no such element;
- a country's name beside its code: `Address.country` holds one string;
- an identifier's issuing country: FHIR's Identifier has no such element.

**What the guide asks for that the model does not give.**
- **No results, specimens or body structures.** So the Bundle has no Observation, Specimen or BodyStructure. It also
  has none of the Composition sections the guide requires (at least one, each with a title, a code and narrative).
- **A Health Professional has no role, specialty or organisation**, so the Bundle has no PractitionerRole.
- **The intended recipient can only be a patient.**
- **No order identifier.** ServiceRequest-eu-lab requires one.
- **A patient's birth date is optional.** PatientEuCore requires one, so a record without it fails the guide.
- **A record dated by day alone** cannot make a document Bundle: the Bundle's timestamp is an instant, with a time
  and a zone.

## Exceptional Values: every one preserved

FHIR is the target that can say what an Exceptional Value says. Where the data-absent-reason code system
(`http://terminology.hl7.org/CodeSystem/data-absent-reason`) has the concept, an Observation's (or component's) value
is replaced by `dataAbsentReason`, and any other element carries the data-absent-reason extension. The null flavors
data-absent-reason has no concept for are written exactly from v3 NullFlavor
(`http://terminology.hl7.org/CodeSystem/v3-NullFlavor`), as the `iso21090-nullFlavor` extension on the element or a v3
NullFlavor coding of `dataAbsentReason` (whose binding is extensible). v3 NullFlavor has no Asked and Refused;
data-absent-reason does.

| ISO 21090 | Written as | Class |
|---|---|---|
| UNK | data-absent-reason `unknown` | preserved |
| ASKU | data-absent-reason `asked-unknown` | preserved |
| NAV | data-absent-reason `temp-unknown` | preserved |
| NASK | data-absent-reason `not-asked` | preserved |
| ASKR | data-absent-reason `asked-declined` | preserved |
| MSK | data-absent-reason `masked` | preserved |
| NA | data-absent-reason `not-applicable` | preserved |
| NINF | data-absent-reason `negative-infinity` | preserved |
| PINF | data-absent-reason `positive-infinity` | preserved |
| NI, INV, DER, OTH, UNC, QS, TRC | v3 NullFlavor, the same code | preserved |

A mapping file cannot change this table.

## What FHIR cannot hold here

- **The record's provenance and audit.** FHIR's Provenance and AuditEvent require a recorded instant with a time
  zone, and the FAIR Data Demo records' times carry none; the PROV and audit values are reported as not representable,
  with that reason.
- **Times without a time zone.** FHIR's dateTime requires a time zone with a time; an observation's date and time is
  written as its date.
- Validity windows and recording times (act, vtb, vte, tr), and the definitions each component is bound to beyond the
  codes written.

## Tests

```
pip install -e ".[dev]"
python -m pytest
```

Every sample record is mapped and each resource validated against the FHIR R4 JSON schema; Bundles are byte-stable;
lookups, Exceptional Values and refused mappings are exercised. The tests also cover document Bundles (built from a
synthetic set of values, and from an NHANES mapping edited to write a document), profiles, the writer's directives and
the FHIR version. The HL7 validator tests are marked `validator` and are skipped without Java and
`FHIR_VALIDATOR_JAR`. The SDCHealth Laboratory Report tests (`tests/test_lab_report.py`) cover the following:
- the samples against the model's XSD 1.1 schema;
- every sample to a document Bundle that passes the FHIR R4 schema, byte-stable;
- every reference resolving to an entry, and each party in its place;
- the guide's identifier and type agreements;
- the Exceptional Values and the value counts.

HL7's validator with the guide's package is a `validator` test, skipped without Java and `FHIR_VALIDATOR_JAR`.
