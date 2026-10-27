"""The FAIR Data Demo's NHANES Medication 4.3.0 model as a FHIR R4 Bundle.

As nhanes_medication.py, with the reason NHANES records as a prevention code (I21.P, prevent heart attack): a
reasonCode whose Coding carries the code under NHANES's own code system, the RXQ_RX_J documentation the model fixes as
the code system, never ICD-10-CM (ICD-10-CM has no I21.P; FAIR Data Demo SOURCE-ERRATA.md). A reason NHANES records as
unknown, refused or don't know is an Exceptional Value in the ICD-10-CM code, written as FHIR's data-absent-reason.
"""
from common import C, V, _links
from nhanes_medication import AUTHOR, MED, RULES as BASE, STATEMENT  # noqa: F401

TITLE = "NHANES Medication 4.3.0 (FAIR Data Demo) to HL7 FHIR R4 Bundle"
ID = "nhanes-medication-4.3.0-fhir-r4"
VERSION = 1
DATE = "2026-10-27"
DESCRIPTION = ("The NHANES Medication 4.3.0 model's values in a FHIR R4 Bundle of type collection: a Patient, a "
               "MedicationStatement with its reasons (ICD-10-CM diagnoses, or NHANES prevention codes under NHANES's own "
               "code system), and the survey's counts as QuestionnaireResponse items.")

NHANES_RX = "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/RXQ_RX_J.htm"


def own_system(at: str):
    """derive: the code system the model fixes for NHANES's prevention codes, read from the component's exactMatch.
    Not one of the systems system_of() knows (it is no standard's code system), so it is copied from the model here,
    for this component only, and checked to be the RXQ_RX_J documentation."""
    def derive(component, _enums):
        iris = list(_links(component, "#exactMatch"))
        assert NHANES_RX in iris, ("the prevention code's exactMatch is not the RXQ_RX_J documentation", iris)
        return {"also": [{"to": at, "transform": "constant", "value": NHANES_RX}]}
    return derive


RULES = [
    *BASE,
    C("Prevention Reason (NHANES)", f"{MED}/reasonCode"),
    V("Prevention Reason Code (NHANES)", "coding/code", derive=own_system("coding/system")),
    V("Code System: NHANES Prevention Reason", "coding/system"),
]
