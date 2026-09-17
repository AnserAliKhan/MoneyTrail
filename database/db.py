
# Database layer for Spendly.
#
# Exposes three helpers used by app.py on startup and by route handlers
# (in later steps) at request time:
#   get_db()   — returns a SQLite connection bound to the current request,
#                with row_factory and foreign-key enforcement enabled.
#   init_db()  — creates the users and expenses tables if they don't exist,
#                and wires the per-request teardown so connections close cleanly.
#   seed_db()  — idempotently inserts one demo user and 8 sample expenses
#                so a fresh checkout has something to show.
#
# All SQL is parameterized (?, never f-strings) and the categories for
# expenses are a fixed TEXT list — there is no categories table.

import os
import sqlite3

from flask import g
from werkzeug.security import generate_password_hash


# --------------------------------------------------------------------- #
# Schema                                                                 #
# --------------------------------------------------------------------- #

# Kept as a module-level string rather than a separate .sql file so the
# module has no hidden file dependencies. Two tables, mirroring spec §4.
SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT    NOT NULL,
    email         TEXT    NOT NULL UNIQUE,
    password_hash TEXT    NOT NULL,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS expenses (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    amount      REAL    NOT NULL,
    category    TEXT    NOT NULL,
    date        TEXT    NOT NULL,                    -- YYYY-MM-DD
    description TEXT,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id)
);
"""


# Fixed list of valid expense categories (spec §10). Validated by
# application code in later steps, not by a CHECK constraint — the spec
# doesn't ask for one.
CATEGORIES = (
    "Food",
    "Transport",
    "Bills",
    "Health",
    "Entertainment",
    "Shopping",
    "Other",
)


# --------------------------------------------------------------------- #
# Connection management                                                  #
# --------------------------------------------------------------------- #

def _resolve_db_path(app) -> str:
    """Return the absolute path to the SQLite file.

    Resolved relative to the project root (this file's parent's parent),
    not CWD, so the DB lands in the same place no matter where the app
    is launched from.
    """
    configured = app.config.get("DATABASE")
    if configured:
        return os.path.abspath(configured)
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(project_root, "expense_tracker.db")


def get_db() -> sqlite3.Connection:
    """Return the SQLite connection for the current request/app context.

    Connections are cached on flask.g so a request that calls get_db()
    several times reuses one connection. The teardown registered in
    init_db() closes it when the app context tears down.
    """
    if "db" not in g:
        conn = sqlite3.connect(current_app_db_path())
        conn.row_factory = sqlite3.Row
        # FK enforcement is per-connection in SQLite; spec §11 requires
        # it set on every connection.
        conn.execute("PRAGMA foreign_keys = ON")
        g.db = conn
    return g.db


def current_app_db_path() -> str:
    """Read the DB path that init_db() stored on the app config."""
    from flask import current_app
    return current_app.config["DATABASE"]


def _close_db(_exc=None) -> None:
    """flask.teardown_appcontext callback — close the per-request connection."""
    db = g.pop("db", None)
    if db is not None:
        db.close()


# --------------------------------------------------------------------- #
# Schema initialization                                                  #
# --------------------------------------------------------------------- #

def init_db(app) -> None:
    """Create tables (if missing) and register the teardown callback.

    Called once from app.py inside app.app_context() at startup.
    Idempotent — CREATE TABLE IF NOT EXISTS makes repeated runs safe.
    """
    app.config["DATABASE"] = _resolve_db_path(app)
    app.teardown_appcontext(_close_db)

    conn = sqlite3.connect(app.config["DATABASE"])
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


# --------------------------------------------------------------------- #
# Demo data                                                              #
# --------------------------------------------------------------------- #

# 8 sample expenses covering all 7 categories (one category gets two).
# Dates spread across the current month (July 2026 per /currentDate).
# All linked to user_id = 1, the demo user inserted just below.
_DEMO_EXPENSES = [
    # (amount, category, date,        description)
    (   250.00, "Food",          "2026-07-01", "Chai and breakfast"),
    (   180.00, "Transport",     "2026-07-03", "Auto to office"),
    (  2200.00, "Bills",         "2026-07-06", "Electricity bill"),
    (   450.00, "Health",        "2026-07-09", "Pharmacy"),
    (   599.00, "Entertainment", "2026-07-12", "Movie ticket"),
    (  1499.00, "Shopping",      "2026-07-18", "T-shirt"),
    (   350.00, "Other",         "2026-07-22", "Household supplies"),
    (   120.00, "Other",         "2026-07-27", "Petty cash"),
]


def seed_db() -> None:
    """Insert the demo user + 8 expenses exactly once.

    Spec §5C: short-circuits if the users table already has data, so
    repeated startups never duplicate the demo row or its expenses.
    """
    db = get_db()
    if db.execute("SELECT COUNT(*) FROM users").fetchone()[0] > 0:
        return

    db.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        (
            "Demo User",
            "demo@spendly.com",
            generate_password_hash("demo123"),
        ),
    )
    db.executemany(
        """
        INSERT INTO expenses (user_id, amount, category, date, description)
        VALUES (?, ?, ?, ?, ?)
        """,
        [
            (1, amount, category, date, description)
            for (amount, category, date, description) in _DEMO_EXPENSES
        ],
    )
    db.commit()
