"""The NHANES mappings: conformant FHIR R4 Bundles, byte-stable, lookups where the model binds the code, and every
Exceptional Value written exactly."""
from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml
from lxml import etree

from sdc_mapper import DECLARED, ERROR, LOOKUP, NOT_REPRESENTABLE, PRESERVED, VALID, Engine, load_mapping
from sdc_gdr2fhir import FHIRMapper, mapping_path
from sdc_gdr2fhir.writer import _validator

ROOT = Path(__file__).resolve().parents[1]
MODELS = [("nhanes-participant", "xy8upneajsb8vdcmnve01g6g"), ("nhanes-medication", "epbdfmvxc3gbh5f66hhb3o2m"),
          ("nhanes-participant-4.2.3", "eehpfapwgvxtzdrofgstdcfs")]   # 4.2.3: the corrected pregnancy codes
PARTICIPANT = MODELS[0]
SDC4 = "https://semanticdatacharter.com/ns/sdc4/"


@pytest.fixture(scope="module")
def engine(tmp_path_factory):
    return Engine(schema_dir=tmp_path_factory.mktemp("schemas"))


def records(model):
    return sorted((ROOT / "samples" / model[0] / "records").glob("*.xml"))


def run(engine, model, xml: bytes, mapping=None):
    return engine.map_record(xml, FHIRMapper(), mapping or load_mapping(mapping_path(model[1])),
                             directory=str(ROOT / "samples" / model[0]))


def bundle(r) -> dict:
    return json.loads(r.files["Bundle.json"])


def resources(b, kind):
    return [e["resource"] for e in b["entry"] if e["resource"]["resourceType"] == kind]


def observation(b, text):
    return next(o for o in resources(b, "Observation") if o["code"].get("text") == text)


def with_participant(engine, need):
    """The first participant record whose Bundle has what `need` looks for."""
    for f in records(PARTICIPANT):
        r = run(engine, PARTICIPANT, f.read_bytes())
        if need(bundle(r)):
            return f.read_bytes(), r
    pytest.skip("no sample record has it")


@pytest.mark.parametrize("model", MODELS, ids=lambda m: m[0])
def test_every_record_is_a_conformant_bundle(engine, model):
    for f in records(model):
        r = run(engine, model, f.read_bytes())
        assert r.outcome == VALID, (f.name, r.errors)
        b = bundle(r)
        assert b["resourceType"] == "Bundle" and b["type"] == "collection"
        for e in b["entry"]:
            assert not list(_validator(e["resource"]["resourceType"]).iter_errors(e["resource"])), f.name
            assert e["fullUrl"] == f"urn:uuid:{e['resource']['id']}"


@pytest.mark.parametrize("model", MODELS, ids=lambda m: m[0])
def test_bundles_are_byte_stable(engine, model):
    xml = records(model)[0].read_bytes()
    assert run(engine, model, xml).files == run(engine, model, xml).files


def test_every_reference_points_to_the_bundles_patient(engine):
    _, r = with_participant(engine, lambda b: len(b["entry"]) > 3)
    b = bundle(r)
    patient = b["entry"][0]
    assert patient["resource"]["resourceType"] == "Patient"
    refs = [o["subject"]["reference"] for o in resources(b, "Observation") + resources(b, "QuestionnaireResponse")]
    assert refs and set(refs) == {patient["fullUrl"]}


def test_where_the_model_binds_the_code_the_value_is_a_lookup(engine):
    _, r = with_participant(engine, lambda b: any(o["code"].get("text") == "Hemoglobin" for o in resources(b, "Observation")))
    classes = {v["label"]: v["class"] for v in r.report.values}
    assert classes["Hemoglobin"] == LOOKUP and classes["Administrative Gender"] == LOOKUP
    assert classes["Respondent Sequence Number (SEQN)"] == DECLARED
    hgb = observation(bundle(r), "Hemoglobin")
    assert hgb["code"]["coding"] == [{"system": "http://loinc.org", "code": "718-7"}]
    assert hgb["valueQuantity"]["system"] == "http://unitsofmeasure.org" and hgb["valueQuantity"]["code"] == "g/dL"
    prov = [v for v in r.report.values if v["path"][1:2] in (["PROV Activity"], ["Audit Event"])]
    assert prov and all(v["class"] == NOT_REPRESENTABLE and "time zone" in v["note"] for v in prov)


def test_blood_pressure_is_a_panel_with_ucum_millimetres_of_mercury(engine):
    _, r = with_participant(engine, lambda b: any(o["code"].get("text") == "Blood pressure panel"
                                                 for o in resources(b, "Observation")))
    bp = observation(bundle(r), "Blood pressure panel")
    codes = {c["code"]["coding"][0]["code"]: c["valueQuantity"] for c in bp["component"]}
    assert set(codes) <= {"8480-6", "8462-4"} and codes
    assert all(q["code"] == "mm[Hg]" for q in codes.values())


# ---------------------------------------------------------------- Exceptional Values
NS = {"sdc4": SDC4}


def with_ev(xml: bytes, label: str, code: str, name: str) -> bytes:
    """The record with a source Exceptional Value on the first value of the component with this label."""
    from sdcreader import load_package, read_model
    model = read_model(load_package(ROOT / "samples" / PARTICIPANT[0], PARTICIPANT[1]))
    ids = {c.ct_id for c in model.components.values() if c.label == label}
    tree = etree.parse(io.BytesIO(xml))
    found = next(el for el in tree.getroot().iter() if isinstance(el.tag, str)
                 and el.tag.startswith(f"{{{SDC4}}}ms-") and el.tag.split("ms-", 1)[1] in ids)
    after = found.find("sdc4:act", NS)
    if after is None:
        after = found.find("label")
    ev = etree.Element(f"{{{SDC4}}}{code}")
    etree.SubElement(ev, "ev-name").text = name
    after.addnext(ev)
    return etree.tostring(tree)


def test_an_observation_value_says_why_it_is_absent(engine):
    xml, _ = with_participant(engine, lambda b: any(o["code"].get("text") == "Hemoglobin" for o in resources(b, "Observation")))
    r = run(engine, PARTICIPANT, with_ev(xml, "Hemoglobin", "ASKR", "Asked and Refused"))
    assert r.outcome == VALID, r.errors
    hgb = observation(bundle(r), "Hemoglobin")
    assert "valueQuantity" not in hgb
    assert hgb["dataAbsentReason"]["coding"] == [
        {"system": "http://terminology.hl7.org/CodeSystem/data-absent-reason", "code": "asked-declined"}]
    assert [(e["code"], e["class"], e["target_code"]) for e in r.report.exceptional] == [
        ("ASKR", PRESERVED, "data-absent-reason#asked-declined")]


def test_a_null_flavor_data_absent_reason_lacks_is_written_exactly(engine):
    xml, _ = with_participant(engine, lambda b: True)
    r = run(engine, PARTICIPANT, with_ev(xml, "Annual Household Income (INDHHIN2)", "INV", "Invalid"))
    if not any(e["label"] == "Annual Household Income (INDHHIN2)" for e in r.report.exceptional):
        pytest.skip("the first record has no household income")
    qr = resources(bundle(r), "QuestionnaireResponse")[0]
    income = next(i for i in qr["item"] if i["text"] == "Annual Household Income (INDHHIN2)")
    assert income["answer"] == [{"_valueString": {"extension": [
        {"url": "http://hl7.org/fhir/StructureDefinition/iso21090-nullFlavor", "valueCode": "INV"}]}}]
    assert r.report.exceptional[0]["class"] == PRESERVED


def test_an_absent_gender_carries_the_extension(engine):
    xml, _ = with_participant(engine, lambda b: True)
    r = run(engine, PARTICIPANT, with_ev(xml, "Administrative Gender", "ASKU", "Asked but Unknown"))
    patient = resources(bundle(r), "Patient")[0]
    assert "gender" not in patient
    assert patient["_gender"]["extension"] == [
        {"url": "http://hl7.org/fhir/StructureDefinition/data-absent-reason", "valueCode": "asked-unknown"}]


def test_every_null_flavor_is_preserved():
    table = FHIRMapper.ev_table
    assert len(table) == 16 and all(r.cls == PRESERVED for r in table.values())
    assert table["ASKR"].target_code == "data-absent-reason#asked-declined"
    assert table["INV"].target_code == "v3-NullFlavor#INV"


# ---------------------------------------------------------------- refused mappings
def edited(model, tmp_path, change):
    doc = yaml.safe_load(mapping_path(model[1]).read_text())
    change(doc)
    p = tmp_path / "m.yaml"
    p.write_text(yaml.safe_dump(doc, sort_keys=False))
    return load_mapping(p)


def test_a_component_with_no_rule_is_an_incomplete_mapping(engine, tmp_path):
    m = edited(PARTICIPANT, tmp_path, lambda d: d.update(rules=[r for r in d["rules"] if not r.get("to", "").endswith("/gender")]))
    r = run(engine, PARTICIPANT, records(PARTICIPANT)[0].read_bytes(), m)
    assert r.outcome == ERROR and "Administrative Gender" in r.errors[0]["reason"]


def test_a_mapping_cannot_change_how_an_exceptional_value_is_written(engine, tmp_path):
    m = edited(PARTICIPANT, tmp_path, lambda d: d.update(exceptional_values={"ASKR": {"class": "lost"}}))
    r = run(engine, PARTICIPANT, records(PARTICIPANT)[0].read_bytes(), m)
    assert r.outcome == ERROR and "exactly" in r.errors[0]["reason"]


def test_an_element_fhir_does_not_have_is_an_error_not_a_guess(engine, tmp_path):
    def change(d):
        for r in d["rules"]:
            if r.get("to", "").endswith("/gender"):
                r["to"] = r["to"].replace("/gender", "/sex")
    r = run(engine, PARTICIPANT, records(PARTICIPANT)[0].read_bytes(), edited(PARTICIPANT, tmp_path, change))
    assert r.outcome == ERROR and "sex is not an element" in r.errors[0]["reason"]


# ---------------------------------------------------------------- the HL7 FHIR validator, where it is installed
VALIDATOR = os.environ.get("FHIR_VALIDATOR_JAR", "")


@pytest.mark.validator
@pytest.mark.skipif(not (shutil.which("java") and VALIDATOR and Path(VALIDATOR).exists()),
                    reason="needs Java and FHIR_VALIDATOR_JAR (the HL7 FHIR validator, validator_cli.jar)")
def test_the_hl7_validator_finds_no_errors(engine, tmp_path):
    for model in MODELS:
        f = tmp_path / f"{model[0]}.json"
        f.write_bytes(run(engine, model, records(model)[0].read_bytes()).files["Bundle.json"])
        out = subprocess.run(["java", "-jar", VALIDATOR, str(f), "-version", "4.0.1"], capture_output=True, text=True)
        assert "*FAILURE*" not in out.stdout and out.returncode == 0, out.stdout[-4000:]


# ---------------------------------------------------------------- what FHIR R4 asks beyond the record (4.0.3)
SURVEY_CYCLE = {"start": "2017-01-01", "end": "2018-12-31"}


def test_every_observation_is_dated_by_the_survey_cycle(engine):
    """NHANES records carry no examination date; FHIR R4's vital signs profiles require one (declared)."""
    _, r = with_participant(engine, lambda b: bool(resources(b, "Observation")))
    obs = resources(bundle(r), "Observation")
    assert obs and all(o["effectivePeriod"] == SURVEY_CYCLE and "effectiveDateTime" not in o for o in obs)


def test_a_record_s_own_date_wins_over_the_survey_cycle():
    from sdc_gdr2fhir.writer import Builder, Node
    k = ("t",)
    obs = Node("resource", k, children=[Node("resourceType", k, text="Observation"),
                                        Node("effectiveDateTime", k, text="2018-03-04"),
                                        Node("effectivePeriod", k, children=[Node("start", k, text="2017-01-01")])])
    Builder._profiles(obs)
    assert obs.child("effectivePeriod") is None and obs.child("effectiveDateTime").text == "2018-03-04"


def test_a_quantity_says_its_unit_as_people_read_it(engine):
    _, r = with_participant(engine, lambda b: any(o["code"].get("text") == "Blood pressure panel"
                                                 for o in resources(b, "Observation")))
    for c in observation(bundle(r), "Blood pressure panel")["component"]:
        if "valueQuantity" in c:
            assert (c["valueQuantity"]["unit"], c["valueQuantity"]["code"]) == ("mmHg", "mm[Hg]")


def test_a_blood_pressure_reading_missing_a_component_says_why(engine):
    """The vital signs profile requires systolic and diastolic; the one the record lacks is absent, reason unknown."""
    _, r = with_participant(engine, lambda b: any(
        "dataAbsentReason" in c for o in resources(b, "Observation") for c in o.get("component", [])))
    for bp in (o for o in resources(bundle(r), "Observation") if o["code"].get("text") == "Blood pressure panel"):
        assert [c["code"]["coding"][0]["code"] for c in bp["component"]] == ["8480-6", "8462-4"]
        for c in bp["component"]:
            assert ("valueQuantity" in c) != ("dataAbsentReason" in c)
            if "dataAbsentReason" in c:
                assert c["dataAbsentReason"]["coding"][0]["code"] == "unknown"


def test_a_coding_display_is_never_the_model_s_label(engine):
    """A Coding's display is the code system's; the model's label is the CodeableConcept's text."""
    for model in MODELS:
        for f in records(model)[:20]:
            assert '"display"' not in run(engine, model, f.read_bytes()).files["Bundle.json"].decode()


# ---------------------------------------------------------------- E-2026-10-01 (4.0.4)
PARTICIPANT_423 = MODELS[2]
PREGNANCY = {"Yes": "LA15173-0", "No": "LA26683-5", "Unknown": "LA4489-6"}


def test_nhanes_participant_4_2_3_answers_pregnancy_with_the_corrected_codes(engine):
    """NHANES Participant 4.2.3 composes the NIH CDE library's correction of "Are you pregnant now?" (E-2026-10-01):
    each answer's LOINC code is the answer's own, not the next value's as in NIH's record and the 4.2.0 model."""
    seen = {}
    for f in records(PARTICIPANT_423):
        if b"ms-zmpqfc6tb0o2hgu8qs6lj8tp" not in f.read_bytes():
            continue
        b = bundle(run(engine, PARTICIPANT_423, f.read_bytes()))
        qr = resources(b, "QuestionnaireResponse")[0]
        for it in qr["item"]:
            if it["text"] == "Are you pregnant now?":
                coding = it["answer"][0]["valueCoding"]
                seen[coding["code"]] = coding["system"]
    assert seen and set(seen) <= set(PREGNANCY.values()) and set(seen.values()) == {"http://loinc.org"}
