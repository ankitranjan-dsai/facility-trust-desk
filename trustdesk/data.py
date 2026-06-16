"""Facility data loading with a pluggable source.

Resolution order:
  1. FACILITIES_TABLE  -> read a Unity Catalog table via databricks-sql-connector
                          (needs DATABRICKS_SERVER_HOSTNAME, DATABRICKS_HTTP_PATH,
                           DATABRICKS_TOKEN). Easiest on a deployed Databricks App.
  2. FACILITIES_CSV    -> read a local/volume CSV (great for the real 10k export).
  3. built-in sample   -> messy demo records so the app always runs.

Real columns are mapped to our canonical schema with COLUMN_MAP (JSON env), e.g.
  COLUMN_MAP='{"facility_name":"name","services":"services_text","dist":"district"}'
Canonical columns: facility_id, name, facility_type, ownership, state, district,
beds_total, latitude, longitude, services_text, infrastructure_text, notes_text.
"""
import os
import re
import json
import logging
import pandas as pd

from .capabilities import TEXT_FIELDS
from . import sample_data

log = logging.getLogger("trustdesk.data")

CANONICAL = [
    "facility_id", "name", "state", "city", "postcode",
    "latitude", "longitude", "numberDoctors", "capacity", "yearEstablished",
] + TEXT_FIELDS

# Map real dataset headers (any casing / spacing / camelCase) onto canonical names,
# so the app reads the provided `facilities` table without a manual COLUMN_MAP.
_ALIASES = {
    "name": ["name", "facilityname", "facility", "hospitalname"],
    "state": ["state"],
    "city": ["city", "town"],
    "postcode": ["postcode", "pincode", "pin", "zip", "zipcode", "postalcode"],
    "latitude": ["latitude", "lat"],
    "longitude": ["longitude", "lon", "lng", "long"],
    "numberDoctors": ["numberdoctors", "numdoctors", "doctors", "numberofdoctors"],
    "capacity": ["capacity", "beds", "bedcount", "numberofbeds", "bedcapacity"],
    "yearEstablished": ["yearestablished", "established", "yearfounded", "estyear"],
    "description": ["description", "desc", "about"],
    "capability": ["capability", "capabilities"],
    "procedure": ["procedure", "procedures"],
    "equipment": ["equipment", "equipments"],
    "specialties": ["specialties", "specialities", "controlledspecialties", "specialty", "speciality"],
    "source_urls": ["sourceurls", "sourceurl", "sources", "urls"],
}


def _norm(s) -> str:
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def _resolve_aliases(df: pd.DataFrame) -> pd.DataFrame:
    norm_to_col = {}
    for c in df.columns:
        norm_to_col.setdefault(_norm(c), c)
    rename = {}
    for canon, variants in _ALIASES.items():
        if canon in df.columns:
            continue
        for v in variants:
            col = norm_to_col.get(v)
            if col is not None and col not in rename:
                rename[col] = canon
                break
    return df.rename(columns=rename) if rename else df

# A safe (optionally) qualified identifier: catalog.schema.table — letters, digits,
# underscores only, 1–3 dot-separated parts. Guards against SQL injection via env.
_TABLE_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*){0,2}$")


def _valid_table_name(name: str) -> bool:
    return bool(name) and bool(_TABLE_RE.match(name))


def _apply_column_map(df: pd.DataFrame) -> pd.DataFrame:
    raw = os.environ.get("COLUMN_MAP")
    if raw:
        try:
            mapping = json.loads(raw)
            if not isinstance(mapping, dict):
                raise ValueError("COLUMN_MAP must be a JSON object")
            df = df.rename(columns=mapping)
        except Exception as e:  # noqa: BLE001
            log.warning("Ignoring malformed COLUMN_MAP (%s): %s", e, raw)
    return df


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    df = _apply_column_map(df)        # explicit overrides win
    df = _resolve_aliases(df)         # then auto-map real headers to canonical
    if "facility_id" not in df.columns:
        df = df.reset_index(drop=True)
        df["facility_id"] = df.index.map(lambda i: f"ROW-{i:05d}")
    if "name" not in df.columns:
        df["name"] = df["facility_id"].astype(str)
    for col in CANONICAL:
        if col not in df.columns:
            df[col] = "" if col in TEXT_FIELDS else None
    for f in TEXT_FIELDS:
        df[f] = df[f].fillna("").astype(str)
    return df


def _read_databricks_table(table: str) -> pd.DataFrame:
    if not _valid_table_name(table):
        raise ValueError(f"unsafe FACILITIES_TABLE identifier: {table!r}")
    from databricks import sql  # databricks-sql-connector
    host = os.environ["DATABRICKS_SERVER_HOSTNAME"]
    http_path = os.environ["DATABRICKS_HTTP_PATH"]
    # use_cloud_fetch=False: return results inline via the warehouse instead of a
    # direct cloud-storage download, which the Databricks Apps sandbox blocks.
    kwargs = {"server_hostname": host, "http_path": http_path, "use_cloud_fetch": False}

    token = os.environ.get("DATABRICKS_TOKEN")
    if token:
        kwargs["access_token"] = token
    else:
        # On Databricks Apps the runtime injects the app's service-principal OAuth
        # credentials — use them so no PAT is needed.
        client_id = os.environ.get("DATABRICKS_CLIENT_ID")
        client_secret = os.environ.get("DATABRICKS_CLIENT_SECRET")
        if not (client_id and client_secret):
            raise ValueError("No DATABRICKS_TOKEN and no OAuth client credentials available")
        from databricks.sdk.core import Config, oauth_service_principal
        cfg = Config(host=f"https://{host}", client_id=client_id, client_secret=client_secret)
        kwargs["credentials_provider"] = lambda: oauth_service_principal(cfg)

    limit = int(os.environ.get("FACILITIES_LIMIT", "10000"))
    with sql.connect(**kwargs) as conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT * FROM {table} LIMIT {limit}")
            cols = [d[0] for d in cur.description]
            return pd.DataFrame(cur.fetchall(), columns=cols)


def load_facilities() -> pd.DataFrame:
    table = os.environ.get("FACILITIES_TABLE")
    csv = os.environ.get("FACILITIES_CSV")
    source = "built-in sample"
    df = None
    if table:
        if not _valid_table_name(table):
            log.warning("Ignoring unsafe FACILITIES_TABLE %r; falling back.", table)
        else:
            try:
                df = _read_databricks_table(table)
                source = f"Databricks table: {table}"
            except Exception as e:  # noqa: BLE001
                log.warning("Could not read table %s: %s; falling back.", table, e)
    if df is None and csv:
        if not os.path.exists(csv):
            log.warning("FACILITIES_CSV not found: %s; falling back.", csv)
        else:
            try:
                df = pd.read_csv(csv)
                source = f"CSV: {csv}"
            except Exception as e:  # noqa: BLE001
                log.warning("Could not read CSV %s: %s; falling back.", csv, e)
    if df is None or df.empty:
        df = sample_data.load_sample()
        source = "built-in sample"
    df = _normalize(df)
    df.attrs["source"] = source
    return df
