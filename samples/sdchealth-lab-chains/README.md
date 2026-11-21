# SDCHealth Laboratory Report chains: synthetic samples

**Synthetic.** Nothing in these records is real: no person, health professional, organisation, order, specimen or
result.

Each `chain-NN/` holds:
- one Laboratory Report sample, the parent (`../sdchealth-lab-report/records/labrep0N…`, named in `chain.json`);
- the six records chained to it (library decision 12), all written by `python tools/make_lab_chain_samples.py`:
  - an Order Information;
  - a Specimen;
  - a Service Request;
  - three Laboratory Observations.

Each child is the catalog's instance template for its model, filled in, and validated against that model's XSD 1.1
schema before it is written.

| Model | ct_id | Package | Records |
|---|---|---|---|
| Order Information | `l6m7g3jk6y6tvnisd35l16pw` | `../sdchealth-order-information/` | 5 |
| Specimen | `qws8pcquvnqc55okidyqll83` | `../sdchealth-specimen/` | 5 |
| Service Request | `nz971o74u4kuk3ifcxc2llq2` | `../sdchealth-service-request/` | 5 |
| Laboratory Observation | `d5b3007cqbmejx7xgs7i484r` | `../sdchealth-lab-observation/` | 15 |

**How they join.**
- **By parent:** Order Information, Service Request and Laboratory Observation carry Parent Record Identifier. It
  holds the report's Record Identifier (`LR-2026-100N`).
- **By reference:** the Specimen carries no parent; the Service Request and the observations name it. The observations
  also name the Service Request, and the Specimen names the Service Request as its request.
  - A reference is the record's IRI, `urn:sdc4:record:<instance_id>`.
  - The library says only "the IRI of the referenced record", so this form is the samples' choice. sdc-gdr2fhir
    matches any IRI that ends with the record's instance id.
- **Shared parties:** each child's subject is the report's patient (the report's details, copied), and its author is
  the report's author.

**Exceptional Values.** The sodium result of chain 02 is Not Available (NAV) and its status is preliminary. The model
also requires a data absent reason (`temp-unknown`) and an interpretation (`IND`) for it, so neither can be an
Exceptional Value.

**What the models make the samples carry** (library findings, in the main README):
- Every quantity's unit is the text "UCUM Units". The models enumerate that one value, so a result can't say mg/dL.
- Every result has a data absent reason, even when it has a value. The model requires one, and a required component
  takes no Exceptional Value, so a result with a value has `not-applicable`.
- Every result names a test kit (the IRI of a record outside the chain) and a calibrator, which the model requires.

## Codes

Each code was looked up on HL7's terminology server (`tx.fhir.org/r4`) on 20 November 2026, and every one was
active. Each is used only where the model allows a code of that system.

| System | Code | Display (from the lookup) | Where |
|---|---|---|---|
| LOINC 2.83 | 2345-7 | Glucose [Mass/volume] in Serum or Plasma | Result Code (LOINC) |
| LOINC 2.83 | 2160-0 | Creatinine [Mass/volume] in Serum or Plasma | Result Code (LOINC) |
| LOINC 2.83 | 2951-2 | Sodium [Moles/volume] in Serum or Plasma | Result Code (LOINC) |
| LOINC 2.83 | 24323-8 | Comprehensive metabolic 2000 panel - Serum or Plasma | Order (LOINC) |
| SNOMED CT International 20260701 | 119364003 | Serum specimen | Specimen Type (SNOMED CT) |
| SNOMED CT International 20260701 | 73211009 | Diabetes mellitus | Order Reason (SNOMED CT) |
| SNOMED CT International 20260701 | 258026004 | Enzyme method | Observation Method (SNOMED CT) |
| SNOMED CT International 20260701 | 703445001 | Ion selective electrode measurement | Observation Method (SNOMED CT) |

The two methods are also in the guide's technique value set, lab-technique-eu-lab. The UCUM units the results are in
(mg/dL and mmol/L, both valid UCUM) were checked too, but the models can't record them.

The other coded values are the models' own enumerations:
- observation, specimen and request status;
- request priority;
- data absent reason;
- the v3 observation interpretation.
