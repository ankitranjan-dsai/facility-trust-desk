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
.cap-card{border:1px solid #e5e7eb;border-left:6px solid var(--c,#6b7280);border-radius:10px;
  padding:14px 16px;margin-bottom:12px;background:#ffffff;}
.cap-head{display:flex;justify-content:space-between;align-items:center;gap:8px;}
.cap-title{font-weight:650;font-size:1.02rem;}
.chip{color:#fff;border-radius:999px;padding:2px 10px;font-size:.78rem;font-weight:600;white-space:nowrap;}
.prov{color:#6b7280;font-size:.74rem;margin-top:2px;}
.rationale{font-size:.9rem;color:#111827;margin-top:6px;}
.ev{font-family:ui-monospace,Menlo,monospace;font-size:.82rem;line-height:1.55;
  background:#f9fafb;border:1px solid #eef0f3;border-radius:8px;padding:8px 10px;margin:4px 0;white-space:pre-wrap;}
.ev .lbl{color:#6b7280;font-weight:700;}
mark.pos{background:#d7f0db;padding:0 2px;border-radius:3px;}
mark.ind{background:#fdf0c2;padding:0 2px;border-radius:3px;}
mark.neg{background:#fbd5d0;padding:0 2px;border-radius:3px;text-decoration:line-through;}
.dq{background:#fff7ed;border:1px solid #fed7aa;border-radius:8px;padding:6px 10px;font-size:.82rem;color:#7c2d12;}
.ovr{background:#eef2ff;border:1px solid #c7d2fe;border-radius:6px;padding:2px 8px;font-size:.76rem;color:#3730a3;}
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
        if s.start < lastend:
            continue
        out.append(html.escape(text[lastend:s.start]))
        cls = "neg" if s.negated else ("pos" if s.kind == "positive" else "ind")
        out.append(f'<mark class="{cls}">{html.escape(text[s.start:s.end])}</mark>')
        lastend = s.end
    out.append(html.escape(text[lastend:]))
    return "".join(out)


store.init_db()
df = load_data()
provider_salt = os.environ.get("MODEL_PROVIDER", "auto") + "|" + os.environ.get("DATABRICKS_MODEL_ENDPOINT", "")

# ---------------- Sidebar: select a facility ----------------
st.sidebar.title("🏥 Facility Trust Desk")
st.sidebar.caption("Evidence-backed capability checks for health-facility planners.")
query = st.sidebar.text_input("Search facility / district", "")
view = df
if query:
    q = query.lower()
    mask = df["name"].str.lower().str.contains(q) | df["district"].astype(str).str.lower().str.contains(q)
    view = df[mask]
if view.empty:
    st.sidebar.warning("No matches; showing all.")
    view = df

labels = {str(r.facility_id): f"{r.name} — {r.district}" for r in view.itertuples()}
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

st.markdown(f"### {row['name']}")
meta = " · ".join(str(x) for x in [row.get("facility_type"), row.get("ownership"),
                                   f"{row.get('district')}, {row.get('state')}",
                                   f"{row.get('beds_total') or '?'} beds"] if x)
st.caption(meta)

# trust summary
counts = {}
for a in assessments.values():
    counts[a.verdict] = counts.get(a.verdict, 0) + 1
summary = "  ".join(f"<span class='chip' style='background:{judge.VERDICT_META[v][2]}'>{n} {v}</span>"
                    for v, n in counts.items())
st.markdown(summary, unsafe_allow_html=True)

dq = assessments[next(iter(assessments))].data_quality
if dq:
    st.markdown("<div class='dq'>⚠ Data quality: " + " ".join(dq) + "</div>", unsafe_allow_html=True)

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
                    st.success("Saved.")
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
