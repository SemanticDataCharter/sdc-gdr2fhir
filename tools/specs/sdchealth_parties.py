"""What every SDCHealth chained record's parties hold, in FHIR R4 (HL7 Europe Base 2.0.1's maps), and the helpers
the chained specs share. The rules are the Laboratory Report spec's (`sdchealth_lab_report.py`), word for word.
"""
from common import V, C

LAB = "http://hl7.eu/fhir/laboratory/StructureDefinition/"
EU_BASE = "http://hl7.eu/fhir/base/StructureDefinition/"
V2_0203 = "http://terminology.hl7.org/CodeSystem/v2-0203"
PRACTITIONER = {"resourceType": "Practitioner", "meta/profile": f"{EU_BASE}practitioner-eu-core"}
#: The Laboratory Report model the chained records join (library decision 12).
LAB_REPORT = "zptekdommw56yiz9lqjy5dga"
B = "/Bundle"
#: The parent's entries a chained record writes into or names (the Laboratory Report mapping's tags).
COMP = f"{B}/=entry#comp/=resource"
DR = f"{B}/=entry#dr/=resource"
ORDER = f"{B}/=entry#sr/=resource"
PATIENT = "{entry#patient}"
#: A chained record's subject is the report's: the chain is about one patient (checked by identifier).
SUBJECT_REASON = ("the report's subject: a chained record is about the report's patient (sdc-gdr2fhir checks that "
                  "their identifiers agree), whose Patient entry the report writes")


def k(path, value):
    return {"to": path, "transform": "constant", "value": value}


def E(element, to, transform="copy", **kw):
    return {"element": element, "to": to, "transform": transform, **kw}


def coded_type(label):
    from common import coded
    return V(label, "type/text", derive=coded("type/coding"))


def coded_text(label, to, **kw):
    from common import coded
    at = to.rsplit("/", 1)[0]
    return V(label, to, derive=coded(f"{at}/coding"), **kw)


PARTY_DETAILS = [
    # ---------------------------------------------------------------- what a party's details hold (any party)
    # BASE map-ehdshumanname: given, family, prefix, suffix, text, use one to one
    C("Human Name", "name"),
    V("Given Name (Person)", "given"),
    V("Surname (Person)", "family"),
    V("Name Prefix", "prefix"),
    V("Name Suffix", "suffix"),
    V("Name As Written", "text"),
    V("Name Use", "use", "binding", prefix="http://hl7.org/fhir/name-use"),
    # BASE map-ehdsaddress. Its street, house number and post box go in extensions of a line, which this mapping does
    # not write: the model's thoroughfare, premises and delivery service are lines of their own (declared).
    C("Address", "address"),
    V("Address (Line 1)", "+line"),
    V("Thoroughfare", "+line"),
    V("Premises Identifier", "+line"),
    V("Delivery Service", "+line"),
    V("City Name", "city"),
    V("Postal Code", "postalCode"),
    V("Address Use", "use", "binding", prefix="http://hl7.org/fhir/address-use"),
    V("Address Type", "type", "binding", prefix="http://hl7.org/fhir/address-type"),
    C("Country", "."),
    # BASE map-ehdsaddress: country -> Address.country (a name) or a country-code extension. Address.country is one
    # string: the ISO 3166 code is written there (FHIR R4 recommends the ISO 3166 code); the name has no second place.
    V("Country Code ISO 3166", "country"),
    V("Country Name", "-", "omit",
      reason="FHIR's Address.country is one string, which holds the record's ISO 3166 code; the country's name has no "
             "second place (HL7 Europe Base's country-code extension is not written here)"),
    # BASE map-ehdstelecom: type -> system, use and value one to one. An email beside a phone is a second ContactPoint.
    C("Telecom", "telecom"),
    V("Phone Number", "value"),
    V("Email Address", "../+telecom/value", also=[k("../+telecom/system", "email")]),
    V("Contact Method", "system", "binding", prefix="http://hl7.org/fhir/contact-point-system"),
    V("Contact Use", "use", "binding", prefix="http://hl7.org/fhir/contact-point-use"),
    # BASE map-ehdspatient / map-ehdshealthprofessional: identifier -> identifier. The issuer is a name: assigner.
    C("Person Identifier", "identifier"),
    V("Identifier Value", "value"),
    V("Issuing Authority", "assigner/display"),
    coded_type("Person Identifier Type"),
    # a driver's licence, passport or social security number: an identifier of its own, typed by the v2-0203 code the
    # model links the component to (a lookup)
    *[V(label, "../+identifier/value", also=[k("../+identifier/type/coding/system", V2_0203),
                                             {"to": "../+identifier/type/coding/code", "transform": "link",
                                              "system": V2_0203}])
      for label in ("Driver License Number", "Passport Number", "Social Security Number")],
    V("Country Code ISO 3166", "-", "omit", within=["Person Identifier"],
      reason="FHIR's Identifier has no element for the country that issued it"),
    C("Organization Identifier", "identifier"),
    coded_type("Organization Identifier Type"),
    # BASE map-ehdspatient: administrativeGender, dateOfBirth, deceased[x] one to one
    V("Administrative Gender", "gender", "binding", prefix="http://hl7.org/fhir/administrative-gender"),
    V("Date of Birth", "birthDate"),
    V("Deceased Indicator", "deceasedBoolean"),
    V("Deceased Date", "deceasedDateTime"),
    # BASE map-ehdsorganisation: name, type, partOf (here a name: partOf by display)
    V("Organization Name", "name"),
    coded_text("Organization Type", "type/text"),
    V("Organisation Part Of", "partOf/display"),

]

# ---------------------------------------------------------------- the 2026-11-21 revision (PRD decision 22)
#: The Laboratory Report each revision's chained records join. The first revision (2026-11-20) is LAB_REPORT; the
#: library's requiredness and units revision of 2026-11-21 published new versions of every Laboratory model.
LAB_REPORT_2 = "rguwjl3y1d2cxmcv7vooocji"
REVISION_DATE = "2026-11-21"
UCUM = "http://unitsofmeasure.org"


def chained_to(rules, parent: str, tag: str | None = None):
    """The rules with their `@chained-to` directive naming another parent model (and, if given, another entry)."""
    out = []
    for r in rules:
        a = r.get("attributes", {})
        if "@chained-to" in a:
            old_parent, old_tag = a["@chained-to"].split()
            r = {**r, "attributes": {**a, "@chained-to": f"{parent} {tag or old_tag}"}}
        out.append(r)
    return out


def ucum(rules):
    """The rules with every quantity's units written as a UCUM code (2026-11-21: a quantity's units take any UCUM code,
    the pattern `[!-~]{1,60}`, where the first revision allowed only the text "UCUM Units"): the units as the Quantity's
    `code` (the writer adds `unit`, the same symbol) and the system UCUM beside the value."""
    out = []
    for r in rules:
        u = r.get("units")
        if u and u.get("to") == "@unit":
            at = r["to"].rsplit("/", 1)[0] if "/" in r["to"] else ""
            system = f"{at}/system" if at else "system"
            r = {**r, "units": {**u, "to": "@code"}, "also": [*r.get("also", []), k(system, UCUM)]}
        out.append(r)
    return out


def without(rules, *contexts):
    """The rules less those within any of `contexts` (a Participation the revised model no longer has)."""
    return [r for r in rules if not set(r.get("within", [])) & set(contexts)
            and r.get("cluster") not in contexts and r.get("component") not in contexts]
