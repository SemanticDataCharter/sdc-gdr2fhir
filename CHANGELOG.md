# Changelog

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
