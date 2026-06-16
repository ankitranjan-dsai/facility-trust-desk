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
    "facility_id", "name", "facility_type", "ownership", "state", "district",
    "beds_total", "latitude", "longitude",
] + TEXT_FIELDS

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
    df = _apply_column_map(df)
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
    token = os.environ.get("DATABRICKS_TOKEN")
    if not token:
        raise ValueError("DATABRICKS_TOKEN is required to read FACILITIES_TABLE")
    from databricks import sql  # databricks-sql-connector
    with sql.connect(
        server_hostname=os.environ["DATABRICKS_SERVER_HOSTNAME"],
        http_path=os.environ["DATABRICKS_HTTP_PATH"],
        access_token=token,
    ) as conn:
        with conn.cursor() as cur:
            limit = os.environ.get("FACILITIES_LIMIT", "10000")
            cur.execute(f"SELECT * FROM {table} LIMIT {int(limit)}")
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
