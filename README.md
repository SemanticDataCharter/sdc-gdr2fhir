# sdc-gdr2fhir

Governed Data Records as HL7 FHIR R4 Bundles. A target mapper for
[sdc-mapper](https://github.com/SemanticDataCharter/sdc-mapper): the core validates the record, resolves every value
against its model and reports each one; this package says which FHIR resource and element each value goes in and
writes the Bundle. Outbound only. Apache 2.0.

**Status:** 4.0.6. Models so far, from the FAIR Data Demo:

| Model | ct_id | Resources | Rules |
|---|---|---|---|
| NHANES Participant 4.3.0 | `drjvqb171q9pqwcdq6nxxrr4` | Patient, Observation, QuestionnaireResponse | 112 |
| NHANES Medication 4.3.0 | `plc9gto1kzy244g1r2op257f` | Patient, MedicationStatement, QuestionnaireResponse | 21 |
| NHANES Participant 4.2.4 (retired) | `tp5pg0u4dasqarie0b3ujn2u` | Patient, Observation, QuestionnaireResponse | 112 |
| NHANES Participant 4.2.3 (retired) | `eehpfapwgvxtzdrofgstdcfs` | Patient, Observation, QuestionnaireResponse | 112 |
| NHANES Participant 4.2.0 (retired) | `xy8upneajsb8vdcmnve01g6g` | Patient, Observation, QuestionnaireResponse | 112 |
| NHANES Medication (retired) | `epbdfmvxc3gbh5f66hhb3o2m` | Patient, MedicationStatement, QuestionnaireResponse | 18 |

## Use

```python
from sdc_mapper import Engine, load_mapping
from sdc_gdr2fhir import FHIRMapper, mapping_path

result = Engine().map_record(xml, FHIRMapper(), load_mapping(mapping_path("tp5pg0u4dasqarie0b3ujn2u")))
result.files["Bundle.json"]     # a FHIR R4 Bundle of type collection
result.report                   # every value: lookup, declared or not representable; every Exceptional Value
```

Through sdc-mapper's CLI and MCP server the mapper is the target `fhir`.

## The target

**HL7 FHIR Release 4 (4.0.1)**, JSON. The specification is © HL7 and licensed under Creative Commons "No Rights
Reserved" (CC0); its terms allow redistribution and implementation-related products, so long as no one claims HL7's
endorsement and no altered specification is published as FHIR. HL7® and FHIR® are HL7's trademarks. This package
carries the FHIR R4 JSON schema unmodified (see `NOTICE`) and ships no terminology: LOINC, SNOMED CT, ICD-10-CM and NCI
Thesaurus codes appear only as the models bind them and the records carry them.

Every Bundle this package writes is valid against the FHIR R4 JSON schema, resource by resource and as a Bundle, or is
not written. The schema checks structure, types, required members and code patterns; it does not check FHIR's
invariants or terminology bindings. HL7's FHIR validator does (`validator_cli.jar`, which checks codes and displays
against HL7's terminology server): `tests/` runs it where Java and the validator are installed (`FHIR_VALIDATOR_JAR`).

**HL7's FHIR validator, 7.0.3, on all 400 sample Bundles (25 October 2026):** no errors in any Participant Bundle; 9
errors in 9 Medication Bundles, every one a reason code the record gives as ICD-10-CM that ICD-10-CM does not have
(`I51.9P`, `D75.9P`, `E11.P` and others: NHANES's own codes, carried as the record holds them). The warnings are best
practice, not conformance: no narrative, no performer, NCI Thesaurus codes the terminology server checks only in part,
the NHANES drug code system it does not know, and one UCUM annotation.

## Where values go

Each record is one Bundle of type `collection`, identified by the record's instance id
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

**What FHIR asks that the record does not say (declared).**

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
lookups, Exceptional Values and refused mappings are exercised.
