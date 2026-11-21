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


def data_cluster(xsd: Path, ct_id: str) -> str:
    """The model's data cluster: the one `ms-` element the model's own complex type names. A record's values are read
    from it (sdcreader 4.4.1 reads nothing outside it). It is not always sdcreader's `model.root`, which is the largest
    uncontained cluster: in a model whose parties have details clusters (SDCHealth), a details cluster can be larger
    than the data cluster."""
    from lxml import etree
    xs = "{http://www.w3.org/2001/XMLSchema}"
    t = etree.parse(str(xsd)).find(f"{xs}complexType[@name='mc-{ct_id}']")
    refs = [e.get("ref").split(":ms-", 1)[1] for e in t.iter(f"{xs}element") if (e.get("ref") or "").startswith("sdc4:ms-")]
    if len(refs) != 1:
        raise ValueError(f"model {ct_id}: {len(refs)} data clusters in its complex type")
    return refs[0]


def walk(model, root=None):
    """Every component reachable from the model's data cluster, with the clusters above it (identifiers, root
    first)."""
    out = []

    def go(c, above):
        out.append((c, above))
        for k in c.contains or []:
            go(model.components[k] if isinstance(k, str) else k, above + [c.ct_id])
    go(model.components[root] if root else model.root, [])
    return out


def enumerations(xsd: Path) -> dict[str, list[tuple[str, str | None]]]:
    """Each enumerated component's values with the IRI each is defined by, from the model's schema."""
    from lxml import etree
    rdf, rdfs = "http://www.w3.org/1999/02/22-rdf-syntax-ns#", "http://www.w3.org/2000/01/rdf-schema#"
    out: dict[str, list] = {}
    xs = "{http://www.w3.org/2001/XMLSchema}"
    for e in etree.parse(str(xsd)).iter(f"{xs}enumeration"):
        c = e.find(f".//{{{rdfs}}}Class")
        if c is not None:
            ct = c.get(f"{{{rdf}}}about").split("/mc-", 1)[1].split("/", 1)[0]
            out.setdefault(ct, []).append((e.get("value"), e.findtext(f".//{{{rdfs}}}isDefinedBy")))
            continue
        # an ordinal's states: `rdfs:isDefinedBy rdf:resource` with no rdfs:Class (SDCStudio's XdOrdinal form), keyed
        # by the enclosing component's complex type
        db = e.find(f".//{{{rdfs}}}isDefinedBy")
        owner = next((a for a in e.iterancestors(f"{xs}complexType") if (a.get("name") or "").startswith("mc-")), None)
        if db is not None and owner is not None and db.get(f"{{{rdf}}}resource"):
            out.setdefault(owner.get("name")[3:], []).append((e.get("value"), db.get(f"{{{rdf}}}resource")))
    return out


def main(name: str, sample: str, ct_id: str) -> int:
    spec = load_spec(name)
    if hasattr(spec, "configure"):       # a spec written for several revisions of a model: the rules for this one
        spec.configure(ct_id)
    pkg = load_package(ROOT / sample, ct_id)
    model = read_model(pkg)
    reach = walk(model, data_cluster(ROOT / sample / f"dm-{ct_id}.xsd", ct_id))
    enums = enumerations(ROOT / sample / f"dm-{ct_id}.xsd")
    clusters: dict[str, set[str]] = {}
    leaves: dict[str, set[str]] = {}
    for c, _ in reach:
        (clusters if c.sdc_type == "Cluster" else leaves).setdefault(c.label, set()).add(c.ct_id)
    # A spec that sets REFERENCE_MODEL reads the record's reference-model parts too (sdc-mapper 4.4.0's
    # `reference_model: true`): the subject, providers, Participations, Attestation and workflow. Their components are
    # named by label like any other; `cluster` and `within` may also name the reference-model element a part stands
    # in (`subject`, `provider`, `performer`, `party-details`, ...), and an `element` rule names one that holds a
    # plain value (`start`, `committed`, `pending`, ...). Both are written as given.
    rm = bool(getattr(spec, "REFERENCE_MODEL", False))
    parts = model.part_leaves() if rm else []
    for leaf in parts:
        for c in leaf.path:
            clusters.setdefault(c.label, set()).add(c.ct_id)
        if leaf.component.ct_id in model.components:          # a component (`function` is one), not a plain element
            leaves.setdefault(leaf.component.label, set()).add(leaf.component.ct_id)
    from sdc_mapper.mapping import RM_NAMES, ancestor_tokens

    skipped = []

    def ids(table, label):
        """The identifiers of the components with a label; a label this model does not use (a rule shared by every
        library document) gives none, and is listed, so a misspelled label shows."""
        if rm and label in RM_NAMES:
            return [label]
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
                        "target": {"name": "HL7 FHIR", "version": "R4"},
                        **({"reference_model": True} if rm else {})}, sort_keys=False, width=120).rstrip(),
        "rules:",
    ]
    count = 0
    for entry in spec.RULES:
        entry = dict(entry)
        kind = next(k for k in ("cluster", "element", "component") if k in entry)
        label = entry.pop(kind)
        within = entry.pop("within", [])
        derive = entry.pop("derive", None)
        listuri = entry.pop("listURI", False)
        iri_to = entry.pop("iri_to", None)       # a path that names the component itself, by its published IRI
        targets = [label] if kind == "element" else ids(clusters if kind == "cluster" else leaves, label)
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
    # The DM's `subject` and `provider` are typed by the reference model's base Party, so the model does not say which
    # Party fills each; sdcreader joins them by the record's label. The spec names that join (PARTIES: element ->
    # Party label) and the check uses it.
    unplaced = {c.label: c.ct_id for c in model.unplaced_parties} if rm else {}
    party_role = {unplaced[label]: role for role, label in getattr(spec, "PARTIES", {}).items() if label in unplaced}
    for leaf in parts:            # the reference-model parts, matched as sdc-mapper's placement matches them
        roles = tuple(leaf.roles) or ("",) * len(leaf.path)
        if leaf.path and not roles[0] and leaf.path[0].ct_id in party_role:
            roles = (party_role[leaf.path[0].ct_id],) + roles[1:]
        tokens = ancestor_tokens(leaf.path, roles)
        flat = lambda n: [t for step in tokens[:n] for t in step]   # noqa: E731
        omitted = any(
            (r := mapping.cluster_rule(c.ct_id, flat(i), roles[i])) is not None and r.transform == "omit"
            for i, c in enumerate(leaf.path))
        if not omitted and mapping.rule_for(leaf.component.ct_id, leaf.component.sdc_type, flat(len(tokens)),
                                            leaf.role) is None:
            unreached.append(" / ".join(f"{c.label}" + (f" ({r})" if r else "") for c, r in zip(leaf.path, roles))
                             + f" / {leaf.component.label}" + (f" ({leaf.role})" if leaf.role else ""))
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
