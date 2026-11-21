# Chained records in sdc-mapper: a design (not implemented)

sdc-gdr2fhir 4.2.0 maps a parent record and its chained records into one FHIR Bundle through a Python API
(`sdc_gdr2fhir.chain.map_files`). The call surfaces (a CLI command, an MCP tool, and the engine's log and report)
belong in sdc-mapper. This note is the design for that change, planned as sdc-mapper 4.5.0. It is not implemented.

## What sdc-gdr2fhir already gives

- `FHIRMapper.map_chain(parent, children)`:
  - `parent` and each child is a (resolved record, mapping) pair;
  - returns a `ChainMapResult`: the files, and one `MapResult` per record (the parent's first), all holding the same
    files.
  - A child that does not belong raises `ChainError`, a `MappingError`.
- `chain.check(parent, children)`: the join, target-independent. It reads the library's Parent Record Identifier and
  Record Identifier components and the subjects' identifiers.
- `chain.map_files(engine, parent, children)`: gates and reads each record with an sdc-mapper `Engine`, calls
  `map_chain`, and builds each record's report with sdc-mapper's `build_report`. It returns a `ChainResult`:
  - `outcome`;
  - `files`;
  - `records`, each with its instance id, ct_id, gate outcome and coverage report.

## sdc-mapper 4.5.0

**`Engine.map_chain(parent_xml, children_xml, mapper, parent_mapping, child_mappings, directories=None, caller=None)
-> ChainCallResult`**

1. **Find each record's model** (`model_for`) and check its mapping against it (`mapping.check`). An unreachable model
   or a mismatched mapping is `error` for the whole chain, naming the record.
2. **Gate each record** against its own schema, with `reference_model` as its mapping asks. Any refusal is `refused`
   for the whole chain, with that record's errors and its position in the chain. No output is written.
3. **Read and resolve each record.**
4. **Call `mapper.map_chain(parent, children)`.**
   - A mapper without `map_chain` cannot map chains: `error`, "the target maps one record at a time".
   - `MappingError` (`ChainError` included) is `error`, with its reason.
5. **Build each record's report** with `build_report(resolved, result_i, mapper, mapping_i)`. An `IncompleteMapping`
   for any record is `error`.
6. **Log one entry for the chain:**
   - each record's sha256, model, mapping and counts;
   - the outputs' hashes;
   - the outcome (`valid`, `valid_with_ev` if any record needed recovery, `refused`, `error`).
   - Kinds and paths only, as for one record.

**`ChainCallResult`** is `CallResult` with `records: list[RecordReport]` in place of `report`. Each `RecordReport`
holds the instance id, ct_id, gate outcome and `CoverageReport`, the parent's first, in the order given.

**The `Mapper` contract** gains an optional method, `map_chain(parent, children) -> ChainMapResult`. A target that
doesn't implement it maps one record at a time, as now. `contract.py` would define `ChainMapResult` (files, results),
and sdc-gdr2fhir's would become an alias.

**CLI:**
```
sdc-mapper map-chain --target fhir --mapping report.yaml REPORT.xml \
    --child obs.yaml OBS1.xml --child obs.yaml OBS2.xml --child specimen.yaml SPEC.xml -o out/
```
- It writes `Bundle.json` and `report.json`, the per-record reports in order.
- Exit codes are as for `map`.
- A chain manifest (`chain.json`: parent, parent_ct_id, children with file and ct_id, as the samples have) could be
  given instead: `--chain chain.json`.

**MCP:** a `map_chain` tool beside `map_record`.
- **Input:** the parent record, `children` (records, or catalog references), the target, and the mappings. A mapping
  is found by ct_id when the target ships one, as `map_record` does.
- **Output:** the outcome, the files, and the per-record reports.
- Same limits as `map_record`, per record and in total.

**What stays in the target:** where a child's values go, and how the records' resources are joined in one output.
The join itself (`chain.check`) is target-independent and could move to sdc-mapper: a target-agnostic
`resolve_chain` that refuses a child before any mapper runs. That move is optional; the target can keep its own
check.

## Not decided here

- Whether a chain may nest: a child with children of its own (a specimen's parent specimen is a reference, not a
  chain).
- How the log names a chain: the parent's instance id, or a hash of all the records.
- Limits on a chain's size.
