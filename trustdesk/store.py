"""Persistence for planner actions (notes + verdict overrides).

Backend is chosen at runtime:
  * **Lakebase / Postgres** when Lakebase env is present (LAKEBASE_HOST or PGHOST
    or LAKEBASE_DSN) — this is the hackathon-compliant persistence layer.
  * **SQLite** otherwise, so local dev and the demo work with zero setup.

The public surface (init_db / add_action / get_actions / get_override) is identical
for both. On a deployed Databricks App, set the Lakebase env (see README) and notes
+ overrides persist in managed Postgres.
"""
import os
import logging
import datetime

log = logging.getLogger("trustdesk.store")

VALID_ACTIONS = {"note", "override"}
VALID_OVERRIDES = {"Supported", "Likely", "Conflicting", "Unsupported", "Weak", "Not stated"}

_SQLITE_PATH = os.environ.get(
    "TRUSTDESK_DB",
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "trustdesk_actions.db"),
)


def _use_postgres() -> bool:
    return bool(os.environ.get("LAKEBASE_DSN") or os.environ.get("LAKEBASE_HOST") or os.environ.get("PGHOST"))


def _lakebase_token(user):
    """Best-effort: mint a short-lived Lakebase credential via the Databricks SDK."""
    instance = os.environ.get("DATABRICKS_DATABASE_INSTANCE")
    if not instance:
        return None
    try:
        from databricks.sdk import WorkspaceClient
        w = WorkspaceClient()
        cred = w.database.generate_database_credential(
            request_id=os.urandom(8).hex(), instance_names=[instance]
        )
        return cred.token
    except Exception as e:  # noqa: BLE001
        log.warning("Could not mint Lakebase credential: %s", e)
        return None


def _pg_params():
    """Return a full DSN string (if LAKEBASE_DSN given) or a dict of connection
    keyword args. Passing kwargs to psycopg.connect lets libpq handle escaping, so
    passwords/hosts with spaces or special characters are safe."""
    dsn = os.environ.get("LAKEBASE_DSN")
    if dsn:
        return dsn
    user = os.environ.get("LAKEBASE_USER") or os.environ.get("PGUSER", "")
    return {
        "host": os.environ.get("LAKEBASE_HOST") or os.environ.get("PGHOST"),
        "port": os.environ.get("LAKEBASE_PORT") or os.environ.get("PGPORT", "5432"),
        "dbname": os.environ.get("LAKEBASE_DATABASE") or os.environ.get("PGDATABASE", "databricks_postgres"),
        "user": user,
        "password": os.environ.get("LAKEBASE_PASSWORD") or os.environ.get("PGPASSWORD") or _lakebase_token(user) or "",
        "sslmode": os.environ.get("PGSSLMODE", "require"),
    }


class _DB:
    def __init__(self):
        self.pg = _use_postgres()
        self.ph = "%s" if self.pg else "?"

    def connect(self):
        if self.pg:
            import psycopg  # lazy: only needed when Lakebase is configured
            params = _pg_params()
            if isinstance(params, str):
                return psycopg.connect(params)
            return psycopg.connect(**params)
        import sqlite3
        parent = os.path.dirname(_SQLITE_PATH)
        if parent and not os.path.isdir(parent):
            os.makedirs(parent, exist_ok=True)
        conn = sqlite3.connect(_SQLITE_PATH)
        conn.row_factory = sqlite3.Row
        return conn


def init_db():
    db = _DB()
    if db.pg:
        ddl = (
            "CREATE TABLE IF NOT EXISTS actions("
            " id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,"
            " facility_id TEXT NOT NULL, capability TEXT NOT NULL,"
            " action_type TEXT NOT NULL, verdict_override TEXT, note TEXT,"
            " author TEXT, created_at TIMESTAMPTZ NOT NULL DEFAULT now())"
        )
    else:
        ddl = (
            "CREATE TABLE IF NOT EXISTS actions("
            " id INTEGER PRIMARY KEY AUTOINCREMENT,"
            " facility_id TEXT NOT NULL, capability TEXT NOT NULL,"
            " action_type TEXT NOT NULL, verdict_override TEXT, note TEXT,"
            " author TEXT, created_at TEXT NOT NULL)"
        )
    with db.connect() as conn:
        cur = conn.cursor()
        cur.execute(ddl)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_actions_fac_cap ON actions(facility_id, capability)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_actions_fac ON actions(facility_id)")
        conn.commit()


def add_action(facility_id, capability, action_type, verdict_override=None, note=None, author="planner"):
    if action_type not in VALID_ACTIONS:
        raise ValueError(f"invalid action_type {action_type!r}; expected one of {sorted(VALID_ACTIONS)}")
    if verdict_override is not None and verdict_override not in VALID_OVERRIDES:
        raise ValueError(f"invalid verdict_override {verdict_override!r}")
    db = _DB()
    ph = db.ph
    with db.connect() as conn:
        cur = conn.cursor()
        if db.pg:
            cur.execute(
                f"INSERT INTO actions(facility_id, capability, action_type, verdict_override, note, author)"
                f" VALUES({ph},{ph},{ph},{ph},{ph},{ph})",
                (str(facility_id), capability, action_type, verdict_override, note, author),
            )
        else:
            cur.execute(
                f"INSERT INTO actions(facility_id, capability, action_type, verdict_override, note, author, created_at)"
                f" VALUES({ph},{ph},{ph},{ph},{ph},{ph},{ph})",
                (str(facility_id), capability, action_type, verdict_override, note, author,
                 datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")),
            )
        conn.commit()


_COLS = ["facility_id", "capability", "action_type", "verdict_override", "note", "author", "created_at"]


def get_actions(facility_id):
    db = _DB()
    ph = db.ph
    q = f"SELECT {', '.join(_COLS)} FROM actions WHERE facility_id={ph} ORDER BY created_at DESC"
    with db.connect() as conn:
        if db.pg:
            from psycopg.rows import dict_row
            cur = conn.cursor(row_factory=dict_row)
            cur.execute(q, (str(facility_id),))
            return list(cur.fetchall())
        cur = conn.cursor()
        cur.execute(q, (str(facility_id),))
        return [dict(zip(_COLS, row)) for row in cur.fetchall()]


def get_override(facility_id, capability):
    db = _DB()
    ph = db.ph
    q = (
        f"SELECT verdict_override FROM actions WHERE facility_id={ph} AND capability={ph}"
        f" AND action_type='override' AND verdict_override IS NOT NULL ORDER BY created_at DESC LIMIT 1"
    )
    with db.connect() as conn:
        cur = conn.cursor()
        cur.execute(q, (str(facility_id), capability))
        row = cur.fetchone()
        return row[0] if row else None
