"""A Laboratory Report and the records chained to it, in one FHIR R4 document Bundle (HL7 Europe Laboratory Report 2.1.0).

The synthetic sets in samples/sdchealth-lab-chains/ (tools/make_lab_chain_samples.py): each a report sample, its Order
Information, a Specimen, a Service Request and three Laboratory Observations.
"""
from __future__ import annotations

import copy
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from lxml import etree

from sdc_mapper import DECLARED, LOOKUP, NOT_REPRESENTABLE, PRESERVED, Engine, MappingError, load_mapping
from sdc_gdr2fhir import FHIRMapper, mapping_path
from sdc_gdr2fhir.chain import ChainError, map_files, read
from sdc_gdr2fhir.writer import FHIR_VERSION, _validator

ROOT = Path(__file__).resolve().parents[1]
CHAINS = ROOT / "samples" / "sdchealth-lab-chains"
REPORT_CT = "zptekdommw56yiz9lqjy5dga"
IG = os.environ.get("FHIR_VALIDATOR_IG", "hl7.fhir.eu.laboratory#2.1.0")
VALIDATOR = os.environ.get("FHIR_VALIDATOR_JAR", "")


@pytest.fixture(scope="module")
def engine(tmp_path_factory):
    return Engine(schema_dir=tmp_path_factory.mktemp("schemas"))


def chains():
    return sorted(CHAINS.glob("chain-*"))


def files(d: Path):
    """(parent, children) as map_files takes them."""
    man = json.loads((d / "chain.json").read_text(encoding="utf-8"))
    parent = ((ROOT / man["parent"]).read_bytes(), load_mapping(mapping_path(REPORT_CT)),
              str(ROOT / "samples" / "sdchealth-lab-report"))
    children = [((d / c["file"]).read_bytes(), load_mapping(mapping_path(c["ct_id"])),
                 str(ROOT / "samples" / f"sdchealth-{c['model']}")) for c in man["children"]]
    return parent, children


def bundle(engine, d):
    result = map_files(engine, *files(d))
    return json.loads(result.files["Bundle.json"]), result


def test_there_are_chained_sets_and_every_record_is_valid_against_its_model():
    from sdc_mapper.gate import SDC4_XSD
    from sdcvalidator import build_xsd11_schema
    assert len(chains()) == 5
    schemas = {}
    for d in chains():
        man = json.loads((d / "chain.json").read_text(encoding="utf-8"))
        assert sorted(c["model"] for c in man["children"]) == ["lab-observation"] * 3 + [
            "order-information", "service-request", "specimen"]
        for c in man["children"]:
            if c["ct_id"] not in schemas:
                schemas[c["ct_id"]] = build_xsd11_schema(
                    str(ROOT / "samples" / f"sdchealth-{c['model']}" / f"dm-{c['ct_id']}.xsd"),
                    uri_mapper=lambda u: str(SDC4_XSD) if u.rstrip("/").endswith("/ns/sdc4/sdc4.xsd") else u)
            errors = list(schemas[c["ct_id"]].iter_errors((d / c["file"]).read_text(encoding="utf-8")))
            assert not errors, f"{d.name}/{c['file']}: {errors[0].reason}"


def test_each_chain_is_one_conformant_document_bundle(engine):
    for d in chains():
        b, _ = bundle(engine, d)
        assert b["type"] == "document"
        assert [e["resource"]["resourceType"] for e in b["entry"][:2]] == ["Composition", "DiagnosticReport"]
        for e in b["entry"]:
            assert not list(_validator(e["resource"]["resourceType"]).iter_errors(e["resource"])), d.name


def test_chained_bundles_are_byte_stable(engine):
    for d in chains():
        assert map_files(engine, *files(d)).files["Bundle.json"] == map_files(engine, *files(d)).files["Bundle.json"]


def test_the_children_are_wired_where_the_guide_puts_them(engine):
    """Results in DiagnosticReport.result and the results section; the specimen in DiagnosticReport.specimen and each
    result's specimen; the request in basedOn (the report's and each result's); the order's identifier on the report's
    ServiceRequest."""
    for d in chains():
        b, _ = bundle(engine, d)
        urls = {e["fullUrl"]: e["resource"] for e in b["entry"]}
        refs = re.findall(r'"reference": "([^"]+)"', json.dumps(b))
        assert all(r in urls for r in refs), d.name
        comp, dr = b["entry"][0]["resource"], b["entry"][1]["resource"]
        kind = lambda ref: urls[ref["reference"]]["resourceType"]   # noqa: E731
        results = [urls[r["reference"]] for r in dr["result"]]
        assert len(results) == 3 and {o["resourceType"] for o in results} == {"Observation"}
        section = next(s for s in comp["section"] if s["code"]["coding"][0]["code"] == "26436-6")
        assert [e["reference"] for e in section["entry"]] == [r["reference"] for r in dr["result"]]
        assert section["text"]["status"] == "generated" and "<li>" in section["text"]["div"]
        [specimen] = [urls[r["reference"]] for r in dr["specimen"]]
        assert specimen["resourceType"] == "Specimen" and specimen["accessionIdentifier"]["value"]
        assert all(urls[o["specimen"]["reference"]] is specimen for o in results)
        requests = [urls[r["reference"]] for r in dr["basedOn"]]
        order = next(r for r in requests if "requester" in r and kind(r["requester"]) == "Practitioner"
                     and r.get("identifier", [{}])[0].get("value", "").startswith("ORD-"))
        assert order["identifier"][0]["value"].startswith("ORD-2026-")
        panel = next(r for r in requests if r is not order)
        assert panel["identifier"][0]["value"].startswith("SR-2026-")
        assert all(urls[o["basedOn"][0]["reference"]] is panel for o in results)
        assert [urls[r["reference"]] for r in specimen["request"]] == [panel]
        assert all(o["subject"] == dr["subject"] for o in results + [specimen, panel])


def test_each_record_has_its_own_report_and_the_chain_one_outcome(engine):
    """One result per chain: the Bundle, the gate's outcome for the chain (valid_with_ev only if a record needed the
    gate's recovery), and a coverage report for each record, the parent's first, with its Exceptional Values."""
    from sdc_mapper import VALID
    results = [bundle(engine, d)[1] for d in chains()]
    assert [r.outcome for r in results] == [VALID] * 5
    nav = results[2].records[-1].report.exceptional
    assert [(e["code"], e["class"]) for e in nav] == [("NAV", PRESERVED)]


def test_every_value_of_every_record_has_a_class(engine):
    counts = {}
    for d in chains():
        _, result = bundle(engine, d)
        assert len(result.records) == 7 and result.records[0].ct_id == REPORT_CT
        for record in result.records:
            for v in record.report.values:
                counts[v["class"]] = counts.get(v["class"], 0) + 1
    assert set(counts) <= {DECLARED, LOOKUP, NOT_REPRESENTABLE, PRESERVED}
    assert counts == {DECLARED: 1131, LOOKUP: 274, NOT_REPRESENTABLE: 546, PRESERVED: 2}


def test_a_child_of_another_report_is_refused(engine):
    parent, children = files(chains()[0])
    _, other = files(chains()[1])
    with pytest.raises(ChainError, match="Parent Record Identifier"):
        map_files(engine, parent, children + [other[0]])


def test_a_specimen_no_record_names_is_refused(engine):
    parent, children = files(chains()[0])
    xml, mapping, directory = next(c for c in children if b"Specimen" in c[0][:600])
    root = etree.fromstring(xml)                     # a second specimen of the same patient, which nothing names
    root.find("instance_id").text = "lc00spc9synthxxxxxxxxxxx"
    for v in root.iter("xdstring-value"):
        if v.text and v.text.startswith("ACC-"):
            v.text = "ACC-2026-7999"
    extra = (etree.tostring(root, xml_declaration=True, encoding="UTF-8"), mapping, directory)
    with pytest.raises(ChainError, match="no record of the chain names it"):
        map_files(engine, parent, children + [extra])


def test_a_reference_to_a_record_outside_the_chain_is_refused(engine):
    parent, children = files(chains()[0])
    without_specimen = [c for c in children if b"Specimen" not in c[0][:600]]
    with pytest.raises(ChainError, match="no record of the chain"):
        map_files(engine, parent, without_specimen)


def test_a_child_about_another_patient_is_refused(engine):
    parent, children = files(chains()[0])
    order = next(c for c in children if b"Order Information" in c[0][:600])
    root = etree.fromstring(order[0])
    for v in root.find("subject").iter("xdstring-value"):
        if v.text and v.text.startswith("PT-SNS-"):
            v.text = "PT-SNS-999999999"
    changed = (etree.tostring(root, xml_declaration=True, encoding="UTF-8"), order[1], order[2])
    with pytest.raises(ChainError, match="another patient"):
        map_files(engine, parent, [changed] + [c for c in children if c is not order])


def test_a_chained_record_s_mapping_maps_only_with_its_parent(engine):
    _, children = files(chains()[0])
    xml, mapping, directory = children[0]
    record, _ = read(engine, xml, mapping, directory)
    with pytest.raises(MappingError, match="maps only with its parent"):
        FHIRMapper.for_mapping(mapping).map(record, mapping)


def test_the_report_alone_is_unchanged_by_the_chain_support(engine):
    """The report sample mapped alone is the Bundle its own tests check: the same bytes through either path."""
    parent, _ = files(chains()[0])
    alone = engine.map_record(parent[0], FHIRMapper.for_mapping(parent[1]), parent[1], directory=parent[2])
    assert map_files(engine, parent, []).files["Bundle.json"] == alone.files["Bundle.json"]


@pytest.mark.validator
@pytest.mark.skipif(not (shutil.which("java") and VALIDATOR and Path(VALIDATOR).exists()),
                    reason="needs Java and FHIR_VALIDATOR_JAR (the HL7 FHIR validator, validator_cli.jar)")
def test_the_hl7_validator_with_the_lab_guide_finds_no_errors_in_the_chains(engine, tmp_path):
    for d in chains():
        out_file = tmp_path / f"{d.name}.json"
        out_file.write_bytes(map_files(engine, *files(d)).files["Bundle.json"])
        out = subprocess.run(["java", "-jar", VALIDATOR, str(out_file), "-version", FHIR_VERSION, "-ig", IG],
                             capture_output=True, text=True)
        assert "*FAILURE*" not in out.stdout and out.returncode == 0, out.stdout[-4000:]
