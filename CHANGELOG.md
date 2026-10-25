# Changelog

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
