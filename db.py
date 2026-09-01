import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime

DB_PATH = "users.db"


@contextmanager
def get_conn():
    """
    Create a SQLite database connection.
    Automatically closes the connection after use.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")

    try:
        yield conn
    finally:
        conn.close()


def init_db():
    """
    Create all required tables if they don't already exist,
    then run database migrations for older database versions.
    """

    with get_conn() as conn:
        c = conn.cursor()

        # ---------------------------------------------------------
        # WATCHLIST
        # ---------------------------------------------------------
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS watchlist_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                ticker TEXT NOT NULL,
                position INTEGER NOT NULL DEFAULT 0,
                added_at TEXT NOT NULL,
                UNIQUE(username, ticker)
            )
            """
        )

        # ---------------------------------------------------------
        # HOLDINGS
        # ---------------------------------------------------------
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS holdings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                ticker TEXT NOT NULL,
                shares REAL NOT NULL,
                cost_basis REAL,
                added_at TEXT NOT NULL
            )
            """
        )

        # ---------------------------------------------------------
        # ANALYSIS HISTORY
        # ---------------------------------------------------------
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS analysis_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                ticker TEXT NOT NULL,
                risk_tolerance TEXT NOT NULL,
                action TEXT NOT NULL,
                kind TEXT,
                confidence REAL,
                rationale TEXT,
                attributions TEXT,
                degraded INTEGER NOT NULL DEFAULT 0,
                latency REAL DEFAULT 0,
                run_at TEXT NOT NULL
            )
            """
        )

        conn.commit()

    # Run migrations AFTER all tables have been created.
    migrate_database()


def migrate_database():
    """
    Upgrade an existing database created with an older version
    of the application.

    In particular, this adds the latency column to old
    analysis_history tables.
    """

    with get_conn() as conn:

        # Check whether analysis_history exists.
        table_exists = conn.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type='table' AND name='analysis_history'
            """
        ).fetchone()

        if not table_exists:
            return

        # Get existing columns.
        columns = [
            row["name"]
            for row in conn.execute(
                "PRAGMA table_info(analysis_history)"
            ).fetchall()
        ]

        # ---------------------------------------------------------
        # Add latency column if it doesn't exist.
        # ---------------------------------------------------------
        if "latency" not in columns:
            conn.execute(
                """
                ALTER TABLE analysis_history
                ADD COLUMN latency REAL DEFAULT 0
                """
            )

        conn.commit()


def get_watchlist(username):
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT ticker
            FROM watchlist_items
            WHERE username=?
            ORDER BY position, id
            """,
            (username,),
        ).fetchall()

        return [r["ticker"] for r in rows]


def set_watchlist(username, tickers):
    now = datetime.now().isoformat()

    with get_conn() as conn:
        c = conn.cursor()

        try:
            c.execute(
                "DELETE FROM watchlist_items WHERE username=?",
                (username,),
            )

            for i, ticker in enumerate(tickers):
                c.execute(
                    """
                    INSERT INTO watchlist_items
                    (username, ticker, position, added_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (username, ticker, i, now),
                )

            conn.commit()

        except Exception:
            conn.rollback()
            raise


def get_holdings(username):
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT id, ticker, shares, cost_basis, added_at
            FROM holdings
            WHERE username=?
            ORDER BY added_at
            """,
            (username,),
        ).fetchall()

        return [dict(r) for r in rows]


def add_holding(username, ticker, shares, cost_basis=None):
    now = datetime.now().isoformat()

    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO holdings
            (username, ticker, shares, cost_basis, added_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                username,
                ticker,
                shares,
                cost_basis,
                now,
            ),
        )

        conn.commit()


def delete_holding(username, holding_id):
    with get_conn() as conn:
        conn.execute(
            """
            DELETE FROM holdings
            WHERE id=? AND username=?
            """,
            (holding_id, username),
        )

        conn.commit()


def add_analysis_record(
    username,
    ticker,
    risk_tolerance,
    synth,
    total_time,
):
    """
    Save an analysis result to analysis_history.

    total_time is stored in the latency column.
    """

    now = datetime.now().isoformat()

    # Make sure total_time is always a valid numeric value.
    try:
        latency = float(total_time)
    except (TypeError, ValueError):
        latency = 0.0

    # Prevent None / invalid synthesis data from crashing the DB insert.
    if not isinstance(synth, dict):
        synth = {}

    action = synth.get("action", "UNKNOWN")
    kind = synth.get("kind")
    confidence = synth.get("confidence")
    rationale = synth.get("rationale")

    attributions = synth.get("attributions", [])

    if not isinstance(attributions, list):
        attributions = []

    degraded = 1 if synth.get("degraded_inputs") else 0

    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO analysis_history
            (
                username,
                ticker,
                risk_tolerance,
                action,
                kind,
                confidence,
                rationale,
                attributions,
                degraded,
                latency,
                run_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                username,
                ticker,
                risk_tolerance,
                action,
                kind,
                confidence,
                rationale,
                json.dumps(attributions),
                degraded,
                latency,
                now,
            ),
        )

        conn.commit()


def get_history(username, ticker=None, limit=50):
    """
    Retrieve analysis history for a user.

    If ticker is supplied, only that ticker's history is returned.
    """

    with get_conn() as conn:

        if ticker:
            rows = conn.execute(
                """
                SELECT *
                FROM analysis_history
                WHERE username=? AND ticker=?
                ORDER BY run_at DESC
                LIMIT ?
                """,
                (
                    username,
                    ticker,
                    limit,
                ),
            ).fetchall()

        else:
            rows = conn.execute(
                """
                SELECT *
                FROM analysis_history
                WHERE username=?
                ORDER BY run_at DESC
                LIMIT ?
                """,
                (
                    username,
                    limit,
                ),
            ).fetchall()

        out = []

        for r in rows:
            d = dict(r)

            # Safely decode attributions.
            if d.get("attributions"):
                try:
                    d["attributions"] = json.loads(d["attributions"])
                except (json.JSONDecodeError, TypeError):
                    d["attributions"] = []
            else:
                d["attributions"] = []

            # Ensure latency always exists for older records.
            if d.get("latency") is None:
                d["latency"] = 0.0

            # Ensure confidence is numeric when possible.
            if d.get("confidence") is not None:
                try:
                    d["confidence"] = float(d["confidence"])
                except (TypeError, ValueError):
                    d["confidence"] = 0.0

            out.append(d)

        return out


# -----------------------------------------------------------------
# INITIALIZE DATABASE
# -----------------------------------------------------------------
# This automatically creates tables and applies migrations when
# db.py is imported.
init_db()