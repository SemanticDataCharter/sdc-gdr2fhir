# SDCHealth Laboratory Report chains, 2026-11-21 revision: synthetic samples

**Synthetic.** Nothing in these records is real: no person, health professional, organisation, order, specimen or
result.

The chains of `../sdchealth-lab-chains/`, made on the library's 2026-11-21 revision of the Laboratory models (PRD
decision 22), written by `python tools/make_lab_chain_samples.py --revised`. Each `chain-NN/` holds:
- one revised Laboratory Report sample, the parent (`../sdchealth-lab-report-2026-11-21/records/labrev0N…`, named in
  `chain.json`);
- the ten records chained to it: an Order Information, a Specimen, its Specimen Collection, a Service Request, three
  Laboratory Observations and a Reference Range for each.

Each child is the catalog's instance template for its model, filled in, and validated against that model's XSD 1.1
schema before it is written.

| Model | ct_id | Package | Records |
|---|---|---|---|
| Order Information | `zfh7quqpqxk176c2j4gdestb` | `../sdchealth-order-information-2026-11-21/` | 5 |
| Specimen | `dkzoy1j9aw2u7i7x5lseo7ro` | `../sdchealth-specimen-2026-11-21/` | 5 |
| Specimen Collection | `idprzkpm6sdqgib5w5wzc3ys` | `../sdchealth-specimen-collection-2026-11-21/` | 5 |
| Service Request | `i1jm5rf4ooomt8tbys75o017` | `../sdchealth-service-request-2026-11-21/` | 5 |
| Laboratory Observation | `ojjr56tqlxk808lqq8ig8vg0` | `../sdchealth-lab-observation-2026-11-21/` | 15 |
| Reference Range | `yg61wcme1sjlnezxh0ho6nh0` | `../sdchealth-reference-range-2026-11-21/` | 15 |

**How they join.** As in the first revision's chains, and:
- each Reference Range's Parent Record Identifier is its observation's Record Identifier (`OBS-2026-N-J`);
- each Specimen Collection's Parent Record Identifier is its specimen's Accession Identifier (`ACC-2026-700N`): a
  Specimen has no Record Identifier.

**What differs from the first revision's chains** (where the models do):
- results are in UCUM units (mg/dL, mmol/L);
- a result has a value or a Data Absent Reason, never both: chain 2's sodium is pending (no value, `temp-unknown`,
  no interpretation);
- no test kit or calibrator (optional now);
- the collector, the collection time, method, body site and quantity are the Specimen Collection's.

**Codes** looked up on tx.fhir.org, 21 November 2026:
- SNOMED CT (International 20260701, active): 28520004 Venipuncture for blood test; 49852007 Structure of median
  cubital vein. From the first revision's chains (checked again, active): 119364003 Serum specimen, 73211009 Diabetes
  mellitus, 258026004 Enzyme method, 703445001 Ion selective electrode measurement.
- LOINC 2.83 (active): 2345-7, 2160-0, 2951-2, 24323-8.
- UCUM (valid): mg/dL, mmol/L, mL.
- referencerange-meaning `normal` (Normal Range), one of the values the Reference Range model enumerates.
