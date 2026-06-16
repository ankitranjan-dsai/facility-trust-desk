"""Capability definitions and lexicons for the Facility Trust Desk.

Evidence is scanned across the dataset's claim-bearing free-text fields
(description, capability, procedure, equipment, specialties, source_urls).
Each capability has positive terms (direct evidence) and indirect terms
(suggestive but not confirming). A shared list of negation cues flags
contradicting / non-functional / referred-elsewhere mentions near a match.
"""
from collections import OrderedDict

# Claim-bearing free-text fields in a facility record that we scan for evidence.
# These match the provided 10k dataset's evidence columns.
TEXT_FIELDS = ["description", "capability", "procedure", "equipment", "specialties", "source_urls"]
FIELD_LABELS = {
    "description": "Description",
    "capability": "Capabilities",
    "procedure": "Procedures",
    "equipment": "Equipment",
    "specialties": "Specialties",
    "source_urls": "Source URLs",
}

# Words/phrases that, near a matched term, indicate the capability is absent,
# broken, or referred elsewhere rather than actually delivered on site.
NEGATION_CUES = [
    "no", "not", "non", "without", "lack", "lacks", "lacking", "nil",
    "absent", "unavailable", "out of order", "non-functional", "non functional",
    "not functional", "refer", "referred", "referral", "closed", "broken",
    "n/a", "zero", "defunct", "yet to", "under construction", "not available",
    "no functional",
]

CAPABILITIES = OrderedDict([
    ("icu", {
        "label": "ICU / Critical Care",
        "positive": ["icu", "intensive care", "critical care", "ventilator",
                     "hdu", "high dependency unit"],
        "indirect": ["icu bed", "critical care unit", "intensivist"],
    }),
    ("nicu", {
        "label": "NICU / Newborn Care",
        "positive": ["nicu", "neonatal intensive care", "neonatal icu", "sncu",
                     "special newborn care unit", "special newborn care", "neonatal unit"],
        "indirect": ["neonatologist", "radiant warmer", "phototherapy"],
    }),
    ("maternity", {
        "label": "Maternity / Delivery",
        "positive": ["maternity", "labour room", "labor room", "delivery", "deliveries",
                     "obstetric", "caesarean", "c-section", "lscs", "institutional delivery",
                     "antenatal"],
        "indirect": ["gynaecologist", "gynecologist", "obstetrician", "anm", "midwife"],
    }),
    ("emergency", {
        "label": "Emergency / 24x7 Casualty",
        "positive": ["emergency", "casualty", "24x7", "24/7", "round the clock",
                     "accident and emergency"],
        "indirect": ["on call doctor", "duty doctor", "ambulance"],
    }),
    ("trauma", {
        "label": "Trauma Care",
        "positive": ["trauma", "trauma care", "trauma centre", "trauma center", "polytrauma"],
        "indirect": ["orthopaedic surgeon", "orthopedic surgeon", "accident"],
    }),
    ("oncology", {
        "label": "Oncology / Cancer Care",
        "positive": ["oncology", "cancer", "chemotherapy", "chemo", "radiotherapy",
                     "radiation therapy", "tumour", "tumor", "carcinoma", "oncosurgery"],
        "indirect": ["oncologist", "linear accelerator"],
    }),
    ("surgery", {
        "label": "Surgery / Operation Theatre",
        "positive": ["operation theatre", "operation theater", "ot", "surgery", "surgical",
                     "major surgery", "minor ot", "laparoscopic"],
        "indirect": ["surgeon", "anaesthetist", "anesthetist"],
    }),
    ("diagnostics", {
        "label": "Diagnostics (Lab & Imaging)",
        "positive": ["x-ray", "xray", "ultrasound", "usg", "ct scan", "mri",
                     "laboratory", "pathology", "ecg", "sonography"],
        "indirect": ["sample collection", "lab technician"],
    }),
    ("bloodbank", {
        "label": "Blood Bank",
        "positive": ["blood bank", "bloodbank", "blood transfusion"],
        "indirect": ["blood storage", "blood storage unit"],
    }),
])
