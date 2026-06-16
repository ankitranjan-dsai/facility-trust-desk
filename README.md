# Facility Trust Desk

**Databricks "Apps & Agents for Good" Hackathon 2026 — Track: Facility Trust Desk.**

Turns messy Indian health-facility records into **trustworthy, cited capability
verdicts** for non-technical planners. For any facility it answers: *can this
place actually deliver ICU / maternity / emergency / surgery / blood bank /
diagnostics?* — and shows the **exact source text** behind every answer, communicates
**uncertainty honestly**, and lets a planner **add notes or override** (persisted).

## Why it's trustworthy (the core idea)
A **retrieve-then-judge** pipeline:
1. A deterministic extractor finds **verbatim evidence spans** in the record and flags
   **negation** ("ventilator *out of order*", "*no* ICU, *refer*"). Citations are real
   substrings of the source, so they cannot be hallucinated.
2. An LLM judge (Databricks Foundation Model API) refines the verdict using **only**
   that source text; any quote it returns is verified to be a verbatim substring.
3. A hard guard: a **Supported/Likely verdict requires a real citation**, else it's
   auto-downgraded. Verdicts: Supported · Likely · Conflicting · Unsupported · Weak ·
   Not stated — each with a confidence and data-quality caveats.

Model fallback chain (resilient demo): **Databricks FM → OpenAI → Anthropic → offline rules.**
The offline rule engine alone still produces real citations + honest uncertainty.

## Run locally (sample data)
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install streamlit pandas
streamlit run app.py
```
Opens with 12 deliberately-messy demo facilities (negation, broken equipment,
partial capability, inconsistent casing, sparse records).

## Deploy as a Databricks App (Free Edition)
1. Push this repo to your Databricks workspace (Apps → create → from repo) — `app.yaml` is the entrypoint.
2. Set the model endpoint in `app.yaml` (`DATABRICKS_MODEL_ENDPOINT`) to a Foundation Model serving endpoint you have access to.
3. Point at the provided dataset (one of):
   - `FACILITIES_TABLE=catalog.schema.table` (read via SQL warehouse — set `DATABRICKS_SERVER_HOSTNAME`, `DATABRICKS_HTTP_PATH`, `DATABRICKS_TOKEN`), or
   - `FACILITIES_CSV=/Volumes/.../facilities.csv`.
4. Map real columns to the canonical schema with `COLUMN_MAP` (JSON), e.g.
   `COLUMN_MAP='{"facility_name":"name","services":"services_text","dist":"district"}'`.
   Canonical text fields scanned for evidence: `services_text`, `infrastructure_text`, `notes_text`.

## Persistence (Lakebase)
Planner notes + verdict overrides persist via `trustdesk/store.py`, which picks its
backend at runtime:
- **Lakebase / Postgres** when Lakebase env is set — the hackathon-compliant store.
- **SQLite** otherwise (local dev / demo, zero setup).

To use Lakebase on the deployed app, set (in `app.yaml` or app env):
```
LAKEBASE_HOST=<your-lakebase-host>
LAKEBASE_DATABASE=databricks_postgres
LAKEBASE_USER=<service-principal-or-user>
# Either provide LAKEBASE_PASSWORD, or set DATABRICKS_DATABASE_INSTANCE to mint a
# short-lived credential automatically via the Databricks SDK.
DATABRICKS_DATABASE_INSTANCE=<lakebase-instance-name>
```
The table + indexes are created on first run. The `add_action / get_actions /
get_override` surface is identical across both backends.

> **Databricks-tool coverage:** Foundation Model serving (the LLM judge) + Lakebase
> (persistence) satisfy the "Databricks App on Lakebase plus another Databricks tool" rule.

## License
MIT — see [LICENSE](LICENSE).

## Layout
```
app.py                 Streamlit UI (cards, highlighted citations, notes/overrides)
trustdesk/capabilities.py  capability lexicons + negation cues
trustdesk/evidence.py      deterministic span extractor + scoring
trustdesk/model_client.py  LLM judge with provider fallback chain
trustdesk/judge.py         merge + trust guards (citation-required verdicts)
trustdesk/data.py          data loader (Databricks table / CSV / sample) + column map
trustdesk/store.py         persistence (notes + overrides)
trustdesk/sample_data.py   messy demo facilities
```

## 3-minute demo script (draft)
- **User & problem (30s):** a district planner must decide where to refer an emergency; the registry text is messy and over-claims.
- **Workflow (90s):** pick *CHC Sinnar* → ICU shows **Conflicting** ("under construction", "ventilator *out of order*" highlighted red); Blood Bank shows **Weak** ("blood storage unit, *not* a full blood bank"); Emergency **Supported** ("Casualty 24x7" highlighted green). Confidence + "assessed by" shown. Add a note + override → it persists.
- **Technical & tradeoffs (45s):** retrieve-then-judge so citations can't be hallucinated; citation-required verdicts; Databricks FM with offline fallback; one config swap to the real 10k table.
- **Ambition (15s):** scales to all four tracks from the same evidence layer.
