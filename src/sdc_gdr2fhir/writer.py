"""A FHIR Bundle from placements, typed and checked by the FHIR JSON schema of the mapping's FHIR version.

The writer knows FHIR's JSON and nothing about any model: the mapping file says where each value goes, and the FHIR
JSON schema (fhir.schema.json, published with the specification) says which elements repeat, which are numbers or
booleans, and which members a resource may have. The mapping's `target.version` picks the schema; R4 is the one
version shipped (VERSIONS). From those it

- builds one element per step and instance (sdc-mapper's placements); a step written `name#tag` is the element
  `name`, kept apart from other `name` elements by its tag (`=entry#patient` joins the one Patient entry);
- writes an element FHIR repeats as an array, and refuses a second value where FHIR allows one;
- writes numbers and booleans as JSON numbers and booleans, from the record's own text, so the bytes are stable;
- gives every entry an id and a `urn:uuid` fullUrl derived from the record's instance id, and replaces a reference
  written `{Patient}` with the fullUrl of the Bundle's one Patient;
- validates every resource, and the Bundle around them, against the FHIR JSON schema, and refuses a Bundle that
  does not conform;
- writes a Bundle of the type the mapping gives it (`type`: `collection`, the default, or `document`), and refuses a
  document that breaks what FHIR asks of one (bdl-9: an identifier with a system and a value; bdl-10: a timestamp;
  bdl-11: a Composition as the first entry).

The mapping steers the writer with directives among the Bundle rule's `attributes`, read here and never written (an
element name never starts with `@`):

- `@first`: the resource types whose entries come first, in that order (default `Patient` for a collection,
  `Composition Patient` for a document); every other entry keeps the record's order;
- `@observation`: what the writer adds to or removes from an Observation, by name, beyond what the record says
  (OBSERVATION_RULES). None applies unless the mapping names it.
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from sdc_mapper import JOIN, MappingError



@dataclass(frozen=True)
class Version:
    """A FHIR version the writer writes: its name in a mapping's `target.version`, the specification's version number
    (as HL7's validator takes it, `-version`) and the JSON schema published with it."""
    name: str
    number: str
    schema: Path


#: The FHIR versions shipped, by the name a mapping's `target.version` gives. A second version is a second schema here,
#: not a second writer.
VERSIONS = {"R4": Version("R4", "4.0.1", Path(__file__).with_name("schemas") / "fhir.schema.json")}
DEFAULT_VERSION = "R4"
SCHEMA = VERSIONS[DEFAULT_VERSION].schema
FHIR_VERSION = VERSIONS[DEFAULT_VERSION].number
#: Bundles identify the Governed Data Record they were written from by its instance id, in this system.
RECORD_SYSTEM = "https://semanticdatacharter.com/ns/sdc4/instance"
_NAMESPACE = uuid.UUID("2f7d1b1e-6a0e-5c3a-9a47-5dc4e2f0a001")


def version(name: str) -> Version:
    """The FHIR version a mapping's `target.version` names; one this package does not ship is refused."""
    if name not in VERSIONS:
        raise MappingError(f"FHIR {name} is not a version sdc-gdr2fhir writes ({', '.join(VERSIONS)})")
    return VERSIONS[name]


@lru_cache(maxsize=None)
def schema(name: str = DEFAULT_VERSION) -> dict:
    return json.loads(version(name).schema.read_text(encoding="utf-8"))


@lru_cache(maxsize=None)
def _validator(definition: str, name: str = DEFAULT_VERSION):
    from jsonschema import Draft6Validator
    root = schema(name)
    return Draft6Validator({"$ref": f"#/definitions/{definition}", "definitions": root["definitions"]})


@dataclass
class Node:
    name: str                      # the step: an element name, with an optional '#tag'
    key: tuple
    text: str | None = None
    children: list["Node"] = field(default_factory=list)
    positions: set[int] = field(default_factory=set)

    @property
    def element(self) -> str:
        return self.name.split("#", 1)[0]

    def child(self, element: str) -> "Node | None":
        return next((c for c in self.children if c.element == element), None)


#: The Bundle types the writer writes, and the resource types whose entries come first in each unless `@first` says.
BUNDLE_TYPES = {"collection": ("Patient",), "document": ("Composition", "Patient")}
#: What a mapping may ask the writer to do to an Observation (`@observation`), each described in the README:
#: - `date-time-over-period`: an Observation dated both ways (an effectivePeriod the mapping gives every Observation and
#:   an effectiveDateTime the record carries) keeps the record's effectiveDateTime; the period is dropped.
#: - `blood-pressure-components`: a blood pressure panel (LOINC 85354-9) has a systolic and a diastolic component, in
#:   that order (FHIR R4's vital signs profile); a reading with only one gets the other with dataAbsentReason unknown.
OBSERVATION_RULES = ("date-time-over-period", "blood-pressure-components")
DIRECTIVES = ("@first", "@observation")

BP_PANEL = "85354-9"
BP_COMPONENTS = ("8480-6", "8462-4")              # systolic, diastolic: the profile's slices, in its order
LOINC = "http://loinc.org"
DATA_ABSENT_REASON = "http://terminology.hl7.org/CodeSystem/data-absent-reason"


def _code_of(node: Node) -> str | None:
    """The LOINC code of an Observation or a component (code/coding/code)."""
    code = node.child("code")
    coding = code.child("coding") if code else None
    if coding is None or (coding.child("system") or Node("", ())).text != LOINC:
        return None
    return (coding.child("code") or Node("", ())).text


def _absent_component(code: str) -> Node:
    key = ("profile", code)
    return Node("component", key, children=[
        Node("code", key, children=[Node("coding", key, children=[Node("system", key, text=LOINC),
                                                                  Node("code", key, text=code)])]),
        Node("dataAbsentReason", key, children=[Node("coding", key, children=[
            Node("system", key, text=DATA_ABSENT_REASON), Node("code", key, text="unknown")])]),
    ])


def _where(steps) -> str:
    return "/".join(n for n, _ in steps)


class Builder:
    def __init__(self, fhir_version: str = DEFAULT_VERSION):
        self.version = version(fhir_version)
        self.root: Node | None = None
        self.index: dict[tuple, Node] = {}

    @property
    def defs(self) -> dict:
        return schema(self.version.name)["definitions"]

    def ensure(self, steps) -> Node:
        name, _ = steps[0]
        if self.root is None:
            self.root = Node(name, ())
        elif self.root.name != name:
            raise MappingError(f"one Bundle, one document element: {self.root.name} and {name}")
        node = self.root
        for name, key in steps[1:]:
            if key == JOIN:
                found = [c for c in node.children if c.name == name]
                if len(found) > 1:
                    raise MappingError(f"'={name}' under {node.name}: {len(found)} elements of that name")
                if found:
                    node = found[0]
                    continue
            k = (id(node), name, key)
            child = self.index.get(k)
            if child is None:
                child = Node(name, key)
                node.children.append(child)
                self.index[k] = child
            node = child
        return node

    def find(self, steps) -> Node | None:
        if self.root is None or not steps or self.root.name != steps[0][0]:
            return None
        node = self.root
        for name, key in steps[1:]:
            if key == JOIN:
                found = [c for c in node.children if c.name == name]
                node = found[0] if len(found) == 1 else None
            else:
                node = self.index.get((id(node), name, key))
            if node is None:
                return None
        return node

    def put(self, steps, text: str, position: int | None = None) -> Node:
        node = self.ensure(steps)
        if node.children:
            raise MappingError(f"{_where(steps)} holds elements, not a value")
        if node.text is not None and node.text != text:
            raise MappingError(f"two values for {_where(steps)}: give one of them its own element ('+')")
        node.text = text
        if position is not None:
            node.positions.add(position)
        return node

    # ------------------------------------------------------------ the Bundle
    def finish(self, instance_id: str) -> bytes:
        if self.root is None or self.root.element != "Bundle":
            raise MappingError("nothing to write, or a document element other than Bundle")
        directives = self._directives()
        kind = self.root.child("type")
        if kind is None:                                             # a collection unless the mapping says otherwise
            kind = Node("type", ("id",), text="collection")
            self.root.children.append(kind)
        if kind.text not in BUNDLE_TYPES:
            raise MappingError(f"a Bundle of type {kind.text}: the writer writes {' and '.join(BUNDLE_TYPES)} Bundles")
        first = tuple(directives["@first"].split()) if "@first" in directives else BUNDLE_TYPES[kind.text]
        for rt in first:
            if rt not in self.defs or "resourceType" not in self.defs[rt].get("properties", {}):
                raise MappingError(f"@first: {rt} is not a resource of FHIR {self.version.name}")
        if kind.text == "document" and first[:1] != ("Composition",):
            raise MappingError("a document Bundle's first entry is its Composition (bdl-11): @first must start with "
                               "Composition")
        observation = set(directives.get("@observation", "").split())
        if observation - set(OBSERVATION_RULES):
            raise MappingError(f"@observation: {', '.join(sorted(observation - set(OBSERVATION_RULES)))} is not one of "
                               f"{', '.join(OBSERVATION_RULES)}")
        entries = [c for c in self.root.children if c.element == "entry"]
        own = self.root.child("identifier")                         # the mapping's own identifier, if it gives one
        rest = [c for c in self.root.children if c.element != "entry" and c is not own]
        kinds = {id(e): self._resource_type(e) for e in entries}
        # the declared resource types first, in their order; otherwise the record's order (the sort is stable)
        entries.sort(key=lambda e: first.index(kinds[id(e)]) if kinds[id(e)] in first else len(first))
        urls = {}
        for i, e in enumerate(entries):
            u = str(uuid.uuid5(_NAMESPACE, f"{instance_id}/{i}/{kinds[id(e)]}"))
            resource = e.child("resource")
            e.children.insert(0, Node("fullUrl", ("id",), text=f"urn:uuid:{u}"))
            at = 1 if resource.children and resource.children[0].element == "resourceType" else 0
            resource.children.insert(at, Node("id", ("id",), text=u))
            urls.setdefault(kinds[id(e)], []).append(f"urn:uuid:{u}")
        identifier = own or Node(                                    # the mapping's own, or the record's instance id
            "identifier", ("id",), children=[Node("system", ("id",), text=RECORD_SYSTEM),
                                             Node("value", ("id",), text=instance_id)])
        self.root.children = [*rest, identifier, *entries]
        for e in entries:
            self._profiles(e.child("resource"), observation)
        self._references(self.root, urls)
        bundle = self._json(self.root, self.defs["Bundle"])
        self._validate(bundle)
        return _dumps(bundle).encode("utf-8")

    def _directives(self) -> dict[str, str]:
        """The writer's directives among the Bundle's members (`@first`, `@observation`), taken out of the Bundle."""
        found = [c for c in self.root.children if c.element.startswith("@")]
        out = {}
        for c in found:
            if c.element not in DIRECTIVES or c.children:
                raise MappingError(f"{c.element} is not a directive of the writer ({', '.join(DIRECTIVES)})")
            out[c.element] = c.text or ""
        self.root.children = [c for c in self.root.children if c not in found]
        return out

    @staticmethod
    def _profiles(resource: Node, rules=()):
        """What the mapping asks the writer to do to an Observation beyond what the record says (`@observation`; each
        rule in OBSERVATION_RULES, described in the README).

        - `date-time-over-period`: the mapping dates an Observation by a period (the NHANES survey cycle), and a record
          that carries its own date keeps it, so a period beside an effectiveDateTime is dropped.
        - `blood-pressure-components`: a blood pressure panel (LOINC 85354-9) has a systolic and a diastolic component
          (the vital signs profile). A reading the record has only one of gets the other with dataAbsentReason
          unknown: the record does not say why it is missing.
        """
        if resource is None or (resource.child("resourceType") or Node("", ())).text != "Observation":
            return
        if "date-time-over-period" in rules and resource.child("effectiveDateTime") is not None \
                and resource.child("effectivePeriod") is not None:
            resource.children.remove(resource.child("effectivePeriod"))
        if "blood-pressure-components" not in rules or _code_of(resource) != BP_PANEL:
            return
        have = {_code_of(c): c for c in resource.children if c.element == "component"}
        filled = [have.get(code) or _absent_component(code) for code in BP_COMPONENTS]
        others = [c for c in resource.children if c.element != "component"]
        extra = [c for c in resource.children if c.element == "component" and _code_of(c) not in BP_COMPONENTS]
        resource.children = others + filled + extra

    @staticmethod
    def _resource_type(entry: Node) -> str:
        resource = entry.child("resource")
        rt = resource.child("resourceType") if resource else None
        if rt is None or not rt.text:
            raise MappingError(f"an entry with no resourceType ({entry.name})")
        return rt.text

    def _references(self, node: Node, urls: dict[str, list[str]]):
        if node.text and node.text.startswith("{") and node.text.endswith("}"):
            kind = node.text[1:-1]
            found = urls.get(kind, [])
            if len(found) != 1:
                raise MappingError(f"a reference to {{{kind}}}: the Bundle has {len(found)} {kind} entries")
            node.text = found[0]
        for c in node.children:
            self._references(c, urls)

    # ------------------------------------------------------------ JSON, typed by the schema
    def _definition(self, prop: dict, node: Node) -> dict:
        defs = self.defs
        ref = prop.get("$ref") or prop.get("items", {}).get("$ref")
        if ref is None:
            return prop
        name = ref.rsplit("/", 1)[1]
        if name == "ResourceList":
            rt = node.child("resourceType")
            if rt is None or rt.text not in defs:
                raise MappingError(f"{node.name}: a resource needs a resourceType FHIR {self.version.name} defines")
            name = rt.text
        return defs[name]

    def _json(self, node: Node, definition: dict):
        props = definition.get("properties")
        if props is None:                                     # a primitive
            if node.children:
                raise MappingError(f"{node.name} is a primitive in FHIR {self.version.name}: it holds a value, not "
                                   "elements")
            kind = definition.get("type")
            if kind == "number":
                return _Raw(node.text)
            if kind == "boolean":
                return node.text == "true"
            return node.text
        if node.text is not None:
            raise MappingError(f"{node.name} is an element of FHIR {self.version.name} with members, not a value")
        groups: dict[str, list[Node]] = {}
        for c in node.children:
            if c.element not in props:
                raise MappingError(f"{c.element} is not an element of {definition.get('description', node.name)[:60]!r} "
                                   f"({node.name}) in FHIR {self.version.name}")
            groups.setdefault(c.element, []).append(c)
        out = {}
        for name in props:                                    # the specification's order
            if name not in groups:
                continue
            prop = props[name]
            items = groups[name]
            if prop.get("type") == "array":
                out[name] = [self._json(c, self._definition(prop, c)) for c in items]
            else:
                if len(items) > 1:
                    raise MappingError(f"{name} repeats in {node.name}; FHIR {self.version.name} allows one")
                out[name] = self._json(items[0], self._definition(prop, items[0]))
        return out

    def _validate(self, bundle: dict):
        name = self.version.name
        plain = json.loads(_dumps(bundle))
        for entry in plain.get("entry", []):
            resource = entry["resource"]
            errors = sorted(_validator(resource["resourceType"], name).iter_errors(resource), key=lambda e: list(e.path))
            if errors:
                e = errors[0]
                raise MappingError(f"the {resource['resourceType']} does not conform to FHIR {name}: {e.message} at "
                                   f"{'/'.join(map(str, e.path))}")
        shell = {**plain, "entry": [{k: v for k, v in e.items() if k != "resource"} for e in plain.get("entry", [])]}
        errors = list(_validator("Bundle", name).iter_errors(shell))
        if errors:
            raise MappingError(f"the Bundle does not conform to FHIR {name}: {errors[0].message}")
        if plain.get("type") == "document":
            _document(plain)


def _document(bundle: dict):
    """What FHIR asks of a document Bundle beyond its schema: bdl-9, bdl-10, bdl-11."""
    identifier = bundle.get("identifier") or {}
    if not (identifier.get("system") and identifier.get("value")):
        raise MappingError("a document Bundle needs an identifier with a system and a value (bdl-9)")
    if not bundle.get("timestamp"):
        raise MappingError("a document Bundle needs a timestamp (bdl-10): the mapping places one, the writer does not "
                           "invent it")
    entries = bundle.get("entry") or []
    if not entries or entries[0]["resource"]["resourceType"] != "Composition":
        raise MappingError("a document Bundle's first entry is a Composition (bdl-11)")


class _Raw(str):
    """A JSON number written as the record's own decimal text."""


def _dumps(value, indent: int = 0) -> str:
    pad, inner = "  " * indent, "  " * (indent + 1)
    if isinstance(value, _Raw):
        return str(value)
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, list):
        if not value:
            return "[]"
        return "[\n" + ",\n".join(inner + _dumps(v, indent + 1) for v in value) + "\n" + pad + "]"
    if isinstance(value, dict):
        if not value:
            return "{}"
        return "{\n" + ",\n".join(f"{inner}{json.dumps(k)}: {_dumps(v, indent + 1)}" for k, v in value.items()) + \
            "\n" + pad + "}"
    raise TypeError(type(value))
