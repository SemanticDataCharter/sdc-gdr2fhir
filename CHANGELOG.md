# Changelog

## Unreleased (planned 4.2.0)

The first SDCHealth mapping: the Laboratory Report, as a FHIR R4 document Bundle following the HL7 Europe Laboratory
Report guide 2.1.0 (`hl7.fhir.eu.laboratory#2.1.0`). HL7's FHIR validator 7.0.6 with the guide fails every sample
Bundle, with 5 errors each, all from what the model does not hold: a Composition section and an order identifier.
Needs sdcreader 4.5.0 and sdc-mapper 4.4.0 (unreleased), so the `sdc-mapper` pin must become `>=4.4` at release.

- **SDCHealth Laboratory Report** (`zptekdommw56yiz9lqjy5dga`): its mapping (100 rules, `reference_model: true`) and
  15 synthetic sample records, valid against the model's XSD 1.1 schema. Every code in them was looked up.
  - The Bundle holds a Composition, a DiagnosticReport, the Patient, a Practitioner for each professional party, the
    custodian Organization, the intended recipient and a ServiceRequest for the order placer.
  - For the 15 samples: 359 lookup, 1,380 declared, 154 not representable, and 5 Exceptional Values, all preserved.
  - The README's new section lists the declared choices, what FHIR or the guide cannot hold, and what the guide asks
    that the model lacks.
- **Writer: references by tag.** `{entry#author}` is the fullUrl of the entry tagged `entry#author`, for a Bundle
  with several entries of one type. `{Patient}` still names the one Patient. The NHANES output does not change.
- **An unknown extension value keeps a code.** An Exceptional Value on the text of an extension's CodeableConcept
  (data-absent-reason `unknown` or a concept under it) also writes the coding data-absent-reason `unknown`, so a
  required binding that includes it is met (Sex Parameter for Clinical Use). The extension on the text keeps the
  exact code. The NHANES output does not change.
- **`tools/build_mapping.py`:**
  - It walks the model's data cluster (the one `ms-` element its complex type names).
  - A spec may set `REFERENCE_MODEL` and `PARTIES`, and name the reference-model parts by label, by the reference
    model's element names, or with `element` rules. The coverage check then includes every part's values.
  - It reads an ordinal's state definitions, written without `rdfs:Class`.
  - The NHANES mapping files it regenerates are byte-identical.
- `tools/make_lab_report_samples.py` writes the Laboratory Report samples from the catalog's instance template.

## 4.1.0 (2026-11-19)

Engine changes so that a mapping can ask for the FHIR output an implementation guide expects: document Bundles,
declared profiles, writer rules that apply only where a mapping names them, and the FHIR version taken from the mapping.
The NHANES output does not change: every sample Bundle (1,400, seven models) is byte-identical to 4.0.7's. No new
mapping and no new model.

- **Document Bundles.** The Bundle rule's `type` may be `document` (`collection` stays the default, and is written
  when a mapping gives no type; any other type is refused). For a document the writer requires an identifier with a
  system and a value (bdl-9; the record's instance id unless the mapping gives its own), a timestamp the mapping places
  (bdl-10) and a Composition as the first entry (bdl-11), and refuses a Bundle that breaks any of them.
- **Entry order** is the directive `@first` (the resource types written first, in order). Defaults: `Patient` for a
  collection, as before; `Composition Patient` for a document.
- **Profiles.** A resource's attributes may declare `meta/profile` (a second one by tag, `meta/profile#2`). A new
  test, marked `validator`, runs HL7's FHIR validator with an implementation guide's package (`-ig`, from
  `FHIR_VALIDATOR_IG`, default `hl7.fhir.eu.laboratory#2.1.0`) on a synthetic document Bundle that claims only FHIR's
  own profiles. Like the existing validator test, it is skipped without Java and `FHIR_VALIDATOR_JAR`.
- **NHANES rules out of the writer.** The survey-cycle dating rule (drop `effectivePeriod` beside
  `effectiveDateTime`) and the vital signs blood pressure fill now apply only where a mapping names them, in the
  directive `@observation` (`date-time-over-period`, `blood-pressure-components`). The five NHANES Participant mapping
  files name both: one line each, the Bundle rule, so their SHA-256 changes and their mapping version stays 1. The
  medication mappings are unchanged. `tools/specs/common.py` `bundle()` takes the directive.
- **FHIR version from the mapping.** The writer's schema comes from a table of versions (`writer.VERSIONS`, R4 only)
  chosen by the mapping's `target.version`. `FHIRMapper(target_version="R4")` and `FHIRMapper.for_mapping(mapping)`
  refuse a version not shipped, and `map()` refuses a mapping for another version. No R5.
- The mapping options are described in the README's new "Mapping options" section. Directives start with `@`, sit
  among the Bundle rule's `attributes` (sdc-mapper's mapping schema is closed) and are never written; an unknown one is
  refused.

## 4.0.7 (2026-10-27)

- **FAIR Data Demo 4.3.1:** NHANES Participant 4.3.1 (`fafj69kdii37997sy7dpsz13`): its mapping and a sample of the
  same 200 participants as the 4.3.0 sample. 4.3.1's four NIH CDE answers carry their compound concept as
  `dcterms:subject` parts, with no exact-match claim (NIH CDE library R-2026-10-27). This mapper writes those answers as
  QuestionnaireResponse items whose codes are the answers' value bindings, never the components' concept links, so the
  mapping is the 4.3.0 one with new identifiers and the Bundles are the 4.3.0 ones apart from identifiers. HL7's FHIR
  validator (7.0.3) on the 200 new Bundles: no errors. The 4.3.0 mapping stays, for records made on that model.

## 4.0.6 (2026-10-27)

The FAIR Data Demo's 4.3.0 models: **NHANES Participant 4.3.0** (`drjvqb171q9pqwcdq6nxxrr4`) and **NHANES Medication
4.3.0** (`plc9gto1kzy244g1r2op257f`), their mappings and a seeded 200-record sample of each, drawn to include Exceptional
Values and prevention codes. The earlier mappings stay, for records made on those models.

- **A refused or unknown answer is data-absent-reason, never a value.** FAIR 4.3.0 carries NHANES's refused and
  don't-know answers as ASKR and ASKU, and the medication file's unknowns as UNK, in place of the value. The mapper
  writes each as FHIR does: `dataAbsentReason` on an Observation value (asked-declined, asked-unknown, unknown), the
  data-absent-reason extension on any other element (a QuestionnaireResponse answer's `_valueString`, a quantity's
  `_value`, a reason's `_code`), with no value beside it. No code change: the 4.0.0 mapper already did this; the tests
  now hold it on records that have them.
- **NHANES prevention codes under NHANES's own system.** `I21.P` (prevent heart attack) is not ICD-10-CM. A Prevention
  Reason (NHANES) is a reasonCode Coding whose system is the RXQ_RX_J documentation
  (`https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/RXQ_RX_J.htm`), copied from the model's own
  `skos:exactMatch` (`tools/specs/nhanes_medication_430.py`), with NHANES's description as the text; never
  `http://hl7.org/fhir/sid/icd-10-cm`. The 4.0.x medication Bundles carried those codes as ICD-10-CM and HL7's
  validator reported them; on the 4.3.0 sample there are none.
- HL7's FHIR validator 7.0.3 on the 400 new Bundles: no errors. The NHANES system is a warning, "A definition for
  CodeSystem ... could not be found, so the code cannot be validated" (52), as for any code system the terminology
  server does not hold.

## 4.0.5 (2026-10-26)

Maps the FAIR Data Demo's NHANES Participant 4.2.4 (`tp5pg0u4dasqarie0b3ujn2u`), the revision of 4.2.3
(`eehpfapwgvxtzdrofgstdcfs`) whose value bindings name codes their terminologies confirm. FAIR Data Demo erratum
E-2026-10-03 (its `SOURCE-ERRATA.md`): 24 of its records named codes for something else (Mexican American as NCIt
C67175, a drug regimen; every level of the difficulty scale as Unknown; both pregnancy-at-exam answers as one code), and
the SI total cholesterol carried the mg/dL LOINC code.

- **New mapping file** `nhanes_participant-tp5pg0u4dasqarie0b3ujn2u.yaml` (112 rules) and **sample**
  `samples/nhanes-participant-4.2.4/` (200 of the demo's 9,254 records, seed 424). Same participant, 4.2.3 then 4.2.4:
  Mexican American `C67175` then `C67114`; "Not pregnant at exam" text then `C82475`; "Much difficulty" text then
  `C121740`; SI cholesterol LOINC `2093-3` then `14647-2`.
- **A value the model defines by a codebook is never a Coding.** E-2026-10-03 defines a value with no exact concept by
  the agency's codebook (`DEMO_J.htm#DMDCITZN`). Such a value is written as text (the CodeableConcept's `text`, or a
  QuestionnaireResponse `valueString`), and the list's other values keep their Codings: before, one uncoded value made
  the whole list text. A main rule that writes nothing is stood in for by an `also` that writes the value as another
  value[x] of the same element.
- HL7's FHIR validator (7.0.3) on the 200 Bundles: no errors. The NCI Thesaurus codes it reports as unknown are in its
  partial copy of the NCI Thesaurus; each was looked up in NCI's EVS (the demo's `build/verified-codes.json`).
- The 4.2.3 and 4.2.0 mapping files and samples stay, for records made on those (retired) models. Tests run over all
  four models.

## 4.0.4 (2026-10-25)

Maps the FAIR Data Demo's NHANES Participant 4.2.3 (`eehpfapwgvxtzdrofgstdcfs`), the revision of 4.2.0
(`xy8upneajsb8vdcmnve01g6g`) that composes the NIH CDE library's correction of "Are you pregnant now?"
(`zmpqfc6tb0o2hgu8qs6lj8tp`). Source erratum E-2026-10-01 (FAIR Data Demo 4.2.3; the NIH CDE library's
`SOURCE-ERRATA.md`): the NIH CDE Repository's record for Current Pregnancy Indicator (`LiUWCWluP`) binds each answer to
the next value's LOINC code, and the 4.2.0 model carried that binding.

- **New mapping file** `nhanes_participant-eehpfapwgvxtzdrofgstdcfs.yaml` (112 rules), built by
  `tools/build_mapping.py` from the same spec as 4.2.0's. A QuestionnaireResponse answer to the pregnancy question is
  now the answer's own code: Yes `LA15173-0`, No `LA26683-5`, Unknown `LA4489-6` (4.2.0: `LA26683-5`, `LA4489-6`,
  `LA15173-0`).
- **New sample** `samples/nhanes-participant-4.2.3/`: the model's schema and 200 records drawn from the demo's 9,254
  (seed 423). HL7's FHIR validator (7.0.3): no errors in the 200 Bundles.
- The 4.2.0 mapping file and sample stay: records made on 4.2.0 remain valid against it and still map.
- Tests run over all three models, with one for the pregnancy codes.

## 4.0.3 (2026-10-25)

What HL7's FHIR validator (7.0.3) found in 4.0.2's output, fixed. On the 400 sample Bundles its errors fall from 2,164
(196 Participant and 10 Medication Bundles) to 9 (the NHANES reason codes ICD-10-CM does not have, carried as the
record holds them). Every value keeps its coverage class.

- **No `Coding.display` from the model's labels.** A display is the code system's ("Pulse regular", not "Regular"); the
  label is now the CodeableConcept's `text`, and a QuestionnaireResponse answer is the code the model binds.
- **The vital signs profiles.** Every Observation is dated by the survey cycle (`effectivePeriod` 2017-01-01 to
  2018-12-31, declared; a record's own date wins); a Quantity carries its `unit` beside its UCUM `code`; a blood
  pressure panel the record has one reading of gets the other with `dataAbsentReason` `unknown`.
- The validator's own test runs where Java is available, and passes.

## 4.0.2 (2026-10-25)

Uses sdc-mapper 4.3.0's code reading in place of this package's own; no change to any output (all 400 sample
Bundles byte-identical, every value's class the same).

- **Codes:** `codes.coding()` reads an IRI with `sdc_mapper.codes.code_of`, then keeps FHIR's one rule: a Coding is a
  concept of LOINC, SNOMED CT or the NCI Thesaurus, or an entry of an HL7 code system (the core also reads a variable
  page's or an ontology term's `#fragment`, which no Coding names). The package's own LOINC, SNOMED CT, NCIt and
  fragment patterns are gone. `codes.model_codes()` replaces `bound_codes()`.
- **Mapping files:** where the model binds a code, the mapping file now says so: the code of the concept a component
  links to is a `link` rule (47 in the Participant mapping), an answer's code a `binding` rule (41), where 4.0.1 copied
  each code in as a constant or a table at authoring time. A value placed by either is a lookup
  (`sdc_mapper.LOOKUP_TRANSFORMS`).
- **Joins:** `=name` writes are resolved shallowest first (`sdc_mapper.join_depth`).
- Requires sdc-mapper 4.3.

## 4.0.1 (2026-10-25)

Rebuilt with the release job's pip pinned by hash: CI and the release workflow install pip 26.2.2 from a hash-pinned
wheel before anything else is fetched (the eMudhra/emSign CA compromise: pip before 26.2.2 trusts the compromised root
through its vendored certifi). No change to the package.

## 4.0.0 (2026-10-25)

The FHIR mapper of the sdc-mapper line: Governed Data Records as HL7 FHIR R4 Bundles.

- **The writer**, typed and checked by the FHIR R4 JSON schema (shipped unmodified): arrays where FHIR repeats an
  element, numbers and booleans from the record's own text, entries with ids and `urn:uuid` fullUrls derived from the
  record's instance id, references to the Bundle's Patient, every resource and the Bundle validated.
- **The NHANES Participant and NHANES Medication mappings** for the FAIR Data Demo's models: a Patient, an Observation
  per blood pressure reading (the vital signs panel), heart rate and laboratory result with the LOINC code the model
  binds, Observations of smoking status and of each chronic condition indicator, a MedicationStatement with its
  ICD-10-CM reasons, and one QuestionnaireResponse for the other survey answers. All 400 sample records map to
  conformant Bundles. Written by `tools/build_mapping.py`, which copies what the model binds into the mapping file.
- **Every ISO 21090 null flavor is preserved**: an Observation's value as `dataAbsentReason`, any other element with the
  data-absent-reason extension, and the codes data-absent-reason has no concept for with the iso21090-nullFlavor
  extension and their exact v3 NullFlavor code.
