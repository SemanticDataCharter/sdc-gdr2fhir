# SDCHealth Laboratory Report: synthetic samples

**Synthetic.** These 15 records are made up. No person, health professional, organisation, identifier, address or
report in them is real.

- **Model:** SDCHealth Laboratory Report, ct_id `zptekdommw56yiz9lqjy5dga`, published on SDCStudio (project SDCHealth).
  The schema is `dm-zptekdommw56yiz9lqjy5dga.xsd`, SHA-256 `150c6c74c3760496ff172141d596a78b75e69753ec8850f3872d1ba00a2a3ec6`.
- **`template/`** is the instance template the catalog publishes with the model (its `xml` artifact).
- **`records/`** are written by `python tools/make_lab_report_samples.py`. The script fills the template and validates
  each record against the model's XSD 1.1 schema (sdcvalidator's `build_xsd11_schema`) before writing it.
- **The attachment URLs** are URNs (`urn:uuid:`), not web addresses: HL7's validator refuses example URLs, and a
  made-up host could be someone's.
- **The intended recipient** is the patient, with the same birth date (PatientEuCore requires one).
- **Exceptional Values:**
  - ASKU on a sex for clinical use;
  - NAV on a result comment;
  - UNK on a document event type code;
  - ASKR on a patient's date of birth (the same person as subject and as intended recipient).

## Codes

Each code was looked up on HL7's terminology server (`tx.fhir.org/r4`, `CodeSystem/$lookup`) on 20 November 2026, and
every one was active. Each is used only where the model allows a code of that system.

| System | Code | Display (from the lookup) | Where |
|---|---|---|---|
| LOINC 2.83 | 11502-2 | Laboratory report | Document Type Code (LOINC) |
| SNOMED CT International 20260701 | 15220000 | Laboratory test | Document Event Type Code (SNOMED CT) |
| SNOMED CT International 20260701 | 394915009 | General pathology (specialty) | Practice Setting Code (SNOMED CT) |
| SNOMED CT International 20260701 | 394596001 | Chemical pathology | Practice Setting Code (SNOMED CT) |
| SNOMED CT International 20260701 | 408454008 | Clinical microbiology | Practice Setting Code (SNOMED CT) |
| SNOMED CT International 20260701 | 394595002 | Pathology | Practice Setting Code (SNOMED CT) |

The other coded values are the model's own enumerations:
- sex for clinical use;
- administrative gender;
- address, name and contact use;
- identifier and organisation types;
- ISO 3166 country codes;
- media type;
- the workflow's composition-status states.
