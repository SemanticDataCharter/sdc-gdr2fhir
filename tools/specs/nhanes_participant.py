"""The FAIR Data Demo's NHANES Participant model as a FHIR R4 Bundle.

The participant is a Patient; each blood pressure reading, the heart rate and each laboratory result an Observation
with the LOINC code the model binds; smoking status and each chronic condition indicator an Observation whose code is
the concept the model binds (LOINC for smoking status, the SNOMED CT subject of each condition) and whose value is the
answer's LOINC answer code; every other survey answer an item of one QuestionnaireResponse. A condition indicator is an
answer to "has a doctor ever told you", so it is an Observation of the answer, not a Condition.
"""
from common import (OBSERVATION_CATEGORY, PATIENT, SUBJECT, C, V, answer_observation, bundle, item,
                    observation, system_of, code_of)
from sdc_gdr2fhir.codes import LOINC, UCUM, UCUM_CODES

TITLE = "NHANES Participant (FAIR Data Demo) to HL7 FHIR R4 Bundle"
ID = "nhanes-participant-fhir-r4"
VERSION = 1
AUTHOR = "Axius SDC, Inc."
DATE = "2026-10-25"
DESCRIPTION = ("The NHANES Participant model's values in a FHIR R4 Bundle of type collection. LOINC and SNOMED CT codes "
               "and answer codes are the model's own bindings; resources and places are declared.")

LABS = ["Basophils Number", "Basophils Percent", "Eosinophils Number", "Eosinophils Percent", "Hematocrit",
        "Hemoglobin", "Lymphocyte Number", "Lymphocyte Percent", "Mean Cell Hemoglobin",
        "Mean Cell Hemoglobin Concentration", "Mean Cell Volume", "Mean Platelet Volume", "Monocyte Number",
        "Monocyte Percent", "Nucleated Red Blood Cells", "Platelet Count", "Red Blood Cell Count",
        "Red Cell Distribution Width", "Segmented Neutrophils Number", "Segmented Neutrophils Percent",
        "Total Cholesterol", "Total Cholesterol (SI)", "White Blood Cell Count"]
CONDITIONS = ["Alzheimer's Disease or Related Disorder", "Angina", "Arthritis", "Asthma", "Cancer", "Chronic Bronchitis",
              "Congestive Heart Failure", "COPD", "Coronary Heart Disease", "Depression", "Diabetes", "Emphysema",
              "Heart Attack", "High Blood Pressure", "High Cholesterol", "Kidney Disease", "Liver Condition",
              "Osteoporosis", "Skin Cancer", "Stroke", "Thyroid Problem"]
SURVEY = [
    "Arm Selected (BPAARM)", "Coded Cuff Size (BPACSZ)", "Pulse Regular or Irregular (BPXPULS)",
    "Maximum Inflation Level (BPXML1)",
    "Annual Household Income (INDHHIN2)", "Citizenship Status (DMDCITZN)", "Country of Birth (DMDBORN4)",
    "Education Level - Adults 20+ (DMDEDUC2)", "Gender (RIAGENDR)", "Marital Status (DMDMARTL)",
    "Pregnancy Status at Exam (RIDEXPRG)", "Race/Hispanic Origin with NH Asian (RIDRETH3)", "Veteran Status",
    "Are you pregnant now?", "Current Educational Attainment", "Marital Status", "Race/Ethnicity Self-Identification",
    "Age in Months at Screening (RIDAGEMN)", "Total Number of People in the Household (DMDHHSIZ)", "Age",
    "Ratio of Family Income to Poverty (INDFMPIR)",
    "Doctor Ever Said You Were Overweight (MCQ080)", "Still Have Asthma (MCQ035)", "Condition Indicator Basis",
    "Difficulty Dressing Yourself (PFQ061L)", "Difficulty Getting In and Out of Bed (PFQ061J)",
    "Difficulty Lifting or Carrying (PFQ061E)", "Difficulty Standing for Long Periods (PFQ061M)",
    "Difficulty Standing Up from an Armless Chair (PFQ061I)", "Difficulty Stooping, Crouching or Kneeling (PFQ061D)",
    "Difficulty Walking a Quarter Mile (PFQ061B)", "Difficulty Walking Between Rooms (PFQ061H)",
    "Difficulty Walking Up Ten Stairs (PFQ061C)", "Experience Confusion or Memory Problems (PFQ057)",
    "Limitations Keeping You from Working (PFQ049)", "Need Special Equipment to Walk (PFQ054)",
    "Do You Now Smoke Cigarettes (SMQ040)", "Ever Used an E-cigarette (SMQ900)",
    "Smoked at Least 100 Cigarettes in Life (SMQ020)", "Age Started Smoking Cigarettes Regularly (SMD030)",
    "Average Cigarettes per Day, Past 30 Days (SMD650)",
    "Data Release Cycle (SDDSRVYR)", "Interview/Examination Status (RIDSTATR)", "Masked Variance Pseudo-PSU (SDMVPSU)",
    "Masked Variance Pseudo-Stratum (SDMVSTRA)", "Full Sample 2 Year Interview Weight (WTINT2YR)",
    "Full Sample 2 Year MEC Exam Weight (WTMEC2YR)",
]
MM_HG = {"to": "@code", "transform": "code", "table": {"mmHg": UCUM_CODES["mmHg"]}}


def bp_component(label):
    at = "+component"
    return V(label, f"{at}/valueQuantity/value", units=MM_HG,
             also=[{"to": f"{at}/valueQuantity/system", "transform": "constant", "value": UCUM}],
             derive=code_of(f"{at}/code"))


RULES = [
    *bundle("NHANES Participant Governed Record", "NHANES Participant"),
    *PATIENT,
    V("Administrative Gender", "=entry#patient/=resource/gender", "binding", prefix="http://hl7.org/fhir/administrative-gender",
      attributes={"resourceType": "Patient"}),

    # each blood pressure reading: an Observation (the vital signs blood pressure panel), systolic and diastolic its
    # components
    *[C(f"Blood Pressure Reading {n}", ".", order=n) for n in range(1, 4)],
    C("Blood Pressure", "+entry/resource", attributes={
        "resourceType": "Observation", **SUBJECT,
        "category/coding/system": OBSERVATION_CATEGORY, "category/coding/code": "vital-signs",
        "code/coding/system": LOINC, "code/coding/code": "85354-9", "code/text": "Blood pressure panel"}),
    V("Observation Status", "status", "binding", prefix="http://hl7.org/fhir/observation-status"),
    V("Observation Date Time", "effectiveDateTime", "format", format="%Y-%m-%d"),
    bp_component("Systolic Blood Pressure"),
    bp_component("Diastolic Blood Pressure"),
    C("Body Site (SNOMED CT)", "bodySite"),
    V("Body Site Code (SNOMED CT)", "coding/code", derive=system_of("coding/system")),
    V("Code Display Text", "coding/display"),
    V("Code System: SNOMED CT", "coding/system"),
    observation("Heart Rate", "vital-signs"),

    *[observation(label, "laboratory") for label in LABS],
    answer_observation("Smoking Status", "social-history"),
    *[answer_observation(f"Condition: {c}", "survey", predicate="/subject") for c in CONDITIONS],
    *[item(label) for label in SURVEY],
]
