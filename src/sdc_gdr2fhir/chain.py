"""Chained records: one FHIR Bundle from a parent record and the records chained to it.

The SDCHealth library keeps a document's repeating entries out of the document's own record: each is a record of its
own, chained to the parent (library decision 12). A Laboratory Report's results, its order and its requests are records
whose Parent Record Identifier holds the report's Record Identifier; a specimen is a record the others name by
reference. FHIR puts them together, in one document Bundle.

- **Which records belong (`check`).** A child that carries a Parent Record Identifier belongs when it holds the
  parent's Record Identifier, or the identifier of another child of the chain (its Record Identifier, or a specimen's
  Accession Identifier): a Reference Range is chained to its Laboratory Observation, a Specimen Collection to its
  Specimen. It is refused otherwise. A child without one (a specimen) belongs when another record of the chain names
  it by reference; one nobody names is refused. A child about another patient (its subject's identifiers and the
  parent's share none) is refused.
- **Each child by its own mapping.** A chained record's mapping says, in its Bundle rule's `@chained-to` directive, the
  parent model it chains to and the tag of the entry the record makes (`zptekdommw56yiz9lqjy5dga obs`). Its paths are
  the parent Bundle's: `{entry#patient}` is the parent's Patient, `=entry#dr/=resource/+result` joins the parent's
  DiagnosticReport: a tag the parent's mapping writes names the parent's entry. Its own entries (tags the parent's
  mapping does not write) are kept apart from its siblings' (the n-th child's `entry#obs` is `entry#obs.n`, and
  `{entry#obs}` in its mapping names its own), and so is every element it adds (`+result`, one per child).
- **A record chained to a child.** Its `@chained-to` names the child's model and the tag of the entry that child makes
  (`ojjr56tqlxk808lqq8ig8vg0 obs`): `=entry#obs` in its mapping is that child's entry (`entry#obs.n`), so a Reference
  Range writes into its own Observation. The directive may sit on the record's data-cluster rule wherever it writes
  (`=entry#obs/=resource/referenceRange`), and is never written itself.
- **References between records.** An element on a path tagged `#record` (`+specimen#record/reference`) holds the IRI
  of a record of the chain (or several, whitespace-delimited, one element each): it is written as the reference to
  that record's entry. A record is named by its instance id (the IRI ends with it) or by a business identifier its
  entry carries (`identifier` or `accessionIdentifier`). A reference to a record outside the chain is refused.
"""
from __future__ import annotations

from dataclasses import dataclass

from sdc_mapper import JOIN, MapResult, MappingError, place

from .writer import Builder

#: The SDCHealth library components the chain is read by (library decision 12; the same component in every model).
PARENT_RECORD_IDENTIFIER = "b5v4p5ju74ugnzyt9bh98398"     # XdString: the parent's Record Identifier value
RECORD_IDENTIFIER = "nieu1e3llgra1v66p2x8jnwu"            # Cluster: Record Identifier
IDENTIFIER_VALUE = "h17egwljmrym3r8ortrqqjwd"             # XdString: Identifier Value (in Record and Person Identifier)
ACCESSION_IDENTIFIER = "yfgaozed8j7bmza0kipkpa3c"         # XdString: a Specimen's Accession Identifier (its own identifier)
#: The tag on a path step whose element holds a record's IRI, written as a reference to that record's entry.
RECORD_TAG = "record"


class ChainError(MappingError):
    """A record that does not belong to the chain it was given with."""


@dataclass
class ChainMapResult:
    """What `FHIRMapper.map_chain` returns: the one Bundle, and each record's MapResult (the parent's first), each
    holding the same files, so sdc-mapper's `build_report` makes each record's coverage report as for one record."""
    files: dict[str, bytes]
    results: list


@dataclass
class ChainRecord:
    instance_id: str
    ct_id: str
    outcome: str                     # the gate's: valid or valid_with_ev
    report: object                   # sdc_mapper CoverageReport: every value of the record, with its class


@dataclass
class ChainResult:
    """One chain mapped: the Bundle, the chain's outcome (the gate's: valid_with_ev if any record needed the gate's
    recovery), and each record's report, the parent's first."""
    outcome: str
    files: dict[str, bytes]
    records: list[ChainRecord]


def _text(v) -> str | None:
    from sdc_mapper.placement import text_of
    return text_of(v)


def record_identifier(record) -> str | None:
    """A record's own Record Identifier value (in its data cluster), or None."""
    for v in record.values:
        if v.ct_id == IDENTIFIER_VALUE and v.path and RECORD_IDENTIFIER in (c.ct_id for c in v.path) \
                and not any(r for r in v.roles):
            return _text(v)
    return None


def own_identifiers(record) -> set[str]:
    """The identifiers a record's children may name it by: its Record Identifier, or a specimen's Accession
    Identifier (a Specimen has no Record Identifier)."""
    out = {record_identifier(record)}
    out |= {_text(v) for v in record.values if v.ct_id == ACCESSION_IDENTIFIER and not any(r for r in v.roles)}
    return out - {None}


def parent_identifier(record) -> str | None:
    for v in record.values:
        if v.ct_id == PARENT_RECORD_IDENTIFIER:
            return _text(v)
    return None


def subject_identifiers(record) -> set[str]:
    """The identifier values of the record's subject (the person it is about)."""
    return {_text(v) for v in record.values
            if v.ct_id == IDENTIFIER_VALUE and v.roles and v.roles[0] == "subject" and _text(v)}


def check(parent, children) -> list:
    """How each child joins the parent: "parent" (its Parent Record Identifier is the parent's Record Identifier), the
    number of the child it is chained to (1 for the first child: its Parent Record Identifier is that child's Record or
    Accession Identifier), or "reference" (it has none, and must be named by another record of the chain). Raises
    ChainError for a child that names a record outside the chain (or two records of it), one chained to itself or in a
    loop, or one about another patient."""
    own = record_identifier(parent)
    patient = subject_identifiers(parent)
    theirs_ids = [own_identifiers(c) for c in children]
    joins = []
    for i, child in enumerate(children, 1):
        named = parent_identifier(child)
        if named is not None:
            if own is not None and named == own:
                joins.append("parent")
            else:
                found = [j for j, ids in enumerate(theirs_ids, 1) if named in ids and j != i]
                if len(found) != 1:
                    raise ChainError(f"chained record {i} ({child.instance_id}): its Parent Record Identifier is "
                                     f"{named!r}, and the parent's Record Identifier is {own!r}"
                                     + (f"; {len(found)} records of the chain carry it" if found else ""))
                joins.append(found[0])
        else:
            joins.append("reference")
        theirs = subject_identifiers(child)
        if patient and theirs and not (patient & theirs):
            raise ChainError(f"chained record {i} ({child.instance_id}) is about another patient: its subject's "
                             "identifiers and the parent's share none")
    for i in range(1, len(children) + 1):           # no loops: each child reaches the parent
        seen, at = set(), i
        while isinstance(joins[at - 1], int):
            if at in seen:
                raise ChainError(f"chained record {i} ({children[i - 1].instance_id}) is chained in a loop")
            seen.add(at)
            at = joins[at - 1]
    return joins


def _depth(joins, i: int) -> int:
    d = 0
    while isinstance(joins[i - 1], int):
        d, i = d + 1, joins[i - 1]
    return d


@dataclass
class _Child:
    index: int
    record: object
    mapping: object
    placements: list
    clusters: list
    writes: list
    notes: dict
    primary: str = ""            # the tag of the entry the record makes, as written (`entry#obs.1`)


class ChainWriter:
    def __init__(self, mapper):
        self.mapper = mapper

    def write(self, parent, children):
        from .mapper import CHAINED, _cluster_attributes, _put_all
        m = self.mapper
        precord, pmapping = parent
        m._check(pmapping)
        joins = check(precord, [r for r, _ in children])
        pplacements, pclusters = place(precord, pmapping)
        pwrites, pnotes = m._writes(pplacements, precord)
        kids: list[_Child] = []
        placed = []
        for i, (record, mapping) in enumerate(children, 1):
            m._check(mapping)
            if mapping.target_version != pmapping.target_version:
                raise ChainError(f"chained record {i}: its mapping is for FHIR {mapping.target_version}, the parent's "
                                 f"for FHIR {pmapping.target_version}")
            placements, clusters = place(record, mapping)
            writes, notes = m._writes(placements, record)
            directive = next((c.attributes[CHAINED] for c in clusters if CHAINED in c.attributes), None)
            if not directive or len(directive.split()) != 2:
                raise ChainError(f"chained record {i}: mapping {mapping.id} has no `{CHAINED}: <parent ct_id> <tag>` "
                                 "directive, so it is not a mapping for a chained record")
            parent_ct, tag = directive.split()
            up = joins[i - 1]
            expected = children[up - 1][1].model_ct_id if isinstance(up, int) else pmapping.model_ct_id
            if parent_ct != expected:
                whose = f"record {up}" if isinstance(up, int) else "the parent"
                raise ChainError(f"chained record {i}: mapping {mapping.id} chains to model {parent_ct}, and {whose} it "
                                 f"is chained to is {expected}")
            kids.append(_Child(i, record, mapping, placements, clusters, [], notes))
            placed.append((writes, tag))
        parents = _entry_tags(pwrites)
        # a record chained to a child after that child, so the child's entry has its name
        for kid in sorted(kids, key=lambda k: _depth(joins, k.index)):
            writes, tag = placed[kid.index - 1]
            up = joins[kid.index - 1]
            mapped = {}
            if isinstance(up, int):           # `entry#<tag>` is the entry of the child this record is chained to
                mapped[tag] = kids[up - 1].primary.split("#", 1)[1]
            kid.writes, kid.primary = _own(writes, kid.index, tag, kid.mapping.id, parents, mapped)
            own = _entry_tags(writes) - parents - set(mapped)
            kid.clusters = [c for c in (_own_cluster(c, kid.index, own, mapped) for c in kid.clusters) if c is not None]

        b = Builder(pmapping.target_version)
        refs = []
        plain = list(pwrites)
        for k in sorted(kids, key=lambda k: _depth(joins, k.index)):
            for w in k.writes:
                (refs if _record_step(w[0]) is not None else plain).append((k, w) if _record_step(w[0]) is not None
                                                                          else w)
        _put_all(b, plain)
        _cluster_attributes(b, pclusters)
        for k in sorted(kids, key=lambda k: _depth(joins, k.index)):
            _cluster_attributes(b, k.clusters)
        named = self._resolve(b, precord, kids, refs, {k.index for k in kids if isinstance(joins[k.index - 1], int)})
        for k, join in zip(kids, joins):
            if join == "reference" and k.primary not in named:
                raise ChainError(f"chained record {k.index} ({k.record.instance_id}) has no Parent Record Identifier, "
                                 "and no record of the chain names it")
        from .mapper import CANNOT_HOLD
        files = {"Bundle.json": b.finish(precord.instance_id)}
        results = [MapResult(files=files, outcomes=m._outcomes(pplacements, pnotes, pmapping),
                             cannot_hold=list(CANNOT_HOLD))]
        results += [MapResult(files=files, outcomes=m._outcomes(k.placements, k.notes, k.mapping),
                              cannot_hold=list(CANNOT_HOLD)) for k in kids]
        return ChainMapResult(files=files, results=results)

    @staticmethod
    def _resolve(b, precord, kids, refs, nested=frozenset()) -> set[str]:
        """Write each `#record` element as the reference to the record it names; the tags of the entries named."""
        names: dict[str, str] = {}
        for k in kids:
            if k.index in nested:
                continue                      # written into the entry of the child it is chained to: no entry of its own
            entry = next((c for c in b.root.children if c.name == k.primary), None) if b.root else None
            if entry is None:
                raise ChainError(f"chained record {k.index} ({k.record.instance_id}) wrote no {k.primary} entry")
            for key in _business_identifiers(entry):
                names.setdefault(key, k.primary)
            names[k.record.instance_id] = k.primary
        named = set()
        for k, (steps, text, position) in refs:
            at = _record_step(steps)
            for n, token in enumerate((text or "").split()):
                tag = names.get(token) or next((t for iid, t in names.items()
                                                if token.endswith(f"/{iid}") or token.endswith(f":{iid}")), None)
                if tag is None:
                    raise ChainError(f"chained record {k.index} ({k.record.instance_id}) names {token!r}, which is no "
                                     "record of the chain")
                named.add(tag)
                s = list(steps)
                name, key = s[at]
                s[at] = (name, key if key == JOIN else key + (("item", n),))
                b.put(s, "{" + tag + "}", position if n == 0 else None)
        return named


def _record_step(steps) -> int | None:
    for i, (name, _key) in enumerate(steps):
        if name.endswith(f"#{RECORD_TAG}"):
            return i
    return None


def _business_identifiers(entry) -> list[str]:
    resource = entry.child("resource")
    out = []
    for c in (resource.children if resource else []):
        if c.element in ("identifier", "accessionIdentifier"):
            value = c.child("value")
            if value is not None and value.text:
                out.append(value.text)
    return out


def _entry_tags(writes) -> set[str]:
    return {name.split("#", 1)[1] for steps, _t, _p in writes for name, _key in steps
            if name.split("#", 1)[0] == "entry" and "#" in name}


def _own(writes, i: int, tag: str, mapping_id: str, parents: set[str], mapped: dict | None = None):
    """A child's writes in the parent's Bundle: its own entries (tags the parent's mapping does not write) tagged apart
    from its siblings', every element it adds keyed apart, `{entry#tag}` naming its own entry, and nothing written to
    the Bundle's own members. A tag the parent writes too (`=entry#dr`) is the parent's entry; a tag in `mapped` is the
    entry of the child this record is chained to (`obs` -> `obs.3`)."""
    mapped = mapped or {}
    tags = _entry_tags(writes) - parents - set(mapped)
    if tag not in tags and tag not in parents and tag not in mapped:
        raise ChainError(f"mapping {mapping_id}: its `@chained-to` names entry#{tag}, which neither it nor the parent "
                         "writes")
    out = []
    for steps, text, position in writes:
        if steps and steps[0][0] == "Bundle" and len(steps) > 1 and steps[1][0].split("#", 1)[0] != "entry":
            continue                                  # the parent's Bundle members are the parent's
        s = [(_renamed(name, i, tags, mapped), key if key == JOIN else (("chain", i),) + key) for name, key in steps]
        if isinstance(text, str) and text.startswith("{entry#") and text.endswith("}"):
            if text[7:-1] in tags:
                text = "{entry#" + text[7:-1] + f".{i}" + "}"
            elif text[7:-1] in mapped:
                text = "{entry#" + mapped[text[7:-1]] + "}"
        out.append((s, text, position))
    if tag in mapped:                                 # a record written into the entry of the child it is chained to
        return out, f"entry#{mapped[tag]}"
    return out, (f"entry#{tag}.{i}" if tag in tags else f"entry#{tag}")    # a record written into a parent's entry


def _own_cluster(c, i: int, tags: set[str], mapped: dict | None = None):
    from .mapper import CHAINED
    if c.steps and c.steps[0][0] == "Bundle" and len(c.steps) == 1:
        return None                                   # the Bundle rule's attributes: the parent's
    from copy import copy
    c = copy(c)
    c.steps = [(_renamed(n, i, tags, mapped), k if k == JOIN else (("chain", i),) + k) for n, k in c.steps]
    c.attributes = {a: v for a, v in c.attributes.items() if a != CHAINED}    # the directive is read, not written
    return c


def _renamed(name: str, i: int, tags: set[str], mapped: dict | None = None) -> str:
    if name.split("#", 1)[0] != "entry" or "#" not in name:
        return name
    tag = name.split("#", 1)[1]
    if mapped and tag in mapped:
        return f"entry#{mapped[tag]}"
    return f"{name}.{i}" if tag in tags else name


def read(engine, xml: bytes, mapping, directory: str | None = None, ct_id: str | None = None):
    """A record gated against its model's schema and read as its mapping asks (sdc-mapper's Engine: its model cache and
    gate), resolved; (record, mapping). A record the gate refuses raises ChainError with the gate's first error."""
    from sdc_mapper.gate import REFUSED
    from sdc_mapper.resolve import resolve
    from sdcreader.record import read_record
    pkg, model = engine.model_for(xml, ct_id, directory)
    mapping.check(model.ct_id, pkg.sha256, "HL7 FHIR", mapping.target_version)
    gate = engine.gate.check(xml, pkg, model, reference_model=mapping.reference_model)
    if gate.outcome == REFUSED:
        first = gate.errors[0] if gate.errors else {}
        raise ChainError(f"record refused by its model's schema: {first.get('reason', first)}")
    return resolve(read_record(gate.xml, model, reference_model=mapping.reference_model), model, pkg, gate), mapping


def map_files(engine, parent, children, mapper=None) -> ChainResult:
    """One chain from records as files: `parent` and each child a (xml bytes, mapping, directory) triple, each gated
    against its own model's schema and read by `engine` (sdc_mapper.Engine). Returns one ChainResult: the Bundle and
    each record's coverage report (sdc-mapper's `build_report`), the parent's first.

    This is the shape sdc-mapper's Engine.map_chain is to have (docs/chained-records.md): one parent, a list of
    children, one result with the per-value report."""
    from sdc_mapper.gate import VALID_WITH_EV
    from sdc_mapper.report import build_report
    from .mapper import FHIRMapper
    m = mapper or FHIRMapper.for_mapping(parent[1])
    records = [read(engine, parent[0], parent[1], parent[2])] + [read(engine, xml, mp, d) for xml, mp, d in children]
    mapped = m.map_chain(records[0], records[1:])
    out = [ChainRecord(r.instance_id, r.ct_id, r.outcome, build_report(r, result, m, mapping))
           for (r, mapping), result in zip(records, mapped.results)]
    outcome = VALID_WITH_EV if any(r.outcome == VALID_WITH_EV for r in out) else out[0].outcome
    return ChainResult(outcome=outcome, files=mapped.files, records=out)
