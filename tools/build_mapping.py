"""Author a FHIR mapping file from a spec written in the model's labels.

    python tools/build_mapping.py nhanes_participant samples/nhanes-participant xy8upneajsb8vdcmnve01g6g

A spec (tools/specs/<name>.py) names clusters and components by label, as a person reads the model; this script
resolves every label to the components' identifiers (a label used by several components gives a rule for each),
writes the mapping file sdc-mapper reads (src/sdc_gdr2fhir/mappings/<name>-<ct_id>.yaml, every rule commented with its
labels), and checks that every value the model can hold reaches a rule: placed, or omitted with a reason. The
published mapping file is the YAML; the spec is how it was written.

A spec entry may carry `derive`: a function of the component (and the model's enumeration definitions) that returns
more of the rule, so what the model binds (a LOINC code, an answer's code, the component's own identifier) is copied
from the model into the mapping file rather than typed into it.
"""
from __future__ import annotations

import importlib.util
import itertools
import sys
from pathlib import Path

import yaml

from sdc_mapper import load_mapping
from sdcreader import load_package, read_model

ROOT = Path(__file__).resolve().parents[1]
SDC4 = "https://semanticdatacharter.com/ns/sdc4/"


def load_spec(name: str):
    specs = ROOT / "tools" / "specs"
    if str(specs) not in sys.path:
        sys.path.insert(0, str(specs))            # a spec composes the shared rules in specs/common.py
    path = specs / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"spec_{name}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def walk(model):
    """Every component reachable from the model's root, with the clusters above it (identifiers, root first)."""
    out = []

    def go(c, above):
        out.append((c, above))
        for k in c.contains or []:
            go(model.components[k] if isinstance(k, str) else k, above + [c.ct_id])
    go(model.root, [])
    return out


def enumerations(xsd: Path) -> dict[str, list[tuple[str, str | None]]]:
    """Each enumerated component's values with the IRI each is defined by, from the model's schema."""
    from lxml import etree
    rdf, rdfs = "http://www.w3.org/1999/02/22-rdf-syntax-ns#", "http://www.w3.org/2000/01/rdf-schema#"
    out: dict[str, list] = {}
    for e in etree.parse(str(xsd)).iter("{http://www.w3.org/2001/XMLSchema}enumeration"):
        c = e.find(f".//{{{rdfs}}}Class")
        if c is None:
            continue
        ct = c.get(f"{{{rdf}}}about").split("/mc-", 1)[1].split("/", 1)[0]
        out.setdefault(ct, []).append((e.get("value"), e.findtext(f".//{{{rdfs}}}isDefinedBy")))
    return out


def main(name: str, sample: str, ct_id: str) -> int:
    spec = load_spec(name)
    pkg = load_package(ROOT / sample, ct_id)
    model = read_model(pkg)
    reach = walk(model)
    enums = enumerations(ROOT / sample / f"dm-{ct_id}.xsd")
    clusters: dict[str, set[str]] = {}
    leaves: dict[str, set[str]] = {}
    for c, _ in reach:
        (clusters if c.sdc_type == "Cluster" else leaves).setdefault(c.label, set()).add(c.ct_id)

    skipped = []

    def ids(table, label):
        """The identifiers of the components with a label; a label this model does not use (a rule shared by every
        library document) gives none, and is listed, so a misspelled label shows."""
        if label not in table:
            skipped.append(f"{'cluster' if table is clusters else 'component'} {label!r}")
            return []
        return sorted(table[label])

    lines = [
        f"# {spec.TITLE}",
        "# Written by tools/build_mapping.py from tools/specs/" + name + ".py; labels in the comments.",
        yaml.safe_dump({"mapping": {"id": spec.ID, "version": spec.VERSION, "author": spec.AUTHOR, "date": spec.DATE,
                                    "description": spec.DESCRIPTION},
                        "model": {"ct_id": ct_id, "schema_sha256": pkg.sha256},
                        "target": {"name": "HL7 FHIR", "version": "R4"}}, sort_keys=False, width=120).rstrip(),
        "rules:",
    ]
    count = 0
    for entry in spec.RULES:
        entry = dict(entry)
        kind = "cluster" if "cluster" in entry else "component"
        label = entry.pop(kind)
        within = entry.pop("within", [])
        derive = entry.pop("derive", None)
        listuri = entry.pop("listURI", False)
        iri_to = entry.pop("iri_to", None)       # a path that names the component itself, by its published IRI
        targets = ids(clusters if kind == "cluster" else leaves, label)
        contexts = list(itertools.product(*[ids(clusters, w) for w in within])) if within else [()]
        for target, ctx in itertools.product(targets, contexts):
            rule = {kind: target}
            if ctx:
                rule["within"] = list(ctx)
            rule.update(entry)
            if derive:
                for k, val in derive(model.components[target], enums.get(target, [])).items():
                    rule[k] = [*rule.get(k, []), *val] if k == "also" else ({**rule.get(k, {}), **val} if k == "attributes" else val)
            if listuri:   # the list a token travels with is the component itself, as published
                rule["attributes"] = {**rule.get("attributes", {}), "listURI": f"{SDC4}mc-{target}"}
            if iri_to:
                rule["also"] = [*rule.get("also", []), {"to": iri_to, "transform": "constant", "value": f"{SDC4}mc-{target}"}]
            note = label + (f" (within {' > '.join(within)})" if within else "")
            lines.append(f"  # {note}")
            lines.append("  - " + yaml.safe_dump(rule, sort_keys=False, default_flow_style=True, width=10_000,
                                                 allow_unicode=True).strip())
            count += 1
    out = ROOT / "src" / "sdc_gdr2fhir" / "mappings" / f"{name}-{ct_id}.yaml"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    mapping = load_mapping(out)

    # every value the model can hold reaches a rule
    unreached = []
    for c, above in reach:
        if c.sdc_type == "Cluster":
            continue
        omitted = any(
            (r := mapping.cluster_rule(cid, above[:i])) is not None and r.transform == "omit"
            for i, cid in enumerate(above))
        if not omitted and mapping.rule_for(c.ct_id, c.sdc_type, above) is None:
            unreached.append(" / ".join(model.components[a].label for a in above[1:]) + f" / {c.label}")
    print(f"{out.relative_to(ROOT)}: {count} rules")
    if skipped:
        print(f"  labels not in this model (no rule written): {', '.join(sorted(set(skipped)))}")
    if unreached:
        print(f"{len(unreached)} value(s) reach no rule:")
        for u in unreached:
            print("  ", u)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
