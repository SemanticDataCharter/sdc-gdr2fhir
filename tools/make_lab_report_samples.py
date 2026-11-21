"""Write the synthetic sample records of the SDCHealth Laboratory Report model, and check each against the model's schema.

    python tools/make_lab_report_samples.py

The records are made up: no person, professional, organisation or report in them is real. Each is the instance
template SDCStudio publishes with the model (samples/sdchealth-lab-report/template/, the catalog's `xml` artifact),
filled in: a value where the record has one, an Exceptional Value where it says why one is missing, and every optional
element it has no value for removed. The template's subject and provider carry no party details (SDCStudio's template
writer leaves them out), so the Patient and Author details are written here from the Patient and Health Professional
clusters the model's Parties name, in the template's own shape (the intended recipient's and the attester's).

Every LOINC and SNOMED CT code used was looked up on HL7's terminology server (tx.fhir.org, 20 November 2026; see the
sample README), not written from memory, and is used only where the model allows a code of that system.

Each record is validated against the model's XSD 1.1 schema (sdcvalidator's `build_xsd11_schema`, the SDC4 reference
schema mapped to the copy sdc-mapper ships); a record that fails is not written.
"""
from __future__ import annotations

import copy
import sys
import uuid
from pathlib import Path

from lxml import etree

ROOT = Path(__file__).resolve().parents[1]
CT = "zptekdommw56yiz9lqjy5dga"
DIR = ROOT / "samples" / "sdchealth-lab-report"
SDC4 = "https://semanticdatacharter.com/ns/sdc4/"
NS = {"sdc4": SDC4}
EV_NAMES = {"UNK": "Unknown", "ASKU": "Asked but Unknown", "ASKR": "Asked and Refused", "NASK": "Not Asked",
            "NAV": "Not Available", "MSK": "Masked", "NI": "No Information", "NA": "Not Applicable"}
UNITS = {"xdcount-units", "xdquantity-units"}
#: The DM-level elements of the record that hold parties, a workflow or an attestation, by the label each carries.
STRUCTURAL = {"subject", "provider", "performer", "party-details", "committer", "attestation", "workflow"}


def label(el) -> str | None:
    lab = el.find("label")
    return lab.text if lab is not None else None


def is_leaf(el) -> bool:
    """A data-bearing component: it has a label, and nothing below it but its units has one."""
    if el.find("label") is None or el.tag in STRUCTURAL or el.tag in UNITS:
        return False
    if all(c.tag == "label" for c in el if isinstance(c.tag, str)):      # a cluster left with nothing in it
        return False
    for d in el.iterdescendants():
        if isinstance(d.tag, str) and d.tag == "label" and d.getparent() is not el and d.getparent().tag not in UNITS:
            return False
    return True


def path_of(el) -> tuple[str, ...]:
    out = []
    for a in [el, *el.iterancestors()]:
        lab = label(a)
        if lab is not None:
            out.append(lab)
    out.reverse()
    return tuple(out[1:] if out and out[0] == "Laboratory Report" else out)   # the data cluster's label is implied


def ev(el, code: str):
    """Replace a leaf's value by an Exceptional Value, in the place the SDC4 schema gives it (after label and act)."""
    for c in list(el):
        if c.tag not in ("label", "act") and c.tag not in UNITS:
            el.remove(c)
    e = etree.Element(f"{{{SDC4}}}{code}")
    etree.SubElement(e, "ev-name").text = EV_NAMES[code]
    at = 1 + (el.find("act") is not None)
    el.insert(at, e)


def fill(el, value):
    """Write a value in a leaf: the template's placeholders say where; optional placeholders are removed."""
    if isinstance(value, str) and value.startswith("EV:"):
        ev(el, value[3:])
        return
    for c in list(el.iter()):
        if c is not el and c.text == "_OPT_PH_":
            c.getparent().remove(c)
    holders = [c for c in el.iter() if c.text == "_PH_"]
    if el.find("xdstringlist-value") is not None:                  # a list: one element per item
        first = el.find("xdstringlist-value")
        at = list(el).index(first)
        el.remove(first)
        for i, item in enumerate(value):
            n = etree.Element("xdstringlist-value")
            n.text = item
            el.insert(at + i, n)
        return
    if el.find("true-value") is not None or el.find("false-value") is not None:
        old = el.find("true-value") if el.find("true-value") is not None else el.find("false-value")
        old.tag = "true-value" if value == "true" else "false-value"
        old.text = value
        return
    if isinstance(value, dict):                                     # several parts: {element: text}
        for name, text in value.items():
            target = el.find(name)
            if target is None:
                raise ValueError(f"{path_of(el)}: no element {name}")
            target.text = text
        for h in holders:
            if h.text == "_PH_":
                raise ValueError(f"{path_of(el)}: {h.tag} has no value")
        return
    main = [h for h in holders if h.getparent() is el]
    if len(main) != 1:
        raise ValueError(f"{path_of(el)}: {len(main)} value placeholders")
    h = main[0]
    if h.tag == "xdtemporal-date" and "T" in value:
        h.tag = "xdtemporal-datetime"
    h.text = value
    for u in holders:
        if u is not h and u.text == "_PH_":                         # a count's units: the model's one symbol
            u.text = "B"


def prune(el):
    """Remove the clusters (and their adapters) left with no value."""
    changed = True
    while changed:
        changed = False
        for c in list(el.iter()):
            if not isinstance(c.tag, str) or not c.tag.startswith(f"{{{SDC4}}}ms-") or c.getparent() is None:
                continue
            has_value = any(is_leaf(d) for d in c.iter())
            if not has_value:
                c.getparent().remove(c)
                changed = True


# ---------------------------------------------------------------- the synthetic people, organisations and reports
PERSONS = [
    # given, surname, gender, birth date, country, city, street, postcode, identifier, issuing authority
    ("Ana", "Ferreira", "female", "1984-03-12", "PT", "Lisboa", "Rua das Flores 12", "1200-195", "PT-SNS-900000101", "SNS"),
    ("Jonas", "Becker", "male", "1957-11-02", "DE", "Leipzig", "Lindenstraße 4", "04109", "DE-KV-A900000102", "GKV"),
    ("Marta", "Kowalska", "female", "1992-06-30", "PL", "Kraków", "ul. Długa 7", "31-147", "PL-PESEL-900000103", "MSWiA"),
    ("Luca", "Bianchi", "male", "1975-01-21", "IT", "Bologna", "Via Indipendenza 33", "40121", "IT-CF-900000104", "AdE"),
    ("Sofie", "Jansen", "female", "2001-09-08", "NL", "Utrecht", "Oudegracht 210", "3511 NR", "NL-BSN-900000105", "RvIG"),
]
PROFESSIONALS = [
    ("Elena", "Moreau", "Dr.", "FR", "Lyon", "Rue de la République 5", "69002", "FR-RPPS-800000201", "ANS"),
    ("Pieter", "de Vries", "Dr.", "NL", "Utrecht", "Heidelberglaan 100", "3584 CX", "NL-BIG-800000202", "CIBG"),
    ("Katarzyna", "Nowak", "Dr.", "PL", "Kraków", "ul. Kopernika 19", "31-501", "PL-NPWZ-800000203", "NIL"),
]
LABS = [
    ("Synthetic Central Laboratory", "prov", "PT", "Lisboa", "Avenida da Liberdade 100", "1250-146", "LAB-900301"),
    ("Example Regional Hospital Laboratory", "dept", "DE", "Leipzig", "Liebigstraße 20", "04103", "LAB-900302"),
]
#: Looked up on tx.fhir.org, 20 November 2026 (LOINC 2.83; SNOMED CT International 20260701): every one active.
LOINC_LAB_REPORT = ("11502-2", "Laboratory report")
EVENT_LAB_TEST = ("15220000", "Laboratory test")
SETTINGS = [("394915009", "General pathology (specialty)"), ("394596001", "Chemical pathology"),
            ("408454008", "Clinical microbiology"), ("394595002", "Pathology")]


def person_details(p, prefix, *, gender=True, contact=None):
    given, surname, sex, born, country, city, street, postcode, ident, authority = p
    out = {
        (*prefix, "Address", "Country", "Country Code ISO 3166"): country,
        (*prefix, "Address", "City Name"): city,
        (*prefix, "Address", "Address (Line 1)"): street,
        (*prefix, "Address", "Postal Code"): postcode,
        (*prefix, "Address", "Address Use"): "home",
        (*prefix, "Human Name", "Given Name (Person)"): given,
        (*prefix, "Human Name", "Surname (Person)"): surname,
        (*prefix, "Human Name", "Name Use"): "official",
        (*prefix, "Person Identifier", "Identifier Value"): ident,
        (*prefix, "Person Identifier", "Issuing Authority"): authority,
        (*prefix, "Person Identifier", "Person Identifier Type"): "NI",
    }
    if gender:
        out[(*prefix, "Administrative Gender")] = sex
        out[(*prefix, "Date of Birth")] = born
    if contact:
        out[(*prefix, "Telecom", "Phone Number")] = contact
        out[(*prefix, "Telecom", "Contact Method")] = "phone"
        out[(*prefix, "Telecom", "Contact Use")] = "mobile"
    return out


def professional_details(h, prefix):
    given, surname, title, country, city, street, postcode, ident, authority = h
    return {
        (*prefix, "Address", "Country", "Country Code ISO 3166"): country,
        (*prefix, "Address", "City Name"): city,
        (*prefix, "Address", "Address (Line 1)"): street,
        (*prefix, "Address", "Postal Code"): postcode,
        (*prefix, "Address", "Address Use"): "work",
        (*prefix, "Human Name", "Given Name (Person)"): given,
        (*prefix, "Human Name", "Surname (Person)"): surname,
        (*prefix, "Human Name", "Name Prefix"): title,
        (*prefix, "Person Identifier", "Identifier Value"): ident,
        (*prefix, "Person Identifier", "Issuing Authority"): authority,
        (*prefix, "Telecom", "Phone Number"): "+351 210 000 000",
        (*prefix, "Telecom", "Contact Method"): "phone",
        (*prefix, "Telecom", "Contact Use"): "work",
    }


def lab_details(o, prefix):
    name, kind, country, city, street, postcode, ident = o
    return {
        (*prefix, "Organization Name"): name,
        (*prefix, "Organization Type"): kind,
        (*prefix, "Address", "Country", "Country Code ISO 3166"): country,
        (*prefix, "Address", "City Name"): city,
        (*prefix, "Address", "Address (Line 1)"): street,
        (*prefix, "Address", "Postal Code"): postcode,
        (*prefix, "Address", "Address Use"): "work",
        (*prefix, "Organization Identifier", "Identifier Value"): ident,
        (*prefix, "Organization Identifier", "Issuing Authority"): "Synthetic Registry",
    }


def record(n: int):
    """The values of sample n: a dict of label paths to values, the workflow state, and the participation times."""
    patient = PERSONS[n % len(PERSONS)]
    author = PROFESSIONALS[n % len(PROFESSIONALS)]
    attester = PROFESSIONALS[(n + 1) % len(PROFESSIONALS)]
    placer = PROFESSIONALS[(n + 2) % len(PROFESSIONALS)]
    lab = LABS[n % len(LABS)]
    setting = SETTINGS[n % len(SETTINGS)]
    day = f"2026-10-{n + 1:02d}"
    authored = f"{day}T{9 + n % 8:02d}:{(7 * n) % 60:02d}:00+01:00"
    LR = ()
    v = {
        ("Document Header Title",): "Laboratory report",
        ("Document Type (LOINC)", "Code System: LOINC"): None,          # fixed in the model: written as is
        ("Document Type (LOINC)", "Document Type Code (LOINC)"): LOINC_LAB_REPORT[0],
        ("Document Type (LOINC)", "Code Display Text"): LOINC_LAB_REPORT[1],
        ("Record Identifier", "Identifier Value"): f"LR-2026-{1000 + n}",
        ("Record Identifier", "Issuing Authority"): lab[0],
        ("Version",): "1",
        ("Authored Date",): authored,
        ("Practice Setting (SNOMED CT)", "Code System: SNOMED CT"): None,
        ("Practice Setting (SNOMED CT)", "Practice Setting Code (SNOMED CT)"): setting[0],
        ("Practice Setting (SNOMED CT)", "Code Display Text"): setting[1],
        ("Document Event Type (SNOMED CT)", "Code System: SNOMED CT"): None,
        ("Document Event Type (SNOMED CT)", "Document Event Type Code (SNOMED CT)"): EVENT_LAB_TEST[0],
        ("Document Event Type (SNOMED CT)", "Code Display Text"): EVENT_LAB_TEST[1],
        ("Document Period", "Document Period Start"): f"{day}T07:30:00+01:00",
        ("Document Period", "Document Period End"): authored,
        ("Lab Report Body", "Lab Report Result Data Section",
         "Lab Report Result Data Comments Interpretation And Recommendations"):
            "Synthetic sample: all results within the laboratory's reference intervals. No follow-up advised.",
        ("Lab Report Body", "Lab Report Supporting Information Section", "Sex For Clinical Use"):
            {"female": "female-typical", "male": "male-typical"}[patient[2]],
    }
    # the report as a document (the model requires an Attachment: the report's presented form)
    v[("Attachment", "Document Title")] = "Laboratory report (PDF)"
    # a URN, not a web address: HL7's validator refuses example URLs, and a made-up host could be someone's
    v[("Attachment", "Document URL")] = f"urn:uuid:{uuid.uuid5(uuid.NAMESPACE_URL, f'synthetic-lab-report-LR-2026-{1000 + n}')}"
    v[("Attachment", "Media Type")] = "application/pdf"
    if n % 3 == 0:
        v[("Attachment", "Document Size")] = str(20480 + 512 * n)
    if n % 4 == 1:
        v[("Lab Report Body", "Lab Report Supporting Information Section",
           "Lab Report Supporting Information Other Supporting Information Reference")] = [
            f"urn:uuid:5e1c0a4e-0000-4000-8000-{n:012d}"]
    if n % 5 == 2:          # an amended report: its second version
        v[("Version",)] = "2"
    # Exceptional Values, where a record says why it has no value
    if n == 4:
        v[("Lab Report Body", "Lab Report Supporting Information Section", "Sex For Clinical Use")] = "EV:ASKU"
    if n == 7:
        v[("Lab Report Body", "Lab Report Result Data Section",
           "Lab Report Result Data Comments Interpretation And Recommendations")] = "EV:NAV"
    if n == 10:
        v[("Document Event Type (SNOMED CT)", "Document Event Type Code (SNOMED CT)")] = "EV:UNK"
        del v[("Document Event Type (SNOMED CT)", "Code Display Text")]

    v.update(person_details(patient, ("Patient", "Patient")))
    if n == 5:
        v[("Patient", "Patient", "Date of Birth")] = "EV:ASKR"
    v.update(professional_details(author, ("Author", "Health Professional")))
    v.update(professional_details(attester, ("Attester Participation", "Attester", "Health Professional")))
    v[("Attester Participation", "Participation Function (Attester)")] = "attester"
    v.update(lab_details(lab, ("Custodian Participation", "Custodian", "Organisation")))
    v[("Custodian Participation", "Participation Function (Custodian)")] = "custodian"
    # the patient receives the report: the same person, with the birth date PatientEuCore requires
    v.update(person_details(patient, ("Intended Recipient Participation", "Intended Recipient", "Patient"),
                            gender=False, contact="+351 910 000 000"))
    v[("Intended Recipient Participation", "Intended Recipient", "Patient", "Date of Birth")] = (
        "EV:ASKR" if n == 5 else patient[3])
    v[("Intended Recipient Participation", "Participation Function (Intended Recipient)")] = "intended recipient"
    v.update(professional_details(placer, ("Order Placer Participation", "Order Placer", "Health Professional")))
    v[("Order Placer Participation", "Participation Function (Order Placer)")] = "order placer"
    v.update(professional_details(attester, ("Legal Authentication", "Legal Authenticator", "Health Professional")))
    v[("Legal Authentication", "Attestation Reason")] = "Legal authentication of the laboratory report"
    times = {"Attester Participation": (authored, authored), "Custodian Participation": (authored, authored),
             "Intended Recipient Participation": (authored, authored),
             "Order Placer Participation": (f"{day}T07:00:00+01:00", f"{day}T07:00:00+01:00")}
    state = ("Main path", "1", "final") if n % 5 != 2 else ("Main path", "2", "amended")
    if n == 13:
        state = ("Main path", "0", "preliminary")
    return v, state, times, authored


# ---------------------------------------------------------------- the record
def instance_id(n: int) -> str:
    return f"labrep{n:02d}synth" + "x" * (24 - len(f"labrep{n:02d}synth"))


def build(n: int, template: etree._ElementTree) -> bytes:
    values, state, times, authored = record(n)
    root = copy.deepcopy(template.getroot())
    root.find("instance_id").text = instance_id(n)
    root.find("creation_timestamp").text = authored
    root.find("instance_version").text = "1"
    for name in ("source_instance_id", "source_version_id"):
        root.remove(root.find(name))
    root.find("current-state").text = state[2]

    # subject and provider: the details the template leaves out, in the template's shape
    recipient = root.find("sdc4:ms-q5g9nqjxzj0su0rpn8icgqjc/performer/party-details", NS)
    attester = root.find("sdc4:ms-e7jes8an7n8t58qyabk1nnm2/performer/party-details", NS)
    root.find("subject").append(copy.deepcopy(recipient))
    root.find("provider").append(copy.deepcopy(attester))
    # the attestation: reason, committer (the legal authenticator), when, and not pending
    att = root.find("attestation")
    pending = att.find("pending")
    reason = etree.Element("reason")
    etree.SubElement(reason, "label").text = "Attestation Reason"
    etree.SubElement(reason, "xdstring-value").text = "_PH_"
    committer = etree.Element("committer")
    etree.SubElement(committer, "label").text = "Legal Authenticator"
    committer.append(copy.deepcopy(attester))
    committed = etree.Element("committed")
    committed.text = authored
    for i, e in enumerate((reason, committer, committed)):
        att.insert(list(att).index(pending), e)
    pending.text = "false"
    # participation times
    for p in root.findall("sdc4:*", NS):
        if label(p) in times:
            p.find("start").text, p.find("end").text = times[label(p)]
    # the workflow: the one path the record is on, at its state
    wf = root.find("workflow")
    for path in list(wf):
        if path.tag == "label":
            continue
        if label(path) != f"Clinical Document: {state[0]}":
            wf.remove(path)
        else:
            leaf = next(e for e in path.iter() if is_leaf(e))
            leaf.find("ordinal").text, leaf.find("symbol").text = state[1], state[2]

    used = set()
    for el in [e for e in root.iter() if isinstance(e.tag, str) and is_leaf(e)]:
        p = path_of(el)
        if p and p[0].startswith("Clinical Document"):
            used.add(p)
            continue
        if p in values:
            used.add(p)
            if values[p] is not None:
                fill(el, values[p])
            continue
        if el.find("link") is not None and el.find("link").text != "_PH_":
            # a fixed code system link: kept only beside a code
            continue
        holder = el.getparent()
        holder.getparent().remove(holder) if holder.tag.startswith(f"{{{SDC4}}}ms-") and len(holder) == 1 else holder.remove(el)
    missing = set(values) - used
    if missing:
        raise ValueError(f"sample {n}: no element for {sorted(missing)}")
    # fixed code-system links stay only in a coded cluster that still has its code
    for el in [e for e in root.iter() if isinstance(e.tag, str) and is_leaf(e) and e.find("link") is not None]:
        cluster = next(a for a in el.iterancestors() if label(a) is not None)
        if not any(is_leaf(d) and d.find("link") is None for d in cluster.iter()):
            holder = el.getparent()
            holder.getparent().remove(holder)
    for c in list(root.iter()):
        if isinstance(c.tag, str) and c.text in ("_OPT_PH_",):
            c.getparent().remove(c)
    prune(root)
    left = [e for e in root.iter() if isinstance(e.tag, str) and e.text in ("_PH_", "_OPT_PH_")]
    if left:
        raise ValueError(f"sample {n}: placeholders left at {[path_of(e.getparent()) for e in left][:5]}")
    etree.indent(root, space="  ")
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8") + b"\n"


def main(count: int = 15) -> int:
    from sdc_mapper.gate import SDC4_XSD
    from sdcvalidator import build_xsd11_schema

    def local(url: str) -> str:
        return str(SDC4_XSD) if url.rstrip("/").endswith("/ns/sdc4/sdc4.xsd") else url

    schema = build_xsd11_schema(str(DIR / f"dm-{CT}.xsd"), uri_mapper=local)
    template = etree.parse(str(DIR / "template" / f"dm-{CT}.xml"),
                           etree.XMLParser(resolve_entities=False, no_network=True))
    out = DIR / "records"
    out.mkdir(exist_ok=True)
    for old in out.glob("*.xml"):
        old.unlink()
    bad = 0
    for n in range(count):
        xml = build(n, template)
        errors = list(schema.iter_errors(xml.decode("utf-8")))
        if errors:
            bad += 1
            print(f"sample {n}: {errors[0].reason} at {errors[0].path}", file=sys.stderr)
            continue
        (out / f"{instance_id(n)}.xml").write_bytes(xml)
    print(f"{count - bad} of {count} records written to {out.relative_to(ROOT)}, each valid against the model's XSD 1.1")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
