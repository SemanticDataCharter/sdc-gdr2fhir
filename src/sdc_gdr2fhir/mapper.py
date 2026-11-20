"""The FHIR mapper: a Governed Data Record as a FHIR Bundle, by a mapping file.

The mapping says the FHIR version (`target.version`; R4 is the one shipped) and the Bundle's type (`collection`, the
default, or `document`); the writer does the rest.

Where the model binds a value to a code FHIR knows (a LOINC code for a laboratory result, a SNOMED CT concept for a
condition, an answer's LOINC answer code, an administrative gender), the code written is the model's own and the
value is a lookup; the mapping file says only where it goes. Everything else is declared.

FHIR is the target that can say most of what an Exceptional Value says: an Observation's value carries a
dataAbsentReason, and any other element carries the data-absent-reason extension, or, for the null flavors
data-absent-reason has no code for, the iso21090-nullFlavor extension with the exact v3 NullFlavor code.
"""
from __future__ import annotations

import html

from sdc_mapper import (DECLARED, JOIN, LOOKUP, LOOKUP_TRANSFORMS, NOT_REPRESENTABLE, PRESERVED, EVRule, IncompleteMapping, MapResult,
                        MappingError, ValueOutcome, join_depth, place)
from sdcreader.record import EXCEPTIONAL_VALUES

from . import __version__
from .codes import DATA_ABSENT_REASON, absent, model_codes
from .writer import DEFAULT_VERSION, FHIR_VERSION, VERSIONS, Builder, version

#: FHIR R4 writes every ISO 21090 null flavor exactly (codes.absent).
EV_TABLE = {code: EVRule(PRESERVED, target_code=f"{absent(code)[0].rsplit('/', 1)[1]}#{absent(code)[1]}")
            for code in EXCEPTIONAL_VALUES}

#: What a FHIR Bundle cannot hold for any record.
CANNOT_HOLD = [
    "validity windows and the time a value was recorded (act, vtb, vte, tr)",
    "the definitions the model binds each component to, beyond the codes written",
]

#: data-absent-reason's `unknown` and the concepts under it (data-absent-reason 4.0.1, looked up on tx.fhir.org).
UNKNOWN = {"unknown", "asked-unknown", "temp-unknown", "not-asked", "asked-declined"}

#: Elements whose value an Observation (or its component) qualifies with dataAbsentReason.
_OBSERVATION_VALUES = {"valueQuantity", "valueCodeableConcept", "valueString", "valueBoolean", "valueInteger",
                       "valueRange", "valueRatio", "valueSampledData", "valueTime", "valueDateTime", "valuePeriod"}


class FHIRMapper:
    """The target `fhir`. `target_version` is the FHIR version it writes (R4 unless given): sdc-mapper refuses a
    mapping whose `target.version` is another, and `for_mapping` gives the mapper a mapping asks for."""
    name = "fhir"
    target = "HL7 FHIR"
    target_version = DEFAULT_VERSION      # the class's default; an instance's own when given (for_mapping)
    package = "sdc-gdr2fhir"
    version = __version__
    ev_table = EV_TABLE

    def __init__(self, target_version: str = DEFAULT_VERSION):
        self.target_version = version(target_version).name

    @classmethod
    def for_mapping(cls, mapping) -> "FHIRMapper":
        """The mapper for the FHIR version a mapping's `target.version` names."""
        return cls(mapping.target_version)

    def map(self, record, mapping) -> MapResult:
        if mapping is None:
            raise MappingError("FHIR needs a mapping file: the model does not say which resource each value belongs to")
        if mapping.target_version != self.target_version:
            raise MappingError(f"mapping {mapping.id} is for FHIR {mapping.target_version}; this mapper writes FHIR "
                               f"{self.target_version}")
        if mapping.carry_rejected:
            raise MappingError("carry_rejected is not available: a rejected value is never written as data")
        if mapping.exceptional_values:
            raise MappingError(f"FHIR {self.target_version} writes every ISO 21090 code exactly; a mapping cannot "
                               "change that")
        placements, clusters = place(record, mapping)
        b = Builder(mapping.target_version)
        notes: dict[int, str] = {}
        later = []
        for p in placements:
            v = p.value
            if p.omitted or p.rule is None or not p.steps:
                continue
            writes = []
            if v.exceptional:
                writes += self._absent(p.steps, p.attribute, v.exceptional.code)
            elif p.text is None and not _stands_in(p):
                notes[v.position] = p.note or "no value to write"
                continue
            elif p.text is None:
                pass                              # an `also` writes the value as another value[x] of the same element
            else:
                writes.append((self._steps(p.steps, p.attribute), p.text, v.position))
                if p.units_attribute and p.units_text is not None:
                    writes.append((self._steps(p.steps, p.units_attribute), p.units_text, None))
                    if p.units_attribute == "code" and v.units:   # a Quantity: the unit as people read it
                        writes.append((self._steps(p.steps, "unit"), v.units.symbol, None))
            own = list(p.steps[:-1])           # the element the value is written in (a valueQuantity)
            # an `also` copy with no value to copy (an Exceptional Value) leaves its tagged element out altogether: a
            # section with a title and no text is not written for a comment the record does not have
            empty = [_tagged(e.steps) for e, sub in zip(p.extras, p.rule.also)
                     if e.text is None and sub.get("transform", "copy") == "copy" and _tagged(e.steps)]
            for e in p.extras:
                if e.text is None:
                    continue
                if v.exceptional and list(e.steps[: len(own)]) == own:
                    continue                      # with no value, nothing beside it (a quantity's system) either
                if v.exceptional and any(list(e.steps[: len(t)]) == t for t in empty):
                    continue
                writes.append((self._steps(e.steps, e.attribute), e.text, None))
            writes += [(self._resource(p.steps) + [(part, ("attr",)) for part in k.split("/")], val, None)
                       for k, val in p.attributes.items()]
            writes = [w for w in (_record_value(w, record) for w in writes) if w is not None]
            for w in writes:
                if any(key == JOIN for _, key in w[0]):
                    later.append(w)             # '=name' joins wait until every element they may join exists
                else:
                    b.put(*w)
        for w in sorted(later, key=lambda w: join_depth(w[0])):   # shallowest join first (sdc-mapper 4.3.0)
            b.put(*w)
        for c in clusters:
            node = b.find(c.steps)
            if node is not None:
                for k, val in c.attributes.items():
                    b.put(c.steps + [(part, ("attr",)) for part in k.split("/")], val)
        instance_id = record.instance_id
        bundle = b.finish(instance_id)

        outcomes, missing = [], []
        for p in placements:
            v = p.value
            if v.exceptional:
                r = self.ev_table[v.exceptional.code]
                outcomes.append(ValueOutcome(v.position, r.cls, location=self._where(p), target_code=r.target_code))
            elif p.omitted:
                outcomes.append(ValueOutcome(v.position, NOT_REPRESENTABLE, note=p.omitted_by.reason or ""))
            elif p.rule is None:
                missing.append(f"{' / '.join(v.path_labels + [v.label])} ({v.ct_id})")
            elif v.position in notes:
                outcomes.append(ValueOutcome(v.position, NOT_REPRESENTABLE, note=notes[v.position]))
            else:
                written = {p.text, p.units_text, *(e.text for e in p.extras)} - {None}
                lookup = p.rule.transform in LOOKUP_TRANSFORMS or bool(written & model_codes(v))
                outcomes.append(ValueOutcome(v.position, LOOKUP if lookup else DECLARED, location=self._where(p)))
        if missing:
            raise IncompleteMapping(f"mapping {mapping.id} has no rule for {len(missing)} value(s): " + "; ".join(missing[:5]))
        return MapResult(files={"Bundle.json": bundle}, outcomes=outcomes, cannot_hold=list(CANNOT_HOLD))

    # ------------------------------------------------------------ paths
    @staticmethod
    def _steps(steps, attribute):
        """An attribute of a primitive is, in FHIR's JSON, a sibling member: valueQuantity's value and its code."""
        return list(steps) if not attribute else list(steps[:-1]) + [(attribute, steps[-1][1])]

    @staticmethod
    def _resource(steps):
        """The steps to the resource a value belongs to: a rule's constant attributes are the resource's members."""
        for i in range(len(steps) - 1, -1, -1):
            if steps[i][0].split("#", 1)[0] == "resource":
                return list(steps[: i + 1])
        raise MappingError(f"{_join(steps)}: attributes are a resource's members, and this path names no resource")

    def _absent(self, steps, attribute, code: str):
        """Where an Exceptional Value goes: an Observation's (or component's) value gets dataAbsentReason; any other
        element the extension that says why it is absent."""
        system, value, extension = absent(code)
        steps = self._steps(steps, attribute)
        for i, (name, _key) in enumerate(steps):
            if name in _OBSERVATION_VALUES and i > 0 and steps[i - 1][0].split("#", 1)[0] in ("resource", "component"):
                at = list(steps[:i]) + [("dataAbsentReason", ("dar",)), ("coding", ("dar",))]
                return [(at + [("system", ("dar",))], system, None), (at + [("code", ("dar",))], value, None)]
        last, key = steps[-1]
        at = list(steps[:-1]) + [(f"_{last}", key), ("extension", ("dar",))]
        writes = [(at + [("url", ("dar",))], extension, None), (at + [("valueCode", ("dar",))], value, None)]
        if last == "text" and len(steps) > 2 and steps[-2][0].split("#", 1)[0] == "valueCodeableConcept" \
                and steps[-3][0].split("#", 1)[0] == "extension" and system == DATA_ABSENT_REASON and value in UNKNOWN:
            # An extension's CodeableConcept value with only an absent text has no code, and a required binding needs
            # one. Its coding is the concept that subsumes this one, data-absent-reason `unknown`, which value sets
            # for what a person may not know include (Sex Parameter for Clinical Use, which PatientEuCore's
            # patient-sexParameterForClinicalUse binds). The extension on the text keeps the exact code.
            coding = list(steps[:-1]) + [("coding", ("dar",))]
            writes += [(coding + [("system", ("dar",))], DATA_ABSENT_REASON, None),
                       (coding + [("code", ("dar",))], "unknown", None)]
        return writes

    @staticmethod
    def _where(p) -> str:
        return _join(p.steps) + (f"/{p.attribute}" if p.attribute else "")


def _tagged(steps) -> list:
    """The steps to the deepest tagged element (`section#notes`) on a path, or [] if it has none."""
    for i in range(len(steps) - 1, -1, -1):
        if "#" in steps[i][0]:
            return list(steps[: i + 1])
    return []


def _record_value(write, record):
    """A write as the Bundle takes it.
    - A constant `{record:<name>}` is the record's own attribute of that name (`dm-language`, `creation_timestamp`,
      `current-state`, ...: the attributes under the record's root). A record without it writes nothing there.
    - Plain text written to a Narrative's `div` is that text, escaped, in the XHTML `div` FHIR requires."""
    steps, text, position = write
    if isinstance(text, str) and text.startswith("{record:") and text.endswith("}"):
        text = (getattr(record, "attributes", None) or {}).get(text[len("{record:"):-1]) or None
        if text is None:
            return None
    if steps and steps[-1][0] == "div" and len(steps) > 1 and steps[-2][0].split("#", 1)[0] == "text" \
            and isinstance(text, str) and not text.lstrip().startswith("<div"):
        text = f'<div xmlns="http://www.w3.org/1999/xhtml">{html.escape(text, quote=False)}</div>'
    return steps, text, position


def _value_at(steps) -> int:
    """The index of the last value[x] step (FHIR's choice element: valueCoding, valueString), or -1."""
    for i in range(len(steps) - 1, -1, -1):
        if steps[i][0].split("#", 1)[0].startswith("value"):
            return i
    return -1


def _stands_in(p) -> bool:
    """A main rule that writes nothing (a `binding` with no code for this value) is stood in for when one of its
    `also` rules writes the value as another value[x] of the same element: a QuestionnaireResponse answer the model
    defines by a codebook, not a code, is a valueString where its siblings are a valueCoding (4.0.5)."""
    i = _value_at(p.steps)
    if i < 0:
        return False
    for e in p.extras:
        j = _value_at(e.steps)
        if e.text is not None and j == i and list(e.steps[:j]) == list(p.steps[:i]) and e.steps[j][0] != p.steps[i][0]:
            return True
    return False


def _join(steps) -> str:
    return "/".join(n.split("#", 1)[0] for n, _ in steps)


__all__ = ["FHIRMapper", "EV_TABLE", "FHIR_VERSION", "VERSIONS"]
