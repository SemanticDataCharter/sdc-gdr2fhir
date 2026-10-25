"""The FHIR R4 mapper: a Governed Data Record as a FHIR R4 Bundle of type collection, by a mapping file.

Where the model binds a value to a code FHIR knows (a LOINC code for a laboratory result, a SNOMED CT concept for a
condition, an answer's LOINC answer code, an administrative gender), the code written is the model's own and the
value is a lookup; the mapping file says only where it goes. Everything else is declared.

FHIR is the target that can say most of what an Exceptional Value says: an Observation's value carries a
dataAbsentReason, and any other element carries the data-absent-reason extension, or, for the null flavors
data-absent-reason has no code for, the iso21090-nullFlavor extension with the exact v3 NullFlavor code.
"""
from __future__ import annotations

from sdc_mapper import (DECLARED, JOIN, LOOKUP, LOOKUP_TRANSFORMS, NOT_REPRESENTABLE, PRESERVED, EVRule, IncompleteMapping, MapResult,
                        MappingError, ValueOutcome, join_depth, place)
from sdcreader.record import EXCEPTIONAL_VALUES

from . import __version__
from .codes import absent, model_codes
from .writer import FHIR_VERSION, Builder

#: FHIR R4 writes every ISO 21090 null flavor exactly (codes.absent).
EV_TABLE = {code: EVRule(PRESERVED, target_code=f"{absent(code)[0].rsplit('/', 1)[1]}#{absent(code)[1]}")
            for code in EXCEPTIONAL_VALUES}

#: What a FHIR Bundle cannot hold for any record.
CANNOT_HOLD = [
    "validity windows and the time a value was recorded (act, vtb, vte, tr)",
    "the definitions the model binds each component to, beyond the codes written",
]

#: Elements whose value an Observation (or its component) qualifies with dataAbsentReason.
_OBSERVATION_VALUES = {"valueQuantity", "valueCodeableConcept", "valueString", "valueBoolean", "valueInteger",
                       "valueRange", "valueRatio", "valueSampledData", "valueTime", "valueDateTime", "valuePeriod"}


class FHIRMapper:
    name = "fhir"
    target = "HL7 FHIR"
    target_version = "R4"
    package = "sdc-gdr2fhir"
    version = __version__
    ev_table = EV_TABLE

    def map(self, record, mapping) -> MapResult:
        if mapping is None:
            raise MappingError("FHIR needs a mapping file: the model does not say which resource each value belongs to")
        if mapping.carry_rejected:
            raise MappingError("carry_rejected is not available: a rejected value is never written as data")
        if mapping.exceptional_values:
            raise MappingError("FHIR R4 writes every ISO 21090 code exactly; a mapping cannot change that")
        placements, clusters = place(record, mapping)
        b = Builder()
        notes: dict[int, str] = {}
        later = []
        for p in placements:
            v = p.value
            if p.omitted or p.rule is None or not p.steps:
                continue
            writes = []
            if v.exceptional:
                writes += self._absent(p.steps, p.attribute, v.exceptional.code)
            elif p.text is None:
                notes[v.position] = p.note or "no value to write"
                continue
            else:
                writes.append((self._steps(p.steps, p.attribute), p.text, v.position))
                if p.units_attribute and p.units_text is not None:
                    writes.append((self._steps(p.steps, p.units_attribute), p.units_text, None))
                    if p.units_attribute == "code" and v.units:   # a Quantity: the unit as people read it
                        writes.append((self._steps(p.steps, "unit"), v.units.symbol, None))
            own = list(p.steps[:-1])           # the element the value is written in (a valueQuantity)
            for e in p.extras:
                if e.text is None:
                    continue
                if v.exceptional and list(e.steps[: len(own)]) == own:
                    continue                      # with no value, nothing beside it (a quantity's system) either
                writes.append((self._steps(e.steps, e.attribute), e.text, None))
            writes += [(self._resource(p.steps) + [(part, ("attr",)) for part in k.split("/")], val, None)
                       for k, val in p.attributes.items()]
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
        return [(at + [("url", ("dar",))], extension, None), (at + [("valueCode", ("dar",))], value, None)]

    @staticmethod
    def _where(p) -> str:
        return _join(p.steps) + (f"/{p.attribute}" if p.attribute else "")


def _join(steps) -> str:
    return "/".join(n.split("#", 1)[0] for n, _ in steps)


__all__ = ["FHIRMapper", "EV_TABLE", "FHIR_VERSION"]
