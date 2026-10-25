"""A FHIR R4 Bundle from placements, typed and checked by the FHIR R4 JSON schema.

The writer knows FHIR's JSON and nothing about any model: the mapping file says where each value goes, and the FHIR
R4 JSON schema (fhir.schema.json, published with the specification) says which elements repeat, which are numbers or
booleans, and which members a resource may have. From those it

- builds one element per step and instance (sdc-mapper's placements); a step written `name#tag` is the element
  `name`, kept apart from other `name` elements by its tag (`=entry#patient` joins the one Patient entry);
- writes an element FHIR repeats as an array, and refuses a second value where FHIR allows one;
- writes numbers and booleans as JSON numbers and booleans, from the record's own text, so the bytes are stable;
- gives every entry an id and a `urn:uuid` fullUrl derived from the record's instance id, and replaces a reference
  written `{Patient}` with the fullUrl of the Bundle's one Patient;
- validates every resource, and the Bundle around them, against the FHIR R4 JSON schema, and refuses a Bundle that
  does not conform.
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from sdc_mapper import JOIN, MappingError

SCHEMA = Path(__file__).with_name("schemas") / "fhir.schema.json"
FHIR_VERSION = "4.0.1"
#: Bundles identify the Governed Data Record they were written from by its instance id, in this system.
RECORD_SYSTEM = "https://semanticdatacharter.com/ns/sdc4/instance"
_NAMESPACE = uuid.UUID("2f7d1b1e-6a0e-5c3a-9a47-5dc4e2f0a001")


@lru_cache(maxsize=1)
def schema() -> dict:
    return json.loads(SCHEMA.read_text(encoding="utf-8"))


@lru_cache(maxsize=None)
def _validator(definition: str):
    from jsonschema import Draft6Validator
    root = schema()
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
    def __init__(self):
        self.root: Node | None = None
        self.index: dict[tuple, Node] = {}

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
        entries = [c for c in self.root.children if c.element == "entry"]
        rest = [c for c in self.root.children if c.element != "entry"]
        kinds = {id(e): self._resource_type(e) for e in entries}
        entries.sort(key=lambda e: kinds[id(e)] != "Patient")       # the subject first; otherwise the record's order
        urls = {}
        for i, e in enumerate(entries):
            u = str(uuid.uuid5(_NAMESPACE, f"{instance_id}/{i}/{kinds[id(e)]}"))
            resource = e.child("resource")
            e.children.insert(0, Node("fullUrl", ("id",), text=f"urn:uuid:{u}"))
            at = 1 if resource.children and resource.children[0].element == "resourceType" else 0
            resource.children.insert(at, Node("id", ("id",), text=u))
            urls.setdefault(kinds[id(e)], []).append(f"urn:uuid:{u}")
        identifier = Node("identifier", ("id",), children=[Node("system", ("id",), text=RECORD_SYSTEM),
                                                           Node("value", ("id",), text=instance_id)])
        self.root.children = [*rest, identifier, *entries]
        for e in entries:
            self._profiles(e.child("resource"))
        self._references(self.root, urls)
        bundle = self._json(self.root, schema()["definitions"]["Bundle"])
        self._validate(bundle)
        return _dumps(bundle).encode("utf-8")

    @staticmethod
    def _profiles(resource: Node):
        """What FHIR R4 asks of an Observation beyond what the record says (declared, in the README).

        - An effective time: the mapping dates an Observation by the survey cycle, and a record that carries its own
          date keeps it, so a period beside an effectiveDateTime is dropped.
        - A blood pressure panel (LOINC 85354-9) has a systolic and a diastolic component (the vital signs profile).
          A reading the record has only one of gets the other with dataAbsentReason unknown: the record does not say
          why it is missing.
        """
        if resource is None or (resource.child("resourceType") or Node("", ())).text != "Observation":
            return
        if resource.child("effectiveDateTime") is not None and resource.child("effectivePeriod") is not None:
            resource.children.remove(resource.child("effectivePeriod"))
        if _code_of(resource) != BP_PANEL:
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
        defs = schema()["definitions"]
        ref = prop.get("$ref") or prop.get("items", {}).get("$ref")
        if ref is None:
            return prop
        name = ref.rsplit("/", 1)[1]
        if name == "ResourceList":
            rt = node.child("resourceType")
            if rt is None or rt.text not in defs:
                raise MappingError(f"{node.name}: a resource needs a resourceType FHIR R4 defines")
            name = rt.text
        return defs[name]

    def _json(self, node: Node, definition: dict):
        props = definition.get("properties")
        if props is None:                                     # a primitive
            if node.children:
                raise MappingError(f"{node.name} is a primitive in FHIR R4: it holds a value, not elements")
            kind = definition.get("type")
            if kind == "number":
                return _Raw(node.text)
            if kind == "boolean":
                return node.text == "true"
            return node.text
        if node.text is not None:
            raise MappingError(f"{node.name} is an element of FHIR R4 with members, not a value")
        groups: dict[str, list[Node]] = {}
        for c in node.children:
            if c.element not in props:
                raise MappingError(f"{c.element} is not an element of {definition.get('description', node.name)[:60]!r} "
                                   f"({node.name}) in FHIR R4")
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
                    raise MappingError(f"{name} repeats in {node.name}; FHIR R4 allows one")
                out[name] = self._json(items[0], self._definition(prop, items[0]))
        return out

    @staticmethod
    def _validate(bundle: dict):
        plain = json.loads(_dumps(bundle))
        for entry in plain.get("entry", []):
            resource = entry["resource"]
            errors = sorted(_validator(resource["resourceType"]).iter_errors(resource), key=lambda e: list(e.path))
            if errors:
                e = errors[0]
                raise MappingError(f"the {resource['resourceType']} does not conform to FHIR R4: {e.message} at "
                                   f"{'/'.join(map(str, e.path))}")
        shell = {**plain, "entry": [{k: v for k, v in e.items() if k != "resource"} for e in plain.get("entry", [])]}
        errors = list(_validator("Bundle").iter_errors(shell))
        if errors:
            raise MappingError(f"the Bundle does not conform to FHIR R4: {errors[0].message}")


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
