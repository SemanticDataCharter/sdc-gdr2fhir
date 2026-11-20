"""The SDCHealth Laboratory Report mapping (HL7 Europe Laboratory Report 2.1.0) and its synthetic samples.

The mapping reads the record's reference-model parts (`reference_model: true`; sdcreader 4.5.0, sdc-mapper 4.4.0):
the subject, provider, Participations, Attestation and workflow beside the data cluster. Conformance to the guide is
for HL7's validator with the guide's package, which runs where Java and the validator are installed.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml
from lxml import etree

from sdc_mapper import DECLARED, LOOKUP, NOT_REPRESENTABLE, PRESERVED, VALID, Engine, load_mapping
from sdc_mapper.gate import VALID_WITH_EV
from sdc_gdr2fhir import FHIRMapper, mapping_path
from sdc_gdr2fhir.writer import FHIR_VERSION, _validator

ROOT = Path(__file__).resolve().parents[1]
CT = "zptekdommw56yiz9lqjy5dga"
DIR = ROOT / "samples" / "sdchealth-lab-report"
DATA_CLUSTER = "qnocwj0gevwczd88of20iucv"           # Laboratory Report: the model's data cluster
SDC4 = "https://semanticdatacharter.com/ns/sdc4/"
IG = os.environ.get("FHIR_VALIDATOR_IG", "hl7.fhir.eu.laboratory#2.1.0")
VALIDATOR = os.environ.get("FHIR_VALIDATOR_JAR", "")
SUBJECT, PROVIDER = "uficdtk6vpsgvpeyr1sevj9j", "qau8mx32a2d0v54jrc2q7y9y"        # the Patient and Author Parties
ATTESTATION, WORKFLOW = "q1yia3n12i53ly5mdjldocw9", "n92zyhs2luqrhr4hw483kh6m"
PARTICIPATIONS = ("e7jes8an7n8t58qyabk1nnm2", "k6j6ln7pcgy0n11in45xtd69", "q5g9nqjxzj0su0rpn8icgqjc",
                  "op04cbyj14qocu2u38nljhk8")               # attester, custodian, intended recipient, order placer
VALUE_ELEMENTS = ("xdstring-value", "xdtoken-value", "xdtemporal-date", "xdtemporal-datetime", "xdcount-value", "uri",
                  "ordinal", "true-value", "false-value", "xdstringlist-value")


@pytest.fixture(scope="module")
def engine(tmp_path_factory):
    return Engine(schema_dir=tmp_path_factory.mktemp("schemas"))


@pytest.fixture(scope="module")
def mapping():
    return load_mapping(mapping_path(CT))


def records():
    return sorted((DIR / "records").glob("*.xml"))


def run(engine, mapping, f: Path):
    return engine.map_record(f.read_bytes(), FHIRMapper.for_mapping(mapping), mapping, directory=str(DIR))


def test_there_is_a_small_synthetic_sample():
    assert 10 <= len(records()) <= 20


def test_every_sample_is_valid_against_the_model_s_xsd_1_1_schema():
    from sdc_mapper.gate import SDC4_XSD
    from sdcvalidator import build_xsd11_schema
    schema = build_xsd11_schema(str(DIR / f"dm-{CT}.xsd"),
                                uri_mapper=lambda u: str(SDC4_XSD) if u.rstrip("/").endswith("/ns/sdc4/sdc4.xsd") else u)
    for f in records():
        errors = list(schema.iter_errors(f.read_text(encoding="utf-8")))
        assert not errors, f"{f.name}: {errors[0].reason}"


def test_the_samples_carry_exceptional_values():
    found = {el.tag.split("}")[1] for f in records() for el in etree.parse(str(f)).iter()
             if isinstance(el.tag, str) and el.find("ev-name") is not None}
    assert {"ASKU", "NAV", "UNK", "ASKR"} <= found


def test_the_mapping_is_for_fhir_r4_and_the_model_s_schema():
    d = yaml.safe_load(mapping_path(CT).read_text(encoding="utf-8"))
    assert d["target"] == {"name": "HL7 FHIR", "version": "R4"}
    assert d["model"]["schema_sha256"] == "150c6c74c3760496ff172141d596a78b75e69753ec8850f3872d1ba00a2a3ec6"
    bundle = next(r for r in d["rules"] if r.get("to") == "Bundle")
    assert bundle["cluster"] == DATA_CLUSTER
    assert bundle["attributes"]["type"] == "document"
    assert bundle["attributes"]["meta/profile"] == "http://hl7.eu/fhir/laboratory/StructureDefinition/Bundle-eu-lab"
    assert d["reference_model"] is True


def test_sdcreader_reads_the_record_s_reference_model_parts():
    """With `reference_model` the reader reads the data cluster and the record's subject, provider, Participations,
    Attestation and workflow: every value the record holds."""
    from sdcreader import load_package, read_model
    from sdcreader.record import read_record
    model = read_model(load_package(DIR, CT))
    for f in records():
        read = read_record(f.read_bytes(), model, reference_model=True).values
        held = [el for el in etree.parse(str(f)).iter() if isinstance(el.tag, str) and el.tag in VALUE_ELEMENTS]
        parts = {v.path[0].ct_id for v in read} - {DATA_CLUSTER}
        assert {SUBJECT, PROVIDER, ATTESTATION, WORKFLOW, *PARTICIPATIONS} <= parts, f.name
        texts = {str(t) for v in read for t in v.elements.values()}
        values = {el.text for el in held if el.getparent().tag != "xdcount-units"}   # a count's units are not a value
        assert values <= texts, f.name                             # every value the record holds is read
        assert {v.role for v in read} >= {"start", "end", "committed", "pending"}   # and the plain values


def test_every_sample_maps_to_a_conformant_document_bundle(engine, mapping):
    for f in records():
        r = run(engine, mapping, f)
        assert r.outcome in (VALID, VALID_WITH_EV), f"{f.name}: {r.errors}"
        b = json.loads(r.files["Bundle.json"])
        assert b["type"] == "document" and b["timestamp"]
        assert [e["resource"]["resourceType"] for e in b["entry"][:2]] == ["Composition", "DiagnosticReport"]
        for e in b["entry"]:
            assert not list(_validator(e["resource"]["resourceType"]).iter_errors(e["resource"])), f.name


def test_bundles_are_byte_stable(engine, mapping):
    for f in records():
        assert run(engine, mapping, f).files["Bundle.json"] == run(engine, mapping, f).files["Bundle.json"]


def entries(b, kind):
    return [e for e in b["entry"] if e["resource"]["resourceType"] == kind]


def test_every_reference_names_an_entry_of_the_bundle_and_each_party_is_in_its_place(engine, mapping):
    """The parties go where the guide's map puts them: the subject and author, the professional attester (the
    Attester Participation) and the legal one (the Attestation), the custodian, the information recipient, and the
    order placer as the requester of the ServiceRequest the DiagnosticReport is based on."""
    for f in records():
        b = json.loads(run(engine, mapping, f).files["Bundle.json"])
        urls = {e["fullUrl"]: e["resource"] for e in b["entry"]}
        refs = re.findall(r'"reference": "([^"]+)"', json.dumps(b))
        assert refs and all(r in urls for r in refs), f.name
        comp, dr = b["entry"][0]["resource"], b["entry"][1]["resource"]
        kind = lambda ref: urls[ref["reference"]]["resourceType"]   # noqa: E731
        assert kind(comp["subject"]) == kind(dr["subject"]) == "Patient" and comp["subject"] == dr["subject"]
        assert [kind(a) for a in comp["author"]] == ["Practitioner"]
        assert {a["mode"] for a in comp["attester"]} == {"professional", "legal"}
        assert all(kind(a["party"]) == "Practitioner" and a["time"] for a in comp["attester"])
        assert kind(comp["custodian"]) == "Organization"
        recipient = next(x for x in comp["extension"] if x["url"].endswith("/information-recipient"))
        assert kind(recipient["valueReference"]) == "Patient"
        sr = urls[dr["basedOn"][0]["reference"]]
        assert sr["resourceType"] == "ServiceRequest" and kind(sr["requester"]) == "Practitioner"
        assert comp["status"] == dr["status"] and comp["status"] in ("preliminary", "final", "amended")


def test_the_composition_and_the_diagnostic_report_agree_as_the_guide_asks(engine, mapping):
    """dr-comp-identifier and dr-comp-type: the same identifier and the same type code in both."""
    for f in records():
        b = json.loads(run(engine, mapping, f).files["Bundle.json"])
        comp, dr = b["entry"][0]["resource"], b["entry"][1]["resource"]
        assert comp["identifier"]["value"] in [i["value"] for i in dr["identifier"]]
        assert comp["type"]["coding"] == dr["code"]["coding"]


def test_every_exceptional_value_is_preserved(engine, mapping):
    found = {}
    for f in records():
        for e in run(engine, mapping, f).report.exceptional:
            found[e["code"]] = e["class"]
    assert found == {"ASKU": PRESERVED, "NAV": PRESERVED, "UNK": PRESERVED, "ASKR": PRESERVED}


def test_the_comments_are_the_guide_s_annotations_section_and_the_conclusion(engine, mapping):
    """Composition-eu-lab's `annotations` section (LOINC 48767-8, no entries): the comment as XHTML narrative, and the
    same comment as the DiagnosticReport's conclusion. The record whose comment is an Exceptional Value has no
    section; the reason is on the conclusion."""
    for f in records():
        b = json.loads(run(engine, mapping, f).files["Bundle.json"])
        comp, dr = b["entry"][0]["resource"], b["entry"][1]["resource"]
        if "conclusion" not in dr:
            assert "section" not in comp and dr["_conclusion"]["extension"][0]["valueCode"] == "temp-unknown", f.name
            continue
        [section] = comp["section"]
        assert section["code"]["coding"][0]["code"] == "48767-8" and "entry" not in section
        assert section["text"]["status"] == "additional"
        assert section["text"]["div"] == f'<div xmlns="http://www.w3.org/1999/xhtml">{dr["conclusion"]}</div>'


def test_the_record_s_language_is_the_documents(engine, mapping):
    """dm-language, an attribute of the record's root (fixed by the model): `{record:dm-language}`."""
    b = json.loads(run(engine, mapping, records()[0]).files["Bundle.json"])
    assert b["entry"][0]["resource"]["language"] == b["entry"][1]["resource"]["language"] == "en-US"


def test_an_unknown_sex_for_clinical_use_still_has_a_code_from_its_required_value_set(engine, mapping):
    """The ASKU: the extension's CodeableConcept carries data-absent-reason `unknown`, which Sex Parameter for
    Clinical Use includes, and its text the exact reason, asked-unknown."""
    f = DIR / "records" / "labrep04synthxxxxxxxxxxx.xml"
    b = json.loads(run(engine, mapping, f).files["Bundle.json"])
    patient = b["entry"][2]["resource"]
    value = patient["extension"][0]["extension"][0]["valueCodeableConcept"]
    assert value["coding"] == [{"system": "http://terminology.hl7.org/CodeSystem/data-absent-reason", "code": "unknown"}]
    assert value["_text"]["extension"][0]["valueCode"] == "asked-unknown"


def test_the_value_counts_of_the_sample(engine, mapping):
    """The counts the README gives."""
    counts = {}
    for f in records():
        for v in run(engine, mapping, f).report.values:
            counts[v["class"]] = counts.get(v["class"], 0) + 1
    assert counts == {DECLARED: 1380, LOOKUP: 359, NOT_REPRESENTABLE: 154, PRESERVED: 5}


@pytest.mark.validator
@pytest.mark.skipif(not (shutil.which("java") and VALIDATOR and Path(VALIDATOR).exists()),
                    reason="needs Java and FHIR_VALIDATOR_JAR (the HL7 FHIR validator, validator_cli.jar)")
def test_the_hl7_validator_with_the_lab_guide_finds_no_errors(engine, mapping, tmp_path):
    for f in records():
        out_file = tmp_path / f"{f.stem}.json"
        out_file.write_bytes(run(engine, mapping, f).files["Bundle.json"])
        out = subprocess.run(["java", "-jar", VALIDATOR, str(out_file), "-version", FHIR_VERSION, "-ig", IG],
                             capture_output=True, text=True)
        assert "*FAILURE*" not in out.stdout and out.returncode == 0, out.stdout[-4000:]
