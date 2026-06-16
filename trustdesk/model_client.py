"""LLM judge with a graceful fallback chain.

Provider order (first that is configured + reachable wins):
  1. Databricks Foundation Model serving endpoint  (preferred — scores on
     "Databricks capability usage")
  2. OpenAI            (OPENAI_API_KEY)
  3. Anthropic         (ANTHROPIC_API_KEY)
  4. None              -> caller falls back to the deterministic rule engine

Set MODEL_PROVIDER=databricks|openai|anthropic|offline to pin one explicitly.
All imports are lazy so the app runs with only streamlit + pandas installed.
"""
import os
import re
import json

_SYSTEM = (
    "You are a careful health-facility data auditor. You judge whether a facility "
    "can deliver a specific capability using ONLY the provided source text. You never "
    "use outside knowledge, you respect negation (no / out of order / referred elsewhere), "
    "and you only quote text that appears verbatim in the source."
)


def _build_prompt(source_text: str, capability_label: str) -> str:
    return f"""CAPABILITY TO VERIFY: {capability_label}

SOURCE TEXT (the only evidence you may use):
\"\"\"
{source_text}
\"\"\"

Rules:
- Use ONLY the source text. No outside knowledge or assumptions.
- Every string in "quotes" MUST be copied verbatim (an exact substring) from the source.
- "Unsupported" if the text says the capability is absent, broken, or referred elsewhere.
- "Not stated" (with quotes: []) if there is no relevant mention at all.
- Be honest about uncertainty; do not upgrade weak signals.

Return ONLY a JSON object:
{{"verdict": one of ["Supported","Likely","Conflicting","Unsupported","Weak","Not stated"],
 "confidence": number between 0 and 1,
 "rationale": one plain-English sentence a non-technical planner can act on,
 "quotes": [verbatim substrings from the source text that justify the verdict]}}"""


def _safe_json(raw: str):
    if not raw:
        return None
    raw = raw.strip()
    raw = re.sub(r"^```(json)?", "", raw).strip().rstrip("`").strip()
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


def _try_databricks(prompt: str):
    endpoint = os.environ.get("DATABRICKS_MODEL_ENDPOINT", "databricks-meta-llama-3-3-70b-instruct")
    try:
        from databricks.sdk import WorkspaceClient
        from databricks.sdk.service.serving import ChatMessage, ChatMessageRole
        w = WorkspaceClient()
        resp = w.serving_endpoints.query(
            name=endpoint,
            messages=[
                ChatMessage(role=ChatMessageRole.SYSTEM, content=_SYSTEM),
                ChatMessage(role=ChatMessageRole.USER, content=prompt),
            ],
            temperature=0.0,
            max_tokens=600,
        )
        return resp.choices[0].message.content, f"databricks:{endpoint}"
    except Exception:
        return None


def _try_openai(prompt: str):
    if not os.environ.get("OPENAI_API_KEY"):
        return None
    try:
        from openai import OpenAI
        model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        client = OpenAI()
        r = client.chat.completions.create(
            model=model, temperature=0, max_tokens=600,
            messages=[{"role": "system", "content": _SYSTEM},
                      {"role": "user", "content": prompt}],
        )
        return r.choices[0].message.content, f"openai:{model}"
    except Exception:
        return None


def _try_anthropic(prompt: str):
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    try:
        import anthropic
        model = os.environ.get("ANTHROPIC_MODEL", "claude-3-5-haiku-latest")
        client = anthropic.Anthropic()
        r = client.messages.create(
            model=model, max_tokens=600, temperature=0, system=_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        return r.content[0].text, f"anthropic:{model}"
    except Exception:
        return None


_PROVIDERS = {
    "databricks": _try_databricks,
    "openai": _try_openai,
    "anthropic": _try_anthropic,
}


def _provider_order():
    pin = os.environ.get("MODEL_PROVIDER", "").strip().lower()
    if pin == "offline":
        return []
    if pin in _PROVIDERS:
        return [_PROVIDERS[pin]]
    return [_try_databricks, _try_openai, _try_anthropic]


def _valid_judgement(data) -> bool:
    """A usable model response must carry a verdict, a numeric confidence, and a rationale."""
    if not isinstance(data, dict):
        return False
    if not isinstance(data.get("verdict"), str) or not data["verdict"].strip():
        return False
    if not isinstance(data.get("rationale"), str) or not data["rationale"].strip():
        return False
    try:
        float(data.get("confidence"))
    except (TypeError, ValueError):
        return False
    return True


def judge_with_llm(source_text: str, capability_label: str):
    """Return {verdict, confidence, rationale, quotes, provider} or None."""
    prompt = _build_prompt(source_text, capability_label)
    for fn in _provider_order():
        out = fn(prompt)
        if not out:
            continue
        raw, provider = out
        data = _safe_json(raw)
        if not _valid_judgement(data):
            continue
        # Anti-hallucination guard: keep only quotes that are verbatim substrings.
        raw_quotes = data.get("quotes")
        if not isinstance(raw_quotes, list):
            raw_quotes = []
        data["quotes"] = [q for q in raw_quotes if isinstance(q, str) and q and q in source_text]
        data["provider"] = provider
        return data
    return None
