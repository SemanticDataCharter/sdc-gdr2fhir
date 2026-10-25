"""The FAIR Data Demo's NHANES Medication model as a FHIR R4 Bundle.

The participant is a Patient; the medicine a MedicationStatement, its reasons the ICD-10-CM diagnoses the record
carries; the survey's counts are items of a QuestionnaireResponse. NHANES asks whether a prescription medicine was
taken in the past month: Yes is the statement's status active, No not-taken (declared).
"""
from common import PATIENT, SUBJECT, C, V, bundle, item, system_of

TITLE = "NHANES Medication (FAIR Data Demo) to HL7 FHIR R4 Bundle"
ID = "nhanes-medication-fhir-r4"
VERSION = 1
AUTHOR = "Axius SDC, Inc."
DATE = "2026-10-25"
DESCRIPTION = ("The NHANES Medication model's values in a FHIR R4 Bundle of type collection: a Patient, a "
               "MedicationStatement with its ICD-10-CM reasons, and the survey's counts as QuestionnaireResponse items.")
MED = "=entry#med/=resource"
STATEMENT = {"resourceType": "MedicationStatement", **SUBJECT}
DRUG_SYSTEM = "https://wwwn.cdc.gov/Nchs/Nhanes/2017-2018/RXQ_RX_J.htm#RXDDRGID"

RULES = [
    *bundle("NHANES Medication Governed Record", "NHANES Medication"),
    *PATIENT,
    V("Taken Prescription Medicine, Past Month (RXDUSE)", f"{MED}/status", "code",
      table={"Yes": "active", "No": "not-taken"}, attributes=STATEMENT),
    V("Generic Drug Code (RXDDRGID)", f"{MED}/medicationCodeableConcept/coding/code", attributes=STATEMENT,
      also=[{"to": f"{MED}/medicationCodeableConcept/coding/system", "transform": "constant", "value": DRUG_SYSTEM}]),
    V("Generic Drug Name (RXDDRUG)", f"{MED}/medicationCodeableConcept/text", attributes=STATEMENT),
    *[C(f"Medication Reason {n}", ".", order=n) for n in range(1, 4)],
    C("Diagnosis (ICD-10-CM)", f"{MED}/reasonCode"),
    V("Diagnosis Code (ICD-10-CM)", "coding/code", derive=system_of("coding/system")),
    V("Code Display Text", "text"),               # the record's own words for the code: the CodeableConcept's text
    V("Code System: ICD-10-CM", "coding/system"),
    item("Number of Days Taken Medicine (RXDDAYS)"),
    item("Number of Prescription Medicines Taken (RXDCOUNT)"),
]
