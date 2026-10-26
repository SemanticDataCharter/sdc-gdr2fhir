"""Rules both NHANES models share with FHIR R4, and the helpers that copy what the model binds into a rule.

Labels are the model's; paths are FHIR's JSON, relative to the element of the nearest enclosing cluster that has one.
`+entry/resource/...` is a resource of the value's own; `=entry#patient/=resource/...` joins the Bundle's one Patient
(the tag keeps it apart from other entries). A rule's `attributes` are constant members of the resource its value is
in. `derive` adds what the model binds: the code of the concept a component links to is a `link` rule, an answer's
code a `binding` rule (sdc-mapper 4.3.0), so the mapping file says where each goes and the model supplies it at run
time; the component's own identifier is copied in.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from sdc_gdr2fhir.codes import LOINC, SNOMED, UCUM, coding  # noqa: E402
from sdc_mapper.codes import EXACT_MATCH  # noqa: E402
from sdc_mapper.codes import SUBJECT as DCTERMS_SUBJECT  # noqa: E402

KNOWN_SYSTEMS = {SNOMED, "http://snomed.info/sct", "http://hl7.org/fhir/sid/icd-10-cm", LOINC}
OBSERVATION_CATEGORY = "http://terminology.hl7.org/CodeSystem/observation-category"
SEQN_SYSTEM = "https://wwwn.cdc.gov/Nchs/Nhanes/2017-2018/DEMO_J.htm#SEQN"
SUBJECT = {"subject/reference": "{Patient}"}
#: NHANES records carry no examination date. FHIR R4's vital signs profiles require an effective time, so an
#: Observation is dated by the survey cycle it was collected in (declared): NHANES 2017-2018 (cycle J). A record that
#: carries its own date keeps it; the writer drops the period beside an effectiveDateTime.
SURVEY_CYCLE = {"effectivePeriod/start": "2017-01-01", "effectivePeriod/end": "2018-12-31"}
PROVENANCE_REASON = ("the record's provenance and audit: FHIR's Provenance and AuditEvent require a recorded instant "
                     "with a time zone, and the record's times carry none")


def C(label, to, **kw):
    return {"cluster": label, "to": to, **kw}


def V(label, to, transform="copy", **kw):
    return {"component": label, "to": to, "transform": transform, **kw}


def OMIT_C(label, reason, **kw):
    return {"cluster": label, "to": "-", "transform": "omit", "reason": reason, **kw}


#: The predicates a spec names by their last part (`"#exactMatch"`, `"/subject"`), as sdc-mapper's link reads them.
PREDICATES = {"#exactMatch": EXACT_MATCH, "/subject": DCTERMS_SUBJECT}


def _links(component, *predicates):
    return [t for p, ts in (component.links or {}).items() if p.endswith(predicates) for t in ts]


def concept(component, predicate="#exactMatch"):
    """The LOINC or SNOMED CT concept the model binds a component to."""
    for iri in _links(component, predicate):
        c = coding(iri)
        if c and c.system in (LOINC, SNOMED):
            return c
    return None


def code_of(at: str, predicate="#exactMatch"):
    """derive: `at`/text with the component's label and, where the model binds the component to a LOINC or SNOMED CT
    concept, `at`/coding with its system and, by `link`, its code."""
    def derive(component, _enums):
        also = [{"to": f"{at}/text", "transform": "constant", "value": component.label}]
        c = concept(component, predicate)
        if c:
            also += [{"to": f"{at}/coding/system", "transform": "constant", "value": c.system},
                     {"to": f"{at}/coding/code", "transform": "link", "system": c.system,
                      "predicates": [PREDICATES[predicate]]}]
        return {"also": also}
    return derive


def system_of(at: str):
    """derive: the code system the model names for a coded string (SNOMED CT for a body site, ICD-10-CM)."""
    def derive(component, _enums):
        for iri in _links(component, "#exactMatch", "/source"):
            if iri in KNOWN_SYSTEMS:
                return {"also": [{"to": at, "transform": "constant", "value": iri}]}
        return {}
    return derive


def answer_codes(enums):
    """The code the model binds each value of a token to, for the values bound to a code a Coding can carry; None when
    no value is, or when two values share one (a target could not tell them apart). A value defined by an agency's
    codebook (`DEMO_J.htm#DMDCITZN`) is not a code: it is left out, and written as text (4.0.5)."""
    pairs = {value: c for value, iri in enums if (c := coding(iri)) is not None}
    if not pairs or len(set(pairs.values())) != len(pairs):
        return None
    return pairs


def uncoded(enums) -> list[str]:
    """The values of a token the model defines by something other than a code (an agency's codebook)."""
    pairs = answer_codes(enums) or {}
    return [value for value, _ in enums if value not in pairs]


def coded(at: str):
    """derive: a token as a Coding at `at`: the system and (by `binding`) the code the model binds it to. The system
    comes by a table: written with the code, not beside an Exceptional Value. The value's label is not the Coding's
    display (that is the code system's); a caller writes it as text where FHIR has a place for it. A value with no code
    (`uncoded`) gets no Coding: both parts miss and are left out."""
    def derive(component, enums):
        pairs = answer_codes(enums)
        if pairs is None:
            return {}
        partial = {"on_miss": "omit"} if uncoded(enums) else {}
        systems = {p.system for p in pairs.values()}
        code = ({"to": f"{at}/code", "transform": "binding", "system": next(iter(systems)), **partial} if len(systems) == 1 else
                {"to": f"{at}/code", "transform": "code", "table": {v: p.code for v, p in pairs.items()}, **partial})
        return {"also": [
            {"to": f"{at}/system", "transform": "code", "table": {v: p.system for v, p in pairs.items()}, **partial}, code]}
    return derive


def both(*derives):
    def derive(component, enums):
        out = {}
        for d in derives:
            for k, v in d(component, enums).items():
                out[k] = [*out.get(k, []), *v] if k == "also" else v
        return out
    return derive


# ---------------------------------------------------------------- the Bundle and the Patient
def bundle(governed: str, data: str):
    return [
        C(governed, "Bundle", attributes={"resourceType": "Bundle", "type": "collection"}),
        C(data, "."),
        OMIT_C("Audit Event", PROVENANCE_REASON),
        OMIT_C("PROV Activity", PROVENANCE_REASON),
        OMIT_C("PROV Agent", PROVENANCE_REASON),
    ]


PATIENT = [
    V("Respondent Sequence Number (SEQN)", "=entry#patient/=resource/identifier/value",
      attributes={"resourceType": "Patient"},
      also=[{"to": "=entry#patient/=resource/identifier/system", "transform": "constant", "value": SEQN_SYSTEM}]),
]


# ---------------------------------------------------------------- one Observation per value
def observation(label: str, category: str, status: str = "unknown"):
    """A measured value as an Observation of its own: the LOINC code the model binds, UCUM units, the subject."""
    r = "+entry/resource"
    return V(label, f"{r}/valueQuantity/value",
             units={"to": "@code", "transform": "copy"},
             attributes={"resourceType": "Observation", "status": status, **SUBJECT, **SURVEY_CYCLE,
                         "category/coding/system": OBSERVATION_CATEGORY, "category/coding/code": category},
             also=[{"to": f"{r}/valueQuantity/system", "transform": "constant", "value": UCUM}],
             derive=code_of(f"{r}/code"))


def answer_observation(label: str, category: str, predicate="#exactMatch"):
    """A coded answer as an Observation of its own: the concept the model binds as the code, the answer as a Coding.
    The answer's label is the CodeableConcept's text: a Coding's display is the code system's, not the model's."""
    r = "+entry/resource"
    return V(label, f"{r}/valueCodeableConcept/text",
             attributes={"resourceType": "Observation", "status": "unknown", **SUBJECT, **SURVEY_CYCLE,
                         "category/coding/system": OBSERVATION_CATEGORY, "category/coding/code": category},
             derive=both(code_of(f"{r}/code", predicate), coded(f"{r}/valueCodeableConcept/coding")))


# ---------------------------------------------------------------- the questionnaire answers
QR = "=entry#qr/=resource"
QR_ATTRIBUTES = {"resourceType": "QuestionnaireResponse", "status": "completed", **SUBJECT}


def item(label: str):
    """A survey answer as an item of the record's QuestionnaireResponse: linkId the component's identifier, text its
    label, the answer by its type (a Coding where the model binds each value to a code)."""
    def derive(component, enums):
        t = component.sdc_type
        at = f"{QR}/+item/answer"
        rule = {"also": [{"to": f"{QR}/+item/linkId", "transform": "constant", "value": component.ct_id},
                         {"to": f"{QR}/+item/text", "transform": "constant", "value": component.label}]}
        if t == "XdToken" and answer_codes(enums):
            # valueCoding has no text, and its display is the code system's: the answer is the code the model binds
            system, code = coded(f"{at}/valueCoding")(component, enums)["also"]
            rule.update({k: v for k, v in code.items()})
            rule["also"].append(system)
            if uncoded(enums):
                # a value the model defines by a codebook, not a code: the answer is its text, valueString
                rule["also"].append({"to": f"{at}/valueString", "transform": "code", "on_miss": "omit",
                                     "table": {v: v for v in uncoded(enums)}})
        elif t in ("XdCount", "XdQuantity"):
            rule["to"] = f"{at}/valueQuantity/value"
            rule["units"] = {"to": "@unit", "transform": "copy"}
        elif t == "XdBoolean":
            rule["to"] = f"{at}/valueBoolean"
        else:
            rule["to"] = f"{at}/valueString"
        return rule
    return V(label, "-", attributes=QR_ATTRIBUTES, derive=derive)
