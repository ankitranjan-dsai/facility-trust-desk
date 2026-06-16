"""Facility Trust Desk — Databricks App (Streamlit).

For a non-technical planner: pick a facility, see whether each claimed capability
(ICU, maternity, emergency, surgery, blood bank, diagnostics) is actually backed
by the record's own words — with the evidence highlighted, the uncertainty made
explicit, and the ability to add notes or override a verdict (persisted).
"""
import os
import html

import pandas as pd
import streamlit as st

from trustdesk import data as tdata
from trustdesk import judge, store
from trustdesk.capabilities import CAPABILITIES, TEXT_FIELDS, FIELD_LABELS

st.set_page_config(page_title="Facility Trust Desk", page_icon="🏥", layout="wide")

CSS = """
<style>
/* Theme-aware: inherit Streamlit's light/dark theme via CSS variables, so the app
   looks right in both. Only custom HTML blocks are styled; native widgets keep
   their theming. Colours fall back to light values on older Streamlit. */
.block-container{padding-top:2rem;padding-bottom:2.5rem;max-width:1200px;}

.cap-card{
  border:1px solid rgba(128,128,128,.22);
  border-left:6px solid var(--c,#6b7280);
  border-radius:12px;padding:15px 17px;margin-bottom:12px;
  background:var(--secondary-background-color,#ffffff);
  color:var(--text-color,#12313a);
  box-shadow:0 6px 18px rgba(0,0,0,.06);
}
.cap-head{display:flex;justify-content:space-between;align-items:flex-start;gap:10px;}
.cap-title{font-weight:650;font-size:1.03rem;line-height:1.25;}
.chip{color:#fff;border-radius:999px;padding:3px 11px;font-size:.78rem;font-weight:650;
  white-space:nowrap;letter-spacing:.2px;}
.prov{font-size:.74rem;margin-top:5px;opacity:.6;}
.rationale{font-size:.92rem;margin-top:9px;line-height:1.5;}
.ev{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.82rem;line-height:1.6;
  background:rgba(127,127,127,.09);border:1px solid rgba(128,128,128,.18);
  border-radius:8px;padding:10px 12px;margin:5px 0;white-space:pre-wrap;}
.ev .lbl{font-weight:700;opacity:.65;}
mark.pos{background:rgba(26,127,55,.30);color:inherit;padding:0 3px;border-radius:3px;font-weight:600;}
mark.ind{background:rgba(176,138,0,.34);color:inherit;padding:0 3px;border-radius:3px;}
mark.neg{background:rgba(179,38,30,.32);color:inherit;padding:0 3px;border-radius:3px;text-decoration:line-through;}
.dq{background:rgba(245,158,11,.13);border:1px solid rgba(245,158,11,.45);
  border-radius:8px;padding:8px 11px;font-size:.84rem;margin:2px 0 8px;}
.ovr{background:rgba(99,102,241,.18);border:1px solid rgba(99,102,241,.42);
  border-radius:6px;padding:2px 8px;font-size:.74rem;}
.legend{font-size:.74rem;opacity:.7;margin-top:5px;}
[data-testid="stProgress"] > div > div > div > div{background:var(--primary-color,#2f9e8f);}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


@st.cache_data(show_spinner=False)
def load_data():
    return tdata.load_facilities()


@st.cache_data(show_spinner="Assessing capabilities from the record…")
def assess_facility(facility_id: str, provider_salt: str):
    df = load_data()
    match = df[df["facility_id"].astype(str) == str(facility_id)]
    if match.empty:
        return None, None
    row = match.iloc[0].to_dict()
    return judge.assess_all(row), row


def highlight(text: str, spans) -> str:
    spans = sorted([s for s in spans], key=lambda x: x.start)
    out, lastend = [], 0
    for s in spans:
        start = max(s.start, lastend)
        if start >= s.end:
            continue
        out.append(html.escape(text[lastend:start]))
        cls = "neg" if s.negated else ("pos" if s.kind == "positive" else "ind")
        out.append(f'<mark class="{cls}">{html.escape(text[start:s.end])}</mark>')
        lastend = s.end
    out.append(html.escape(text[lastend:]))
    return "".join(out)


def _present(v):
    return v is not None and str(v).strip().lower() not in ("", "nan", "none")


def _facility_label(r):
    loc = ", ".join(str(v) for v in (getattr(r, "city", None), getattr(r, "state", None)) if _present(v))
    return f"{r.name} — {loc}" if loc else str(r.name)


store.init_db()
df = load_data()
provider_salt = os.environ.get("MODEL_PROVIDER", "auto") + "|" + os.environ.get("DATABRICKS_MODEL_ENDPOINT", "")

# ---------------- Sidebar: select a facility ----------------
st.sidebar.title("🏥 Facility Trust Desk")
st.sidebar.caption("Evidence-backed capability checks for health-facility planners.")
query = st.sidebar.text_input("Search facility / city / state", "")
view = df
if query:
    q = query.lower()
    mask = (df["name"].astype(str).str.lower().str.contains(q, na=False, regex=False)
            | df["city"].astype(str).str.lower().str.contains(q, na=False, regex=False)
            | df["state"].astype(str).str.lower().str.contains(q, na=False, regex=False))
    view = df[mask]
if view.empty:
    st.sidebar.warning("No matches; showing all.")
    view = df

labels = {str(r.facility_id): _facility_label(r) for r in view.itertuples()}
options = list(labels)
if not options:
    st.error("No facilities are loaded. Check the data source.")
    st.stop()
_qp_fid = st.query_params.get("facility")
_index = options.index(_qp_fid) if _qp_fid in options else 0
fid = st.sidebar.selectbox("Facility", options, index=_index, format_func=lambda x: labels[x])
st.query_params["facility"] = fid
st.sidebar.markdown("---")
st.sidebar.caption(f"Data source: **{df.attrs.get('source','?')}**  ·  {len(df)} facilities")
st.sidebar.caption("Engine order: Databricks FM → OpenAI → Anthropic → offline rules")

# ---------------- Main ----------------
assessments, row = assess_facility(fid, provider_salt)
if row is None:
    st.warning("That facility isn't in the current data. Pick one from the sidebar.")
    st.stop()
if not assessments:
    st.error("No assessments available.")
    st.stop()

st.markdown(f"### {row['name']}")


def _has(v):
    return v is not None and str(v).strip().lower() not in ("", "nan", "none")


def _num(v, suffix):
    try:
        return f"{int(float(v))}{suffix}"
    except (TypeError, ValueError):
        return None


_loc = ", ".join(str(row[k]) for k in ("city", "state") if _has(row.get(k)))
if _has(row.get("postcode")):
    _loc = f"{_loc} {str(row['postcode']).split('.')[0]}".strip()
_meta_parts = [p for p in [
    _loc or None,
    _num(row.get("capacity"), " beds") if _has(row.get("capacity")) else None,
    _num(row.get("numberDoctors"), " doctors") if _has(row.get("numberDoctors")) else None,
    (f"est. {str(row['yearEstablished']).split('.')[0]}" if _has(row.get("yearEstablished")) else None),
] if p]
st.caption(" · ".join(_meta_parts))

# trust summary
counts = {}
for a in assessments.values():
    counts[a.verdict] = counts.get(a.verdict, 0) + 1
summary = "  ".join(f"<span class='chip' style='background:{judge.VERDICT_META[v][2]}'>{n} {v}</span>"
                    for v, n in counts.items())
st.markdown(summary, unsafe_allow_html=True)

dq = assessments[next(iter(assessments))].data_quality
if dq:
    dq_text = " ".join(html.escape(str(item)) for item in dq)
    st.markdown("<div class='dq'>⚠ Data quality: " + dq_text + "</div>", unsafe_allow_html=True)

st.markdown("")
cols = st.columns(2)
for i, (cap_key, a) in enumerate(assessments.items()):
    col = cols[i % 2]
    override = store.get_override(fid, cap_key)
    with col:
        ovr_html = f"<span class='ovr'>overridden → {html.escape(str(override))}</span>" if override else ""
        st.markdown(
            f"<div class='cap-card' style='--c:{a.color}'>"
            f"<div class='cap-head'><span class='cap-title'>{CAPABILITIES[cap_key]['label']}</span>"
            f"<span class='chip' style='background:{a.color}'>{a.verdict}</span></div>"
            f"<div class='prov'>{a.label_name} · assessed by {html.escape(a.provider)} {ovr_html}</div>"
            f"<div class='rationale'>{html.escape(a.rationale)}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )
        st.progress(a.confidence, text=f"confidence {a.confidence:.0%}")

        with st.expander("Evidence & citations"):
            if not a.citations:
                st.markdown("_No supporting or contradicting text found in this record._")
            else:
                by_field = {}
                for s in a.citations:
                    by_field.setdefault(s.field, []).append(s)
                for f in TEXT_FIELDS:
                    if f in by_field:
                        st.markdown(
                            f"<div class='ev'><span class='lbl'>{FIELD_LABELS[f]}:</span> "
                            + highlight(str(row.get(f) or ""), by_field[f]) + "</div>",
                            unsafe_allow_html=True,
                        )
                st.caption("🟩 supports · 🟥 contradicts/negated · 🟨 indirect")

        with st.expander("Add note / override (saved)"):
            with st.form(f"form-{cap_key}", clear_on_submit=True):
                new_override = st.selectbox(
                    "Override verdict", ["— keep model verdict —", "Supported", "Unsupported",
                                          "Conflicting", "Not stated"], key=f"ov-{cap_key}")
                note = st.text_input("Note for the next planner", key=f"nt-{cap_key}")
                if st.form_submit_button("Save"):
                    if new_override != "— keep model verdict —":
                        store.add_action(fid, cap_key, "override", verdict_override=new_override, note=note or None)
                    elif note:
                        store.add_action(fid, cap_key, "note", note=note)
                    st.toast("Saved.")
                    st.rerun()

# ---------------- Persisted actions ----------------
actions = store.get_actions(fid)
if actions:
    st.markdown("#### 📝 Saved actions for this facility (persisted)")
    st.dataframe(
        pd.DataFrame(actions)[["created_at", "capability", "action_type", "verdict_override", "note", "author"]],
        hide_index=True, use_container_width=True,
    )

st.markdown("---")
st.caption("Every important claim is cited to the facility's own text; verdicts never exceed the evidence. "
           "Swap the demo data for the real Databricks table via FACILITIES_TABLE / FACILITIES_CSV.")
