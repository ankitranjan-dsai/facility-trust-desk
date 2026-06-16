"""Combine deterministic evidence with the LLM judge into a final, cited verdict.

Hard rule enforced here regardless of what the model says:
a "Supported"/"Likely" verdict REQUIRES at least one real, non-negated citation
from the facility record. No citation -> no positive claim. This is what makes
the app trustworthy ("cite the underlying facility text for any important claim").
"""
from dataclasses import dataclass, field
from typing import List

from . import evidence, model_client
from .capabilities import CAPABILITIES, TEXT_FIELDS, FIELD_LABELS

# verdict -> (label, default confidence, colour)
VERDICT_META = {
    "Supported":   ("Strong evidence",            0.90, "#1a7f37"),
    "Likely":      ("Partial evidence",           0.68, "#3a7d44"),
    "Conflicting": ("Conflicting — needs review", 0.45, "#b35900"),
    "Unsupported": ("Contradicted by record",     0.80, "#b3261e"),
    "Weak":        ("Indirect only",              0.40, "#8a6d00"),
    "Not stated":  ("No evidence in record",      0.12, "#6b7280"),
    "Unverified":  ("Claimed but not citable",    0.30, "#8a6d00"),
}
_ALLOWED = set(VERDICT_META)


@dataclass
class Assessment:
    capability: str
    label_name: str
    verdict: str
    confidence: float
    color: str
    rationale: str
    provider: str
    citations: List[evidence.Span] = field(default_factory=list)
    data_quality: List[str] = field(default_factory=list)
    deterministic_verdict: str = ""


def _map_verdict(v: str) -> str:
    if not v:
        return "Not stated"
    v = v.strip().capitalize() if v.strip().lower() not in ("not stated",) else "Not stated"
    for a in _ALLOWED:
        if a.lower() == str(v).lower():
            return a
    return "Not stated"


def _clamp(x, default=0.5):
    try:
        return max(0.0, min(1.0, float(x)))
    except Exception:
        return default


def build_source_text(row) -> str:
    parts = []
    for f in TEXT_FIELDS:
        t = str(row.get(f) or "").strip()
        if t:
            parts.append(f"[{FIELD_LABELS.get(f, f)}] {t}")
    return "\n".join(parts)


def _missing(v) -> bool:
    return v is None or str(v).strip().lower() in ("", "nan", "none")


def _data_quality(row) -> List[str]:
    notes = []
    total_text = sum(len(str(row.get(f) or "").strip()) for f in TEXT_FIELDS)
    if total_text < 40:
        notes.append("Sparse record — very little evidence text to assess; treat verdicts as low-information.")
    if _missing(row.get("description")):
        notes.append("No description text.")
    thin = [f for f in ("capability", "procedure", "equipment") if _missing(row.get(f))]
    if thin:
        notes.append("Missing evidence field(s): " + ", ".join(thin) + ".")
    if _missing(row.get("capacity")):
        notes.append("Bed capacity not reported.")
    return notes


def _offline_rationale(ev: evidence.EvidenceResult, cap_label: str) -> str:
    base = " ".join(ev.reasons)
    return f"{cap_label}: {base} (Rule-based verdict — no language model was reachable, so this rests purely on matched text.)"


def assess(row, cap_key: str) -> Assessment:
    cap_label = CAPABILITIES[cap_key]["label"]
    ev = evidence.extract(row, cap_key)
    positives = [s for s in ev.flat if s.kind == "positive" and not s.negated]
    negatives = [s for s in ev.flat if s.negated]
    indirects = [s for s in ev.flat if s.kind == "indirect" and not s.negated]

    source_text = build_source_text(row)
    llm = model_client.judge_with_llm(source_text, cap_label) if source_text else None

    if llm:
        verdict = _map_verdict(llm.get("verdict"))
        confidence = _clamp(llm.get("confidence"), default=VERDICT_META.get(verdict, (None, 0.5))[1])
        rationale = (llm.get("rationale") or "").strip() or _offline_rationale(ev, cap_label)
        provider = llm.get("provider", "llm")
    else:
        verdict = ev.deterministic_verdict
        confidence = ev.confidence
        rationale = _offline_rationale(ev, cap_label)
        provider = "offline (rule-based)"

    # --- Trust guards: a positive verdict must be backed by a real citation ---
    downgraded = False
    if verdict in ("Supported", "Likely") and not positives:
        verdict = "Weak" if indirects else ("Unverified" if llm else "Not stated")
        rationale += "  ⚠ Downgraded: no citable supporting text exists in this record."
        downgraded = True
    if positives and negatives and verdict in ("Supported", "Likely"):
        verdict = "Conflicting"
        rationale += "  ⚠ The record also contains contradicting language — flagged for review."
        downgraded = True

    label_name, default_conf, color = VERDICT_META.get(verdict, VERDICT_META["Not stated"])
    # A downgraded (or rule-based) verdict must not keep an inflated confidence.
    if not llm or downgraded:
        confidence = min(confidence, default_conf)

    def _field_order(field):
        return TEXT_FIELDS.index(field) if field in TEXT_FIELDS else len(TEXT_FIELDS)

    citations = sorted(ev.flat, key=lambda s: (_field_order(s.field), s.start))
    return Assessment(
        capability=cap_key,
        label_name=label_name,
        verdict=verdict,
        confidence=confidence,
        color=color,
        rationale=rationale,
        provider=provider,
        citations=citations,
        data_quality=_data_quality(row),
        deterministic_verdict=ev.deterministic_verdict,
    )


def assess_all(row) -> dict:
    return {k: assess(row, k) for k in CAPABILITIES}
