"""The SDCHealth Laboratory models of the library's 2026-11-21 revision (PRD decision 22), in FHIR R4 document Bundles
(HL7 Europe Laboratory Report 2.1.0).

The revision made many members optional, gave Observation Result one assertion (a value or a data absent reason), made
Patient's Date of Birth required, let quantities take any UCUM code, and modelled Reference Range and Specimen
Collection as records chained to a Laboratory Observation and to a Specimen. The synthetic samples:
samples/sdchealth-lab-report-2026-11-21/records/ (tools/make_lab_report_samples.py --revised) and
samples/sdchealth-lab-chains-2026-11-21/ (tools/make_lab_chain_samples.py --revised).
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from lxml import etree

from sdc_mapper import DECLARED, LOOKUP, NOT_REPRESENTABLE, PRESERVED, VALID, Engine, load_mapping
from sdc_mapper.gate import VALID_WITH_EV
from sdc_gdr2fhir import FHIRMapper, mapping_path
from sdc_gdr2fhir.chain import ChainError, map_files
from sdc_gdr2fhir.writer import FHIR_VERSION, _validator

ROOT = Path(__file__).resolve().parents[1]
SUFFIX = "-2026-11-21"
REPORT_CT = "rguwjl3y1d2cxmcv7vooocji"
REPORT_DIR = ROOT / "samples" / f"sdchealth-lab-report{SUFFIX}"
CHAINS = ROOT / "samples" / f"sdchealth-lab-chains{SUFFIX}"
#: the revision's models and the ones they supersede (None: new)
MODELS = {"lab-report": (REPORT_CT, "zptekdommw56yiz9lqjy5dga"),
          "order-information": ("zfh7quqpqxk176c2j4gdestb", "l6m7g3jk6y6tvnisd35l16pw"),
          "lab-observation": ("ojjr56tqlxk808lqq8ig8vg0", "d5b3007cqbmejx7xgs7i484r"),
          "specimen": ("dkzoy1j9aw2u7i7x5lseo7ro", "qws8pcquvnqc55okidyqll83"),
          "service-request": ("i1jm5rf4ooomt8tbys75o017", "nz971o74u4kuk3ifcxc2llq2"),
          "reference-range": ("yg61wcme1sjlnezxh0ho6nh0", None),
          "specimen-collection": ("idprzkpm6sdqgib5w5wzc3ys", None)}
UCUM = "http://unitsofmeasure.org"
IG = os.environ.get("FHIR_VALIDATOR_IG", "hl7.fhir.eu.laboratory#2.1.0")
VALIDATOR = os.environ.get("FHIR_VALIDATOR_JAR", "")
needs_validator = pytest.mark.skipif(not (shutil.which("java") and VALIDATOR and Path(VALIDATOR).exists()),
                                     reason="needs Java and FHIR_VALIDATOR_JAR (the HL7 FHIR validator, validator_cli.jar)")


@pytest.fixture(scope="module")
def engine(tmp_path_factory):
    return Engine(schema_dir=tmp_path_factory.mktemp("schemas"))


def reports():
    return sorted((REPORT_DIR / "records").glob("*.xml"))


def chains():
    return sorted(CHAINS.glob("chain-*"))


def run_report(engine, f: Path):
    m = load_mapping(mapping_path(REPORT_CT))
    return engine.map_record(f.read_bytes(), FHIRMapper.for_mapping(m), m, directory=str(REPORT_DIR))


def files(d: Path):
    man = json.loads((d / "chain.json").read_text(encoding="utf-8"))
    parent = ((ROOT / man["parent"]).read_bytes(), load_mapping(mapping_path(man["parent_ct_id"])), str(REPORT_DIR))
    children = [((d / c["file"]).read_bytes(), load_mapping(mapping_path(c["ct_id"])),
                 str(ROOT / "samples" / f"sdchealth-{c['model']}{SUFFIX}")) for c in man["children"]]
    return parent, children


def bundle(engine, d):
    result = map_files(engine, *files(d))
    return json.loads(result.files["Bundle.json"]), result


def schema_for(ct, d):
    from sdc_mapper.gate import SDC4_XSD
    from sdcvalidator import build_xsd11_schema
    return build_xsd11_schema(str(d / f"dm-{ct}.xsd"),
                              uri_mapper=lambda u: str(SDC4_XSD) if u.rstrip("/").endswith("/ns/sdc4/sdc4.xsd") else u)


# ---------------------------------------------------------------- the mappings
def test_each_revised_model_has_its_own_mapping_and_the_superseded_ones_keep_theirs():
    for kind, (ct, old) in MODELS.items():
        m = load_mapping(mapping_path(ct))
        pkg = ROOT / "samples" / f"sdchealth-{kind}{SUFFIX}"
        import hashlib
        assert m.model_ct_id == ct and m.target_version == "R4"
        assert m.model_schema_sha256 == hashlib.sha256((pkg / f"dm-{ct}.xsd").read_bytes()).hexdigest()
        if old:
            assert load_mapping(mapping_path(old)).model_ct_id == old


def test_each_chained_mapping_chains_to_the_revised_parent():
    text = lambda ct: mapping_path(ct).read_text(encoding="utf-8")     # noqa: E731
    for kind in ("order-information", "lab-observation", "specimen", "service-request"):
        assert f"'@chained-to': {REPORT_CT} " in text(MODELS[kind][0])
    assert "'@chained-to': ojjr56tqlxk808lqq8ig8vg0 obs" in text(MODELS["reference-range"][0])
    assert "'@chained-to': dkzoy1j9aw2u7i7x5lseo7ro spec" in text(MODELS["specimen-collection"][0])


def test_the_mapper_finds_the_mapping_a_model_ships():
    assert FHIRMapper.mapping_for(REPORT_CT) == mapping_path(REPORT_CT)
    assert FHIRMapper.mapping_for("a" * 24) is None


# ---------------------------------------------------------------- the report
def test_the_revised_report_samples_are_valid_against_the_model():
    schema = schema_for(REPORT_CT, REPORT_DIR)
    assert len(reports()) == 15
    for f in reports():
        errors = list(schema.iter_errors(f.read_text(encoding="utf-8")))
        assert not errors, f"{f.name}: {errors[0].reason}"
    # optional since the revision: some reports leave out the attachment, the practice setting and the period
    texts = [f.read_text(encoding="utf-8") for f in reports()]
    assert sum("<label>Attachment</label>" not in t for t in texts) == 3
    assert sum("<label>Document Period</label>" not in t for t in texts) == 2


def test_each_revised_report_maps_to_a_conformant_byte_stable_document_bundle(engine):
    for f in reports():
        r = run_report(engine, f)
        assert r.outcome in (VALID, VALID_WITH_EV), f"{f.name}: {r.errors}"
        b = json.loads(r.files["Bundle.json"])
        assert b["type"] == "document"
        for e in b["entry"]:
            assert not list(_validator(e["resource"]["resourceType"]).iter_errors(e["resource"])), f.name
        assert run_report(engine, f).files["Bundle.json"] == r.files["Bundle.json"]


def test_the_revised_report_value_counts(engine):
    counts = {}
    for f in reports():
        for v in run_report(engine, f).report.values:
            counts[v["class"]] = counts.get(v["class"], 0) + 1
    assert counts == {DECLARED: 1366, LOOKUP: 359, NOT_REPRESENTABLE: 148, PRESERVED: 5}


# ---------------------------------------------------------------- the chains
def test_there_are_revised_chains_and_every_record_is_valid_against_its_model():
    assert len(chains()) == 5
    schemas = {}
    for d in chains():
        man = json.loads((d / "chain.json").read_text(encoding="utf-8"))
        assert man["parent_ct_id"] == REPORT_CT
        assert sorted(c["model"] for c in man["children"]) == ["lab-observation"] * 3 + [
            "order-information"] + ["reference-range"] * 3 + ["service-request", "specimen", "specimen-collection"]
        for c in man["children"]:
            pkg = ROOT / "samples" / f"sdchealth-{c['model']}{SUFFIX}"
            schemas.setdefault(c["ct_id"], schema_for(c["ct_id"], pkg))
            errors = list(schemas[c["ct_id"]].iter_errors((d / c["file"]).read_text(encoding="utf-8")))
            assert not errors, f"{d.name}/{c['file']}: {errors[0].reason}"


def test_each_revised_chain_is_one_conformant_byte_stable_bundle(engine):
    for d in chains():
        b, result = bundle(engine, d)
        assert result.outcome == VALID and len(result.records) == 11
        assert [e["resource"]["resourceType"] for e in b["entry"][:2]] == ["Composition", "DiagnosticReport"]
        for e in b["entry"]:
            assert not list(_validator(e["resource"]["resourceType"]).iter_errors(e["resource"])), d.name
        assert map_files(engine, *files(d)).files["Bundle.json"] == result.files["Bundle.json"]


def test_results_carry_ucum_units_and_a_value_or_a_reason_never_both(engine):
    for d in chains():
        b, _ = bundle(engine, d)
        results = [e["resource"] for e in b["entry"] if e["resource"]["resourceType"] == "Observation"]
        assert len(results) == 3
        for o in results:
            assert ("valueQuantity" in o) != ("dataAbsentReason" in o), d.name           # obs-6
            if "valueQuantity" in o:
                q = o["valueQuantity"]
                assert q["system"] == UCUM and q["code"] == q["unit"] and q["code"] in ("mg/dL", "mmol/L")
    b, _ = bundle(engine, chains()[2])                    # chain 2's sodium is pending: a reason, no value
    pending = [e["resource"] for e in b["entry"] if "dataAbsentReason" in e["resource"]]
    assert [p["dataAbsentReason"]["coding"][0]["code"] for p in pending] == ["temp-unknown"]


def test_each_reference_range_is_in_its_own_observation(engine):
    for d in chains():
        b, _ = bundle(engine, d)
        for o in (e["resource"] for e in b["entry"] if e["resource"]["resourceType"] == "Observation"):
            [rr] = o["referenceRange"]
            assert rr["low"]["code"] == rr["high"]["code"] == o.get("valueQuantity", rr["low"])["code"]
            assert rr["low"]["value"] < rr["high"]["value"]
            assert rr["type"]["coding"] == [{"system": "http://terminology.hl7.org/CodeSystem/referencerange-meaning",
                                             "code": "normal"}]
            loinc = o["code"]["coding"][0]["code"]
            assert {"2345-7": 70, "2160-0": 0.6, "2951-2": 136}[loinc] == rr["low"]["value"]


def test_the_specimen_collection_is_the_specimen_s_collection_with_its_collector(engine):
    for d in chains():
        b, _ = bundle(engine, d)
        urls = {e["fullUrl"]: e["resource"] for e in b["entry"]}
        [spec] = [r for r in urls.values() if r["resourceType"] == "Specimen"]
        c = spec["collection"]
        assert urls[c["collector"]["reference"]]["resourceType"] == "Practitioner"
        assert c["collectedDateTime"].endswith("T07:30:00+01:00")
        assert c["quantity"] == {"value": 5, "unit": "mL", "system": UCUM, "code": "mL"}
        assert c["method"]["coding"][0]["code"] == "28520004" and c["bodySite"]["coding"][0]["code"] == "49852007"
        refs = re.findall(r'"reference": "([^"]+)"', json.dumps(b))
        assert all(r in urls for r in refs), d.name


def test_every_value_of_every_revised_record_has_a_class(engine):
    counts = {}
    for d in chains():
        for record in bundle(engine, d)[1].records:
            for v in record.report.values:
                counts[v["class"]] = counts.get(v["class"], 0) + 1
    assert set(counts) <= {DECLARED, LOOKUP, NOT_REPRESENTABLE, PRESERVED}
    assert counts == {DECLARED: 1207, LOOKUP: 274, NOT_REPRESENTABLE: 786, PRESERVED: 1}


# ---------------------------------------------------------------- refusals
def _with(xml: bytes, old: str, new: str) -> bytes:
    root = etree.fromstring(xml)
    for v in root.iter("xdstring-value"):
        if v.text == old:
            v.text = new
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8")


def test_a_reference_range_of_an_observation_outside_the_chain_is_refused(engine):
    parent, children = files(chains()[0])
    rr = next(c for c in children if b"<dm-label>Reference Range</dm-label>" in c[0])
    changed = (_with(rr[0], "OBS-2026-0-1", "OBS-2026-0-9"), rr[1], rr[2])
    with pytest.raises(ChainError, match="Parent Record Identifier"):
        map_files(engine, parent, [c if c is not rr else changed for c in children])


def test_a_second_collection_of_one_specimen_is_refused(engine):
    parent, children = files(chains()[0])
    col = next(c for c in children if b"<dm-label>Specimen Collection</dm-label>" in c[0])
    root = etree.fromstring(col[0])
    root.find("instance_id").text = "lv00col9synthxxxxxxxxxxx"
    for v in root.iter("xdtemporal-datetime"):
        if v.text and v.text.endswith("T07:30:00+01:00"):
            v.text = v.text.replace("T07:30", "T07:40")
    second = (etree.tostring(root, xml_declaration=True, encoding="UTF-8"), col[1], col[2])
    from sdc_mapper import MappingError
    with pytest.raises(MappingError):
        map_files(engine, parent, children + [second])


def test_a_reference_range_with_a_superseded_observation_s_mapping_target_is_refused(engine):
    """A Reference Range chained to a record of another model than its mapping names (here: to the specimen)."""
    parent, children = files(chains()[0])
    rr = next(c for c in children if b"<dm-label>Reference Range</dm-label>" in c[0])
    changed = (_with(rr[0], "OBS-2026-0-1", "ACC-2026-7000"), rr[1], rr[2])
    with pytest.raises(ChainError, match="chains to model ojjr56tqlxk808lqq8ig8vg0"):
        map_files(engine, parent, [c if c is not rr else changed for c in children])


def test_the_cli_manifest_path_finds_every_mapping_by_model(tmp_path):
    """sdc-mapper 4.5.0's map-chain with the chain manifest alone: FHIRMapper.mapping_for names each mapping."""
    from sdc_mapper.service import load_chain, map_chain
    spec = load_chain(chains()[1] / "chain.json")
    r = map_chain(Engine(schema_dir=tmp_path), "fhir", spec["parent"], spec["children"],
                  parent_ct_id=spec["parent_ct_id"], packages=[str(ROOT / "samples")])
    assert r.outcome == VALID and len(r.records) == 11


# ---------------------------------------------------------------- HL7's validator
def _validate(paths, tmp_path) -> str:
    out = subprocess.run(["java", "-jar", VALIDATOR, *map(str, paths), "-version", FHIR_VERSION, "-ig", IG],
                         capture_output=True, text=True)
    return out.stdout


@pytest.mark.validator
@needs_validator
def test_the_hl7_validator_with_the_lab_guide_finds_no_errors_in_the_revised_chains(engine, tmp_path):
    paths = []
    for d in chains():
        paths.append(tmp_path / f"{d.name}.json")
        paths[-1].write_bytes(map_files(engine, *files(d)).files["Bundle.json"])
    out = _validate(paths, tmp_path)
    assert "*FAILURE*" not in out and out.count("Success: 0 errors") == len(paths), out[-4000:]


@pytest.mark.validator
@needs_validator
def test_the_hl7_validator_finds_only_the_known_model_errors_in_a_revised_report_alone(engine, tmp_path):
    """A report mapped without its chained records has no order identifier (it is the Order Information's) and, where
    its comment is an Exceptional Value, no Composition section. Those are the only errors."""
    paths = []
    for f in reports():
        paths.append(tmp_path / f"{f.stem}.json")
        paths[-1].write_bytes(run_report(engine, f).files["Bundle.json"])
    out = _validate(paths, tmp_path)
    errors = [line for line in out.splitlines() if line.strip().startswith("Error @")]
    known = ("ServiceRequest.identifier: minimum required = 1", "Composition.section: minimum required = 1",
             "Unable to find a profile match")
    assert errors and all(any(k in e for k in known) for e in errors), "\n".join(errors)[:4000]
    assert sum("Composition.section" in e for e in errors) == 1                  # labrev07, its comment NAV
    assert sum("ServiceRequest.identifier" in e for e in errors) == len(paths)
