"""Deterministic evidence extraction.

Finds verbatim spans of capability-related terms in a facility's free-text
fields and flags whether each match sits inside a negation context (absent,
broken, referred elsewhere). Because spans are real substrings of the source,
they double as guaranteed-honest citations — the model can never invent them.
"""
import re
from dataclasses import dataclass
from typing import List, Dict

from .capabilities import CAPABILITIES, TEXT_FIELDS, NEGATION_CUES


@dataclass
class Span:
    field: str
    start: int
    end: int
    text: str
    term: str
    kind: str            # 'positive' or 'indirect'
    negated: bool = False


@dataclass
class EvidenceResult:
    capability: str
    spans_by_field: Dict[str, List[Span]]
    flat: List[Span]
    deterministic_verdict: str
    confidence_label: str
    confidence: float
    reasons: List[str]


_WINDOW_BEFORE = 30
_WINDOW_AFTER = 28

# Negation usually PRECEDES the term ("no ICU", "without OT"), so the backward
# window honours every cue. Only a subset is meaningful when it FOLLOWS the term
# ("ventilator out of order", "ICU nil", "maternity referred"), and the forward
# window stops at a clause boundary so a negation about a *different* item in the
# next clause ("SNCU. No adult ICU") cannot leak onto this one.
_BACK_PATTERNS = [re.compile(r'(?<![a-z0-9])' + re.escape(c) + r'(?![a-z0-9])') for c in NEGATION_CUES]
_FORWARD_CUES = [
    "out of order", "non-functional", "non functional", "not functional",
    "referred", "referral", "refer", "under construction", "closed", "broken",
    "defunct", "not available", "unavailable", "yet to", "nil", "no", "na",
    "zero", "absent",
]
_FWD_PATTERNS = [re.compile(r'(?<![a-z0-9])' + re.escape(c) + r'(?![a-z0-9])') for c in _FORWARD_CUES]


def _is_negated(text_lower: str, start: int, end: int) -> bool:
    before = text_lower[max(0, start - _WINDOW_BEFORE):start]
    if any(p.search(before) for p in _BACK_PATTERNS):
        return True
    after = re.split(r"[.;]", text_lower[end:end + _WINDOW_AFTER], 1)[0]
    return any(p.search(after) for p in _FWD_PATTERNS)


def _find_terms(text: str, terms: List[str], kind: str, fieldname: str) -> List[Span]:
    spans: List[Span] = []
    low = text.lower()
    for term in terms:
        # allow a simple trailing plural (ventilator -> ventilators, x-ray -> x-rays)
        pat = re.compile(r'(?<![a-z0-9])' + re.escape(term.lower()) + r's?(?![a-z0-9])')
        for m in pat.finditer(low):
            s, e = m.start(), m.end()
            spans.append(Span(field=fieldname, start=s, end=e, text=text[s:e],
                              term=term, kind=kind, negated=_is_negated(low, s, e)))
    return spans


def _dedupe(spans: List[Span]) -> List[Span]:
    """Drop spans fully contained in a longer span at the same start region."""
    spans = sorted(spans, key=lambda x: (x.start, -(x.end - x.start)))
    kept: List[Span] = []
    for sp in spans:
        if any(sp.start >= k.start and sp.end <= k.end for k in kept):
            continue
        kept.append(sp)
    return sorted(kept, key=lambda x: x.start)


def _score(spans: List[Span]):
    pos = [s for s in spans if s.kind == "positive" and not s.negated]
    neg = [s for s in spans if s.negated]
    ind = [s for s in spans if s.kind == "indirect" and not s.negated]
    distinct_pos = {s.term for s in pos}
    reasons: List[str] = []

    if pos and neg:
        verdict, label, conf = "Conflicting", "Conflicting — needs review", 0.45
        reasons.append("Both supporting and contradicting language present.")
    elif len(distinct_pos) >= 2:
        verdict, label, conf = "Supported", "Strong evidence", 0.90
    elif pos:
        verdict, label, conf = "Likely", "Some evidence", 0.68
    elif neg:
        verdict, label, conf = "Unsupported", "Contradicted by record", 0.80
        reasons.append("Record explicitly says this is absent / broken / referred out.")
    elif ind:
        verdict, label, conf = "Weak", "Indirect only", 0.40
        reasons.append("Only indirect signals (e.g. a relevant specialist) — not confirmed.")
    else:
        verdict, label, conf = "Not stated", "No evidence in record", 0.12
        reasons.append("No supporting or contradicting text found.")

    def _uniq(spans):
        seen, out = set(), []
        for s in spans:
            key = s.text.lower()
            if key not in seen:
                seen.add(key)
                out.append(s.text)
        return out

    if pos:
        reasons.append("Supporting: " + ", ".join(f'"{t}"' for t in _uniq(pos)[:4]))
    if neg:
        reasons.append("Contradicting: " + ", ".join(f'"{t}"' for t in _uniq(neg)[:4]))
    return verdict, label, conf, reasons


def extract(row, cap_key: str) -> EvidenceResult:
    if cap_key not in CAPABILITIES:
        raise ValueError(f"Unknown capability key: {cap_key}")
    cap = CAPABILITIES[cap_key]
    spans_by_field: Dict[str, List[Span]] = {}
    flat: List[Span] = []
    for f in TEXT_FIELDS:
        text = str(row.get(f) or "").strip()
        if not text:
            continue
        sp = _find_terms(text, cap["positive"], "positive", f) + \
            _find_terms(text, cap["indirect"], "indirect", f)
        sp = _dedupe(sp)
        if sp:
            spans_by_field[f] = sp
            flat.extend(sp)
    verdict, label, conf, reasons = _score(flat)
    return EvidenceResult(cap_key, spans_by_field, flat, verdict, label, conf, reasons)
