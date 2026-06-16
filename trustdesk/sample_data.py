"""Synthetic but realistic (messy) Indian health-facility records for local dev.

These deliberately include the hard cases the judges care about: negation
("no ICU, refer"), broken equipment ("ventilator out of order"), partial
capability ("blood storage unit, not full blood bank"), inconsistent casing,
and sparse / missing fields. Swap for the real 10k dataset via env (see data.py).
"""
import pandas as pd

_ROWS = [
    {
        "facility_id": "IND-0001", "name": "District Hospital Nashik",
        "facility_type": "District Hospital", "ownership": "Public",
        "state": "Maharashtra", "district": "Nashik", "beds_total": 320,
        "latitude": 19.9975, "longitude": 73.7898,
        "services_text": "OPD, IPD, 24x7 Casualty & Emergency, Operation Theatre (major & minor surgery), Maternity ward with labour room, Blood Bank functional, ICU 12 beds with ventilators.",
        "infrastructure_text": "X-Ray, USG, CT scan, fully equipped laboratory, 108 ambulance on site.",
        "notes_text": "High footfall; ICU frequently at capacity.",
    },
    {
        "facility_id": "IND-0002", "name": "PHC Khedgaon",
        "facility_type": "Primary Health Centre", "ownership": "Public",
        "state": "Maharashtra", "district": "Nashik", "beds_total": 6,
        "latitude": 19.71, "longitude": 73.99,
        "services_text": "Normal deliveries conducted, antenatal checkups, immunization, basic OPD.",
        "infrastructure_text": "No ICU. No operation theatre. No blood bank. Refer serious and surgical cases to district HQ.",
        "notes_text": "Single medical officer posted.",
    },
    {
        "facility_id": "IND-0003", "name": "CHC Sinnar",
        "facility_type": "Community Health Centre", "ownership": "Public",
        "state": "Maharashtra", "district": "Nashik", "beds_total": 30,
        "latitude": 19.85, "longitude": 74.00,
        "services_text": "Casualty 24x7, labour room, minor OT, X-ray available.",
        "infrastructure_text": "ICU under construction. Ventilator out of order. Blood storage unit (not a full blood bank).",
        "notes_text": "USG machine yet to be installed.",
    },
    {
        "facility_id": "IND-0004", "name": "Apollo Clinic Indiranagar",
        "facility_type": "Private Clinic", "ownership": "Private",
        "state": "Karnataka", "district": "Bengaluru Urban", "beds_total": 0,
        "latitude": 12.97, "longitude": 77.64,
        "services_text": "Consultation, pathology laboratory, ECG, pharmacy.",
        "infrastructure_text": "Tie-up with third party for ambulance.",
        "notes_text": "",
    },
    {
        "facility_id": "IND-0005", "name": "SDH Malegaon",
        "facility_type": "Sub-District Hospital", "ownership": "Public",
        "state": "Maharashtra", "district": "Nashik", "beds_total": 100,
        "latitude": 20.55, "longitude": 74.53,
        "services_text": "ICU AVAILABLE; OT FUNCTIONAL; maternity & caesarean section done; bloodbank NO.",
        "infrastructure_text": "x-ray, usg, laboratory all working.",
        "notes_text": "Data entered by ward clerk, casing inconsistent.",
    },
    {
        "facility_id": "IND-0006", "name": "Rural Hospital Trimbak",
        "facility_type": "Rural Hospital", "ownership": "Public",
        "state": "Maharashtra", "district": "Nashik", "beds_total": 50,
        "latitude": 19.93, "longitude": 73.53,
        "services_text": "OPD, IPD, emergency services not functional after 8 pm.",
        "infrastructure_text": "Maternity referred to FRU at district. Operation theatre present but no anaesthetist.",
        "notes_text": "Blood transfusion via storage unit only.",
    },
    {
        "facility_id": "IND-0007", "name": "Trauma Care Centre Sangamner",
        "facility_type": "Trauma Centre", "ownership": "Public",
        "state": "Maharashtra", "district": "Ahmednagar", "beds_total": 40,
        "latitude": 19.57, "longitude": 74.21,
        "services_text": "24x7 trauma and emergency, accident and emergency, major surgery, ICU with 6 ventilators, blood bank.",
        "infrastructure_text": "CT scan, X-ray, USG, laboratory.",
        "notes_text": "Critical care unit staffed round the clock.",
    },
    {
        "facility_id": "IND-0008", "name": "PHC Igatpuri",
        "facility_type": "Primary Health Centre", "ownership": "Public",
        "state": "Maharashtra", "district": "Nashik", "beds_total": 4,
        "latitude": 19.69, "longitude": 73.56,
        "services_text": "Immunization and OPD only.",
        "infrastructure_text": "",
        "notes_text": "",
    },
    {
        "facility_id": "IND-0009", "name": "Wellcare Maternity Home",
        "facility_type": "Private Nursing Home", "ownership": "Private",
        "state": "Telangana", "district": "Hyderabad", "beds_total": 25,
        "latitude": 17.39, "longitude": 78.49,
        "services_text": "Obstetric care, institutional delivery, LSCS, NICU level 1, antenatal clinic.",
        "infrastructure_text": "Operation theatre for caesarean, ultrasound, laboratory.",
        "notes_text": "No general ICU; adult critical cases referred.",
    },
    {
        "facility_id": "IND-0010", "name": "CHC Deola",
        "facility_type": "Community Health Centre", "ownership": "Public",
        "state": "Maharashtra", "district": "Nashik", "beds_total": 30,
        "latitude": 20.73, "longitude": 74.06,
        "services_text": "Casualty, labour room, surgery (general surgeon visiting twice a week).",
        "infrastructure_text": "X-ray functional. ICU nil. Blood bank nil.",
        "notes_text": "Surgeon not full time — verify before referral.",
    },
    {
        "facility_id": "IND-0011", "name": "Lifeline Multispecialty",
        "facility_type": "Private Hospital", "ownership": "Private",
        "state": "Maharashtra", "district": "Pune", "beds_total": 180,
        "latitude": 18.52, "longitude": 73.85,
        "services_text": "Round the clock emergency, ICU and HDU, cardiac surgery, maternity, blood bank, dialysis.",
        "infrastructure_text": "MRI, CT scan, X-ray, USG, advanced laboratory, ECG.",
        "notes_text": "NABH accredited.",
    },
    {
        "facility_id": "IND-0012", "name": "Sub Centre Pimpalgaon",
        "facility_type": "Sub Centre", "ownership": "Public",
        "state": "Maharashtra", "district": "Nashik", "beds_total": None,
        "latitude": 20.17, "longitude": 73.98,
        "services_text": "ANM available for antenatal checkups and immunization.",
        "infrastructure_text": "No inpatient facility.",
        "notes_text": "Open three days a week.",
    },
]


def load_sample() -> pd.DataFrame:
    return pd.DataFrame(_ROWS)
