"""Write synthetic chained-record sets for the SDCHealth Laboratory Report, and check each record against its model.

    python tools/make_lab_chain_samples.py

Each set is one Laboratory Report sample (samples/sdchealth-lab-report/records/) and the records chained to it
(library decision 12), in samples/sdchealth-lab-chains/chain-NN/:
- an Order Information: the order the report answers (its identifier, when and why it was placed);
- a Specimen: named by the other records by reference, identified by its accession identifier;
- a Service Request: the requested panel;
- three Laboratory Observations: the results, each naming the specimen and the request.
`chain.json` lists the parent and the children. Each child's Parent Record Identifier is the report's Record
Identifier, its subject is the report's patient (the report's subject details, copied), and its author the report's.

The records are made up: no person, professional, organisation, order, specimen or result in them is real. Every LOINC,
SNOMED CT and UCUM code was looked up on HL7's terminology server (tx.fhir.org, 20 November 2026; see the README in
samples/sdchealth-lab-chains/), not written from memory, and is used only where the model allows a code of that system.
Each record is validated against its model's XSD 1.1 schema before it is written.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

from lxml import etree

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_lab_report_samples import (LABS, PERSONS, PROFESSIONALS, SDC4, UNITS, fill, is_leaf, label,  # noqa: E402
                                     prune)

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "samples" / "sdchealth-lab-report"
OUT = ROOT / "samples" / "sdchealth-lab-chains"
MODELS = {"order-information": "l6m7g3jk6y6tvnisd35l16pw", "specimen": "qws8pcquvnqc55okidyqll83",
          "service-request": "nz971o74u4kuk3ifcxc2llq2", "lab-observation": "d5b3007cqbmejx7xgs7i484r"}
SETS = 5

LOINC_PANEL = ("24323-8", "Comprehensive metabolic 2000 panel - Serum or Plasma")
SERUM = ("119364003", "Serum specimen")
DIABETES = ("73211009", "Diabetes mellitus")
#: The only text the models' XdQuantity units allow (each model's schema enumerates it).
MODEL_UNITS = "UCUM Units"
ENZYME = ("258026004", "Enzyme method")
ISE = ("703445001", "Ion selective electrode measurement")
#: (LOINC code, its display, UCUM units, normal low, normal high, method) for each result
RESULTS = [("2345-7", "Glucose [Mass/volume] in Serum or Plasma", "mg/dL", 70, 99, ENZYME),
           ("2160-0", "Creatinine [Mass/volume] in Serum or Plasma", "mg/dL", 0.6, 1.2, ENZYME),
           ("2951-2", "Sodium [Moles/volume] in Serum or Plasma", "mmol/L", 136, 145, ISE)]
VALUES = [["92", "0.9", "140"], ["131", "1.1", "138"], ["88", "0.8", "EV:NAV"], ["104", "1.4", "142"],
          ["79", "0.7", "137"]]


def iid(n: int, kind: str, j: int = 0) -> str:
    base = f"lc{n:02d}{kind}{j}synth"
    return base + "x" * (24 - len(base))


def iri(instance_id: str) -> str:
    """A record's IRI as the chain names it: its instance id at the end (sdc-gdr2fhir's chain)."""
    return f"urn:sdc4:record:{instance_id}"


def path_of(el, root_label: str) -> tuple[str, ...]:
    out = [lab for a in [el, *el.iterancestors()] if (lab := label(a)) is not None]
    out.reverse()
    return tuple(out[1:] if out and out[0] == root_label else out)


def professional(h, prefix):
    given, surname, title, country, city, street, postcode, ident, authority = h
    return {(*prefix, "Address", "Country", "Country Code ISO 3166"): country, (*prefix, "Address", "City Name"): city,
            (*prefix, "Address", "Address (Line 1)"): street, (*prefix, "Address", "Postal Code"): postcode,
            (*prefix, "Address", "Address Use"): "work", (*prefix, "Human Name", "Given Name (Person)"): given,
            (*prefix, "Human Name", "Surname (Person)"): surname, (*prefix, "Human Name", "Name Prefix"): title,
            (*prefix, "Person Identifier", "Identifier Value"): ident,
            (*prefix, "Person Identifier", "Issuing Authority"): authority}


def lab(o, prefix):
    name, kind, country, city, street, postcode, ident = o
    return {(*prefix, "Organization Name"): name, (*prefix, "Organization Type"): kind,
            (*prefix, "Address", "Country", "Country Code ISO 3166"): country, (*prefix, "Address", "City Name"): city,
            (*prefix, "Address", "Address (Line 1)"): street, (*prefix, "Address", "Postal Code"): postcode,
            (*prefix, "Address", "Address Use"): "work",
            (*prefix, "Organization Identifier", "Identifier Value"): ident,
            (*prefix, "Organization Identifier", "Issuing Authority"): "Synthetic Registry"}


def build(template, instance_id, created, values, report, times=None):
    """A child record: the template filled with `values` (label paths below the data cluster), its subject (and
    provider) the report's, every element without a value removed."""
    root = copy.deepcopy(template.getroot())
    root_label = root.findtext("dm-label")
    root.find("instance_id").text = instance_id
    root.find("creation_timestamp").text = created
    root.find("instance_version").text = "1"
    for name in ("source_instance_id", "source_version_id", "current-state"):
        if root.find(name) is not None:
            root.remove(root.find(name))
    for part in ("subject", "provider"):
        if root.find(part) is not None:
            root.find(part).append(copy.deepcopy(report.find(f"{part}/party-details")))
    for p in root.findall("sdc4:*", {"sdc4": SDC4}):
        if p.find("performer") is not None:
            start, end = (times or {}).get(label(p), (None, None))
            if start is None:
                root.remove(p)
            else:
                p.find("start").text, p.find("end").text = start, end
    used = set()
    for el in [e for e in root.iter() if isinstance(e.tag, str) and is_leaf(e)]:
        if el.getparent() is None:
            continue
        if any(a.tag in ("subject", "provider") for a in el.iterancestors()):
            continue                                   # the report's details, copied whole
        p = path_of(el, root_label)
        if p in values:
            used.add(p)
            value = values[p]
            if isinstance(value, dict) and "EV" in value:     # an Exceptional Value beside the quantity's units
                fill(el, f"EV:{value['EV']}")
                for u in el.iter():
                    if u.text == "_PH_" and any(a.tag in UNITS for a in u.iterancestors()):
                        u.text = value["units"]
            else:
                fill(el, value)
            continue
        if el.find("link") is not None and el.find("link").text != "_PH_":
            continue                                   # a fixed code system: kept only beside a code (below)
        holder = el.getparent()
        holder.getparent().remove(holder) if holder.tag.startswith(f"{{{SDC4}}}ms-") and len(holder) == 1 \
            else holder.remove(el)
    missing = set(values) - used
    if missing:
        raise ValueError(f"{instance_id}: no element for {sorted(missing)}")
    for el in [e for e in root.iter() if isinstance(e.tag, str) and is_leaf(e) and e.find("link") is not None]:
        cluster = next(a for a in el.iterancestors() if label(a) is not None)
        if not any(is_leaf(d) and d.find("link") is None for d in cluster.iter()):
            holder = el.getparent()
            holder.getparent().remove(holder)
    for c in list(root.iter()):
        if isinstance(c.tag, str) and c.text == "_OPT_PH_":
            c.getparent().remove(c)
    prune(root)
    left = [e for e in root.iter() if isinstance(e.tag, str) and e.text in ("_PH_", "_OPT_PH_")]
    if left:
        raise ValueError(f"{instance_id}: placeholders left at {[path_of(e.getparent(), root_label) for e in left][:5]}")
    etree.indent(root, space="  ")
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8") + b"\n"


def chain(n: int, templates, report_file: Path):
    report = etree.parse(str(report_file)).getroot()
    record_id = f"LR-2026-{1000 + n}"
    assert report.findtext(".//{%s}ms-h17egwljmrym3r8ortrqqjwd/xdstring-value" % SDC4) == record_id, report_file
    day = f"2026-10-{n + 1:02d}"
    ordered = f"{day}T07:00:00+01:00"            # the report's Order Placer Participation starts then
    collected = f"{day}T07:30:00+01:00"
    performed = f"{day}T08:15:00+01:00"
    labo = LABS[n % len(LABS)]
    collector = PROFESSIONALS[(n + 2) % len(PROFESSIONALS)]
    spec_id, req_id = iid(n, "spc", 1), iid(n, "srq", 1)
    out = []

    out.append(("order-information", iid(n, "ord", 1), {
        ("Parent Record Identifier",): record_id,
        ("Order Identifier", "Identifier Value"): f"ORD-2026-{5000 + n}",
        ("Order Identifier", "Issuing Authority"): labo[0],
        ("Order Authored Date",): ordered,
        ("Order Reason (SNOMED CT)", "Order Reason Code (SNOMED CT)"): DIABETES[0],
        ("Order Reason (SNOMED CT)", "Code Display Text"): DIABETES[1],
        ("Clinical Question",): "Synthetic sample: glycaemic control and renal function?",
    }, None))
    out.append(("specimen", spec_id, {
        ("Accession Identifier",): f"ACC-2026-{7000 + n}",
        ("Specimen Type (SNOMED CT)", "Specimen Type Code (SNOMED CT)"): SERUM[0],
        ("Specimen Type (SNOMED CT)", "Code Display Text"): SERUM[1],
        ("Specimen Status",): "available",
        ("Received Date Time",): f"{day}T07:50:00+01:00",
        ("Specimen Request Reference",): [iri(req_id)],
        **professional(collector, ("Specimen Collector Participation", "Specimen Collector", "Health Professional")),
        ("Specimen Collector Participation", "Participation Function (Specimen Collector)"): "specimen collector",
    }, {"Specimen Collector Participation": (collected, collected)}))
    out.append(("service-request", req_id, {
        ("Parent Record Identifier",): record_id,
        ("Record Identifier", "Identifier Value"): f"SR-2026-{6000 + n}",
        ("Record Identifier", "Issuing Authority"): labo[0],
        ("Request Status",): "completed",
        ("Request Priority",): "routine",
        ("Authored Date",): day,
        ("Order (LOINC)", "Order Code (LOINC)"): LOINC_PANEL[0],
        ("Order (LOINC)", "Code Display Text"): LOINC_PANEL[1],
        ("Service Request Specimen Reference",): [iri(spec_id)],
    }, None))
    for j, (code, display, units, low, high, method) in enumerate(RESULTS, 1):
        value = VALUES[n][j - 1]
        pending = value.startswith("EV:")
        v = {
            ("Parent Record Identifier",): record_id,
            ("Record Identifier", "Identifier Value"): f"OBS-2026-{n}-{j}",
            ("Record Identifier", "Issuing Authority"): labo[0],
            ("Observation Status",): "preliminary" if pending else "final",
            ("Result Code (LOINC)", "Result Code Code (LOINC)"): code,
            ("Result Code (LOINC)", "Code Display Text"): display,
            ("Observation Date Time",): performed,
            # the model's quantity units hold one text, "UCUM Units", and no UCUM code (a library finding): the unit
            # the result is in (`units`, looked up) cannot be recorded
            ("Observation Result", "Result Quantity"): {"EV": value[3:], "units": MODEL_UNITS} if pending else
            {"xdquantity-value": value, "xdquantity-units/xdstring-value": MODEL_UNITS},
            # the model requires a data absent reason beside every result, a value or not, and a required component
            # takes no Exceptional Value (a library finding): for a result with a value it is `not-applicable`
            ("Observation Result", "Data Absent Reason"): "temp-unknown" if pending else "not-applicable",
            ("Observation Method (SNOMED CT)", "Observation Method Code (SNOMED CT)"): method[0],
            ("Observation Method (SNOMED CT)", "Code Display Text"): method[1],
            ("Note",): "Synthetic sample result." if not pending else "Synthetic sample: result to follow.",
            # required by the model: the test kit (the IRI of a record outside the chain) and the calibrator
            ("Lab Observation Test Kit Reference",): f"urn:sdc4:record:testkit{n}{j}",
            ("Lab Observation Calibrator", "Identifier Value"): f"CAL-{code}-2026",
            ("Lab Observation Calibrator", "Issuing Authority"): labo[0],
            ("Observation Specimen Reference",): iri(spec_id),
            ("Observation Order Reference",): iri(req_id),
            **lab(labo, ("Performer Participation", "Performer", "Organisation")),
            ("Performer Participation", "Participation Function (Performer)"): "performer",
        }
        # required by the model, so never an Exceptional Value: a pending result is IND (indeterminate)
        v[("Interpretation Code",)] = "IND" if pending else \
            ("H" if float(value) > high else ("L" if float(value) < low else "N"))
        out.append(("lab-observation", iid(n, "obs", j), v, {"Performer Participation": (performed, performed)}))
    files = []
    for kind, instance_id, values, times in out:
        files.append((kind, instance_id, build(templates[kind], instance_id, performed, values, report, times)))
    return files


def main() -> int:
    from sdc_mapper.gate import SDC4_XSD
    from sdcvalidator import build_xsd11_schema

    def local(url: str) -> str:
        return str(SDC4_XSD) if url.rstrip("/").endswith("/ns/sdc4/sdc4.xsd") else url

    parser = etree.XMLParser(resolve_entities=False, no_network=True)
    schemas, templates = {}, {}
    for kind, ct in MODELS.items():
        d = ROOT / "samples" / f"sdchealth-{kind}"
        schemas[kind] = build_xsd11_schema(str(d / f"dm-{ct}.xsd"), uri_mapper=local)
        templates[kind] = etree.parse(str(d / "template" / f"dm-{ct}.xml"), parser)
    reports = sorted((REPORT / "records").glob("*.xml"))
    bad = 0
    for n in range(SETS):
        d = OUT / f"chain-{n:02d}"
        d.mkdir(parents=True, exist_ok=True)
        for old in d.glob("*.xml"):
            old.unlink()
        manifest = {"parent": str(reports[n].relative_to(ROOT)), "parent_ct_id": "zptekdommw56yiz9lqjy5dga",
                    "children": []}
        for kind, instance_id, xml in chain(n, templates, reports[n]):
            errors = list(schemas[kind].iter_errors(xml.decode("utf-8")))
            if errors:
                bad += 1
                print(f"chain {n} {kind} {instance_id}: {errors[0].reason} at {errors[0].path}", file=sys.stderr)
                continue
            (d / f"{instance_id}.xml").write_bytes(xml)
            manifest["children"].append({"file": f"{instance_id}.xml", "model": kind, "ct_id": MODELS[kind]})
        (d / "chain.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"{SETS} chains written to {OUT.relative_to(ROOT)}; {bad} record(s) failed their model's XSD 1.1 schema")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
