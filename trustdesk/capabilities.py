"""Capability definitions and lexicons for the Facility Trust Desk.

Each capability has a set of positive terms (direct evidence) and indirect terms
(suggestive but not confirming). A shared list of negation cues is used to detect
contradicting / non-functional / referred-elsewhere mentions near a match.
"""
from collections import OrderedDict

# Free-text fields in a facility record that we scan for evidence.
TEXT_FIELDS = ["services_text", "infrastructure_text", "notes_text"]
FIELD_LABELS = {
    "services_text": "Services",
    "infrastructure_text": "Infrastructure",
    "notes_text": "Field notes",
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
        "indirect": ["icu bed", "critical care unit"],
    }),
    ("maternity", {
        "label": "Maternity / Delivery",
        "positive": ["maternity", "labour room", "labor room", "delivery",
                     "deliveries", "obstetric", "caesarean", "c-section", "lscs",
                     "institutional delivery", "antenatal"],
        "indirect": ["gynaecologist", "gynecologist", "anm", "midwife"],
    }),
    ("emergency", {
        "label": "Emergency / 24x7 Casualty",
        "positive": ["emergency", "casualty", "24x7", "24/7", "round the clock",
                     "trauma", "accident and emergency"],
        "indirect": ["on call doctor", "duty doctor"],
    }),
    ("surgery", {
        "label": "Surgery / Operation Theatre",
        "positive": ["operation theatre", "operation theater", "ot",
                     "surgery", "surgical", "major surgery", "minor ot"],
        "indirect": ["surgeon", "anaesthetist", "anesthetist"],
    }),
    ("bloodbank", {
        "label": "Blood Bank",
        "positive": ["blood bank", "bloodbank", "blood transfusion"],
        "indirect": ["blood storage", "blood storage unit"],
    }),
    ("diagnostics", {
        "label": "Diagnostics (Lab & Imaging)",
        "positive": ["x-ray", "xray", "ultrasound", "usg", "ct scan", "mri",
                     "laboratory", "pathology", "ecg"],
        "indirect": ["sample collection", "lab technician"],
    }),
])
