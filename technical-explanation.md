# MoneyTrail — Technical Explanation

> A programmer-oriented walk-through of every file in the MoneyTrail
> codebase. This document is intended for engineers joining the project
> who need to come up to speed quickly on what each file does, the
> languages and algorithms in play, and the workflows that connect the
> pieces. Each section points to concrete code excerpts with
> `file_path:line_number` references so you can jump to the source.

---

## Table of Contents

1. [Project Layout (recap)](#1-project-layout-recap)
2. [Languages and Runtime Versions](#2-languages-and-runtime-versions)
3. [Application Entry Point: `app.py`](#3-application-entry-point-apppy)
4. [Database Layer: `database/db.py`](#4-database-layer-databasedbpy)
5. [Query Helpers: `database/queries.py`](#5-query-helpers-databasequeriespy)
6. [Seed Scripts](#6-seed-scripts)
7. [Template System](#7-template-system)
8. [Static Assets: CSS, JS, Images](#8-static-assets-css-js-images)
9. [Automated Tests](#9-automated-tests)
10. [Configuration and Tooling](#10-configuration-and-tooling)
11. [End-to-End Workflows](#11-end-to-end-workflows)

---

## 1. Project Layout (recap)

```
expense-tracker/
├── app.py                  # Flask app: routes + helpers
├── seed_user.py            # CLI: create one fake user
├── seed_expenses.py        # CLI: insert N fake expenses for a user
├── requirements.txt
├── .gitignore
├── CLAUDE.md               # Project notes for the AI assistant
├── explanation.md          # Non-technical walkthrough
├── technical-explanation.md# This document
│
├── database/
│   ├── __init__.py         # Empty package marker
│   ├── db.py               # Schema, connection, seed
│   └── queries.py          # Reusable CRUD helpers
│
├── templates/              # Jinja2 templates
│   ├── base.html
│   ├── landing.html
│   ├── login.html
│   ├── register.html
│   ├── profile.html
│   ├── dashboard.html
│   ├── analytics.html
│   ├── terms.html
│   ├── privacy.html
│   └── expenses/
│       ├── add.html
│       └── edit.html
│
├── static/
│   ├── css/style.css
│   ├── js/main.js
│   └── img/
│       ├── hero.svg
│       └── figma-reference.png
│
└── tests/
    ├── conftest.py
    ├── test_06-date-filter.py
    └── test_07_add_expense.py
```

---

## 2. Languages and Runtime Versions

| Item                  | Version / Detail                                          |
|-----------------------|-----------------------------------------------------------|
| Python                | 3.x (uses `from __future__`-style hints like `str | None`)|
| Web framework         | Flask 3.1.3                                               |
| Crypto / WSGI helpers | Werkzeug 3.1.6                                            |
| Tests                 | pytest 8.3.5 + pytest-flask 1.3.0                         |
| Templating            | Jinja2 (bundled with Flask)                               |
| Storage               | SQLite 3 (via Python's stdlib `sqlite3`)                 |
| Browser-side          | Hand-written ES5/ES6 in `landing.html` and `profile.html` |
| Browser libs          | Lucide icons, Chart.js (both via CDN)                     |

There is no build step. There is no transpiler. The "frontend" is
hand-written HTML, CSS, and small inline JavaScript.

---

## 3. Application Entry Point: `app.py`

`app.py` is the heart of the application. It contains:

- The `Flask` instance,
- A few module-level helpers (validators, decorators, date utilities),
- All route handlers,
- The `if __name__ == "__main__"` block that starts the dev server.

### 3.1 Imports and Flask setup (`app.py:1-21`)

```python
import os
import secrets
import sqlite3
import sys
from datetime import date, datetime, timedelta
from functools import wraps

from flask import Flask, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from database.db import CATEGORIES, get_db, init_db, seed_db
from database.queries import delete_expense as db_delete_expense,
                             get_expense_by_id, insert_expense, update_expense

app = Flask(__name__)
app.secret_key = "dev-secret-change-me"
```

**What's happening here**

- `os`, `secrets`, `sys` are stdlib — env vars, CSRF tokens, platform checks.
- `sqlite3` is the stdlib driver for SQLite. It's used in the
  registration route to catch `IntegrityError` for duplicate emails
  (`app.py:103`).
- `functools.wraps` is used by the two auth decorators so the
  underlying view function keeps its `__name__` (Flask's `url_for`
  needs that to resolve the endpoint).
- `check_password_hash` / `generate_password_hash` are from Werkzeug.
  They implement PBKDF2 by default; passwords are never stored as
  plaintext.
- The `db_delete_expense` import is **aliased** because we already
  have a local function `delete_expense` for the route — namespacing
  keeps them straight.
- `app.secret_key` is currently a hard-coded dev value. The comment
  above it (`app.py:16-19`) explicitly flags this as something to fix
  before production.

### 3.2 Database bootstrap (`app.py:27-32`)

```python
with app.app_context():
    init_db(app)
    seed_db()
```

This block runs once at import time (i.e. every time the dev server
starts). It is `idempotent`:

- `init_db` issues `CREATE TABLE IF NOT EXISTS`.
- `seed_db` short-circuits if the `users` table already has rows.

That double-safe behaviour is what makes the seed user (`demo@spendly.com`)
appear once and never get duplicated across restarts.

### 3.3 Validators and decorators (`app.py:39-76`)

```python
def _validate_registration(name: str, email: str, password: str) -> str | None:
    if not name:
        return "Please enter your name."
    if "@" not in email or "." not in email.split("@")[-1]:
        return "Please enter a valid email address."
    if len(password) < 8:
        return "Password must be at least 8 characters."
    return None
```

This is a classic **fail-fast validator**: it returns the first error
it finds, or `None` if everything is OK. The route handler then
re-renders the form with the error message above the fields.

```python
def _login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped
```

**Algorithm**: gate-on-session. Look up `user_id` in the Flask
session; if absent, redirect to `/login`; otherwise delegate to the
wrapped view. `functools.wraps` preserves `view.__name__` so
`url_for("profile")` keeps working.

```python
def _redirect_if_authenticated(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if session.get("user_id"):
            return redirect(url_for("landing"))
        return view(*args, **kwargs)
    return wrapped
```

Mirror of the above: already-signed-in users don't see the login or
register pages — they get bounced to the landing page.

### 3.4 Landing and auth routes

#### `/` — landing (`app.py:79-81`)

```python
@app.route("/")
def landing():
    return render_template("landing.html")
```

A pure render — no database, no auth, no parameters.

#### `/register` (`app.py:84-108`)

The `GET` path renders the form. The `POST` path runs `_validate_registration`,
hashes the password, attempts the insert, and either re-renders with an
error (on validation failure or unique-email collision) or redirects to
`/login`.

```python
try:
    db.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        (name, email, generate_password_hash(password)),
    )
    db.commit()
except sqlite3.IntegrityError:
    return render_template("register.html",
                           error="An account with that email already exists.")
```

The `try/except IntegrityError` is the **standard SQLite pattern** for
handling a `UNIQUE` constraint violation. Because the
`email` column is declared `UNIQUE` in the schema, the database
itself enforces uniqueness — the application only needs to translate
the constraint failure into a friendly error.

#### `/login` (`app.py:111-141`)

```python
row = db.execute(
    "SELECT id, name, password_hash FROM users WHERE email = ?",
    (email,),
).fetchone()

if row is None or not check_password_hash(row["password_hash"], password):
    return render_template("login.html", error="Invalid email or password.")

session["user_id"] = row["id"]
session["user_name"] = row["name"]
return redirect(url_for("profile"))
```

**Algorithms and decisions worth flagging:**

- **Single error message for "no such user" and "wrong password."**
  This is an intentional **anti-enumeration measure** — without it,
  an attacker could use the login form to learn which emails are
  registered. (`app.py:127-130`).
- **`session.clear()` is not called** on a failed login, so a
  previous user's session is not accidentally reused.
- **Successful logins redirect to `/profile`**, not `/dashboard` —
  the comment at `app.py:134-138` explains the reasoning: returning
  users get straight to their stats.

#### `/logout` (`app.py:158-162`)

```python
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))
```

**Note**: this is a `GET` request. That's fine for "log me out" but
worth knowing for security reviews — see the analysis document for
the implications.

### 3.5 Date helpers and the profile filter

`_PRESETS` (`app.py:184-190`) is a small dict that maps a preset name
to a human-readable label. The route uses `_resolve_preset(preset,
today)` (`app.py:193-209`) to expand a preset into a `(from, to)`
date tuple.

```python
def _resolve_preset(preset: str, today: date) -> tuple[date | None, date | None]:
    if preset == "this-month":
        return (today.replace(day=1), today)
    if preset == "last-month":
        first_this_month = today.replace(day=1)
        last_prev_month = first_this_month - timedelta(days=1)
        return (last_prev_month.replace(day=1), last_prev_month)
    if preset == "last-30-days":
        return (today - timedelta(days=29), today)
    if preset == "last-7-days":
        return (today - timedelta(days=6), today)
    return (None, None)
```

**Algorithm:** each branch computes its endpoints using only `today`
and the `timedelta` arithmetic. Note that `last-7-days` is **inclusive
of today** — six days back, plus today, is a 7-day window.

`_parse_iso_date` (`app.py:212-225`) parses a `YYYY-MM-DD` string
into a `date` object, or appends an error to a list and returns
`None`. Empty strings are treated as "unbounded" without an error —
a valid state.

`_date_bounds` (`app.py:228-242`) builds the SQL fragment:

```python
def _date_bounds(from_date, to_date):
    clauses, params = [], []
    if from_date is not None:
        clauses.append("date >= ?")
        params.append(from_date.isoformat())
    if to_date is not None:
        clauses.append("date <= ?")
        params.append(to_date.isoformat())
    return (" AND ".join(clauses), params)
```

**Why this works on text columns**: SQLite stores dates as ISO
`YYYY-MM-DD` strings, and ISO strings sort lexicographically the
same way they sort chronologically. The comment at `app.py:231-233`
calls this out.

### 3.6 `/profile` route (`app.py:249-402`)

This is the longest route handler in the project. It does, in order:

1. **Parse and validate the date filter** from the query string.
2. **Build the WHERE fragment** for `date` bounds.
3. **Run five SQL queries**:
   - `SELECT user details`
   - `SELECT SUM(amount)` (total spent)
   - `SELECT COUNT(*)` (transaction count)
   - `SELECT category, SUM(amount) ... LIMIT 1` (top category)
   - `SELECT category, SUM(amount) GROUP BY category` (per-category)
   - `SELECT individual expenses` (for the detailed table)
4. **Format the results** for the template (currency, initials,
   member-since).
5. **Render** `profile.html` with everything in scope.

Two small algorithms are worth pointing out:

```python
parts = (user["name"] or "").split()
initials = "".join(p[0] for p in parts[:2]).upper() or "?"
```

`initials` takes the first character of each of the first two
whitespace-separated words and uppercases them. The `or "?"` is a
defensive fallback for empty/whitespace names.

```python
day_fmt = "%#d" if sys.platform.startswith("win") else "%-d"
member_since = parsed.strftime(f"{day_fmt} %B %Y")
```

This is the **cross-platform day-of-month formatting** workaround.
`%-d` (Unix) and `%#d` (Windows) are not interchangeable, so the
code branches on `sys.platform`.

### 3.7 Add / Edit / Delete expense routes

#### `/expenses/add` (`app.py:405-490`)

The form has four fields (amount, category, date, description). On
`POST`, the handler:

1. **Verifies the CSRF token** by comparing
   `request.form.get("csrf_token")` to `session["csrf_token"]`. A
   mismatch returns 403.
2. **Validates each field** with a small set of rules:
   - amount must be a positive float,
   - category must be in `CATEGORIES` (imported from `database.db`),
   - date must parse as `YYYY-MM-DD`.
3. **Re-renders with errors** if validation fails, preserving the
   user's input so they don't have to retype.
4. **Calls `insert_expense`** from `database.queries` on success and
   redirects to `/profile`.

The CSRF token is generated on `GET` with `secrets.token_hex(16)`
(`app.py:485`) and stored in the session.

#### `/expenses/<int:id>/edit` (`app.py:493-591`)

Same shape as `add`, but:

- It first fetches the expense with `get_expense_by_id(id, user_id)`.
  If the expense doesn't exist or doesn't belong to the user, the
  helper returns `None` and the route returns 404.
- The form fields are pre-populated from the existing row.
- On success it calls `update_expense` and redirects to `/profile`.

#### `/expenses/<int:id>/delete` (`app.py:594-609`)

```python
@app.route("/expenses/<int:id>/delete", methods=["POST"])
@_login_required
def delete_expense(id):
    user_id = session["user_id"]
    expense = get_expense_by_id(id, user_id)
    if expense is None:
        return "Expense not found", 404
    db_delete_expense(id, user_id)
    return redirect(url_for("profile"))
```

`POST`-only — deletes can never be triggered by a casual link
click. The ownership check is enforced by `get_expense_by_id` and
re-enforced inside `db_delete_expense` (the `WHERE` clause includes
`user_id`).

### 3.8 Dev server entry point (`app.py:612-614`)

```python
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run(debug=True, host="0.0.0.0", port=port)
```

`debug=True` enables the Werkzeug interactive debugger. The port is
configurable via the `PORT` env var (Railway uses this); the default
`5001` is intentional because `5000` is often taken on dev machines
(see `CLAUDE.md`).

---

## 4. Database Layer: `database/db.py`

This file owns the **schema** and the **connection lifecycle**.

### 4.1 Schema (`db.py:28-47`)

```python
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
```

**Schema decisions worth knowing:**

- `id` is `INTEGER PRIMARY KEY AUTOINCREMENT` — SQLite's recommended
  way to get auto-incrementing integer ids.
- `email` is `UNIQUE` — the database enforces uniqueness; the
  application translates violations into friendly errors.
- `password_hash` is `NOT NULL` — accounts without a password can't
  exist.
- `created_at` uses `datetime('now')` as a default, so the database
  stamps the row when it's inserted.
- `expenses.user_id` is a **foreign key** to `users.id`. Foreign keys
  are not enforced by SQLite by default; the connection must turn
  them on with `PRAGMA foreign_keys = ON` (see `db.py:94`).
- `expenses.date` is `TEXT` rather than a date type — SQLite has no
  native date type, and ISO `YYYY-MM-DD` strings sort correctly
  with `<=` / `>=`.

### 4.2 `CATEGORIES` constant (`db.py:53-61`)

```python
CATEGORIES = (
    "Food", "Transport", "Bills", "Health",
    "Entertainment", "Shopping", "Other",
)
```

The seven valid expense categories. **There is no `categories`
table** — these are a hard-coded tuple. Application code
(`app.py:435-436`, `app.py:524-526`) validates user input against
this tuple.

### 4.3 Connection helpers

`_resolve_db_path(app)` (`db.py:68-79`) returns the absolute path to
the SQLite file. It honours an explicit `app.config["DATABASE"]`,
otherwise it picks `expense_tracker.db` in the project root.

```python
def get_db() -> sqlite3.Connection:
    if "db" not in g:
        conn = sqlite3.connect(current_app_db_path())
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        g.db = conn
    return g.db
```

**Algorithm:** the connection is cached on Flask's `g` object —
a per-request namespace. Multiple `get_db()` calls in the same
request share one connection, and the teardown registered in
`init_db` closes it at the end of the request.

`row_factory = sqlite3.Row` lets us treat query results like
dictionaries (`row["column_name"]`) instead of tuples.

`_close_db` (`db.py:105-109`) is the teardown callback that runs at
the end of every request, closing the cached connection.

### 4.4 `init_db(app)` (`db.py:116-130`)

```python
def init_db(app) -> None:
    app.config["DATABASE"] = _resolve_db_path(app)
    app.teardown_appcontext(_close_db)

    conn = sqlite3.connect(app.config["DATABASE"])
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()
```

`executescript` is the right tool for running multi-statement SQL
at once. The connection is opened briefly, the script runs, and it
closes — a one-time bootstrap.

### 4.5 `seed_db()` (`db.py:153-181`)

Inserts one demo user (`demo@spendly.com` / `demo123`) and 8 sample
expenses **only if the `users` table is empty**:

```python
if db.execute("SELECT COUNT(*) FROM users").fetchone()[0] > 0:
    return
```

This short-circuit is what makes it safe to call `seed_db()` on
every server start without duplicating demo data.

---

## 5. Query Helpers: `database/queries.py`

Four small functions, one per CRUD operation. Every query is
**parameterized** — `?` placeholders, never f-strings — so SQL
injection is impossible.

```python
def get_expense_by_id(expense_id, user_id):
    db = get_db()
    return db.execute(
        "SELECT id, user_id, amount, category, date, description "
        "FROM expenses WHERE id = ? AND user_id = ?",
        (expense_id, user_id),
    ).fetchone()
```

**Pattern:** every read/write of an expense is scoped to `user_id`.
This is the single most important security invariant in the app:
it is impossible to read or modify someone else's expenses by
guessing or stealing the id.

```python
def insert_expense(user_id, amount, category, date, description) -> int:
    db = get_db()
    cursor = db.execute(
        "INSERT INTO expenses (user_id, amount, category, date, description) "
        "VALUES (?, ?, ?, ?, ?)",
        (user_id, amount, category, date, description if description else None),
    )
    db.commit()
    return cursor.lastrowid
```

The `description if description else None` is the only place we
collapse empty strings to SQL `NULL` — a small piece of data
normalisation.

`update_expense` and `delete_expense` follow the same pattern:
parameterized query, `user_id` in the `WHERE` clause, `commit()`
after, and a boolean return from `cursor.rowcount > 0` so the
caller can detect "row not found."

---

## 6. Seed Scripts

### 6.1 `seed_user.py`

A one-off script that creates a single fake Indian user. The name
pools (`FIRST_NAMES`, `LAST_NAMES`) are lists of plausible Indian
names spanning regions. The email is built as
`firstname.lastname<2-3 digits>@gmail.com`, and the script loops
until it lands an email that isn't already taken.

The script creates its **own** Flask app instance to mirror
`app.py`'s startup sequence — that's how it can call `get_db()` and
`init_db()` without the import-time side effects of importing
`app`.

### 6.2 `seed_expenses.py`

Inserts a configurable number of realistic expenses for a given
user, with weighted random categories (Food is the most common,
Health the least). The `TODAY` constant at `seed_expenses.py:62`
pins the random date generation to `2026-07-17` for reproducible
output:

```python
TODAY = date(2026, 7, 17)

def pick_random_date(months: int) -> date:
    year = TODAY.year
    month = TODAY.month - (months - 1)
    while month <= 0:
        month += 12
        year -= 1
    earliest = date(year, month, 1)
    span_days = (TODAY - earliest).days
    return earliest + timedelta(days=random.randint(0, span_days))
```

**Algorithm:** find the first day of the month that is `months-1`
months before `TODAY`, then add a random number of days up to the
span. The `while month <= 0` loop handles year wrap-around (e.g.
asking for 8 months of history in July 2026 requires walking back
into November 2025).

The actual insert is wrapped in a `with db:` block (`seed_expenses.py:106-112`)
which is SQLite's standard idiom for atomic transactions — if any
row fails, the whole batch rolls back.

---

## 7. Template System

Every page extends `base.html`. The base template defines four
blocks: `title`, `head`, `content`, `scripts`. The base also
pulls in the stylesheet, Google Fonts, and the Lucide icon
library:

```html
<script src="https://unpkg.com/lucide@latest"></script>
<link href="https://fonts.googleapis.com/css2?family=DM+Serif+Display..."
      rel="stylesheet">
<link rel="stylesheet" href="{{ url_for('static', filename='css/style.css') }}">
```

The navbar branches on `session.user_id`:

```html
{% if session.user_id %}
    <a href="{{ url_for('profile') }}">Profile</a>
    <a href="{{ url_for('analytics') }}">Analytics</a>
    <span>{{ session.get('user_name', '') }}</span>
    <a href="{{ url_for('logout') }}">Sign out</a>
{% else %}
    <a href="{{ url_for('login') }}">Sign in</a>
    <a href="{{ url_for('register') }}" class="nav-cta">Get started</a>
{% endif %}
```

### 7.1 `profile.html` — the most complex page

`profile.html` has three meaningful sections beyond the basic
filter form:

1. **Stats row** — three tiles for Total Spent / Transactions / Top
   Category. The values are pre-computed in the route, not in the
   template.
2. **Spending by category** — a table of category, amount, and a
   CSS-bar showing share. The bar widths are computed in the
   template with a per-row formula:
   ```jinja
   {% set pct = (row["total"] / total_spent * 100) if total_spent else 0 %}
   ```
3. **All Expenses** — the full row table with Edit / Delete actions.
   Delete is a `<form method="POST" ...>` with a JavaScript
   `onsubmit="return confirm(...)"` confirmation.
4. **Category Share** — a `<canvas>` that Chart.js turns into a
   doughnut chart using a JSON-serialised data block:
   ```jinja
   const categoryData = {{ category_rows|tojson }};
   ```

The Chart.js script also defines a per-category colour map inline:
```js
const colors = {
    'Food': '#e6a23c',
    'Transport': '#5b7fa6',
    ...
};
```

These are hard-coded — not pulled from CSS variables. A future
refactor could share a single source of truth between the template
and the stylesheet.

### 7.2 The CSRF token in form templates

Both `expenses/add.html` and `expenses/edit.html` include:

```html
<input type="hidden" name="csrf_token" value="{{ session.get('csrf_token', '') }}">
```

The server checks this on `POST` (see `app.py:411-414` and
`app.py:501-504`).

### 7.3 Landing page video modal

The "See how it works" link opens a YouTube iframe in a modal. The
iframe uses a **deferred-load** pattern:

- The `<iframe>` has `data-src="..."` and `src=""`.
- On modal open, the script sets `src` to the real URL with
  `?autoplay=1`.
- On modal close, it clears the `src` again so the video stops.

The relevant code is in `landing.html:453-510`. The same pattern
is used in production websites to defer third-party media until
the user actually asks for it.

---

## 8. Static Assets: CSS, JS, Images

### 8.1 `static/css/style.css`

A single hand-written stylesheet. The top of the file defines
**design tokens** as CSS variables on `:root` (`style.css:5-34`):

```css
:root {
    --ink: #1a2019;
    --paper: #f8f4e8;
    --paper-card: #ffffff;
    --accent: #3f5e3a;
    --accent-strong: #2c4527;
    --accent-2: #b88247;
    --border: #e4dfcc;
    --border-soft: #eeebde;
    --font-display: 'DM Serif Display', Georgia, serif;
    --font-body: 'DM Sans', system-ui, sans-serif;
    --max-width: 1200px;
    --auth-width: 440px;
    --radius-sm: 6px;
    --radius-md: 12px;
    --radius-lg: 20px;
    --radius-xl: 28px;
}
```

**The rebrand from forest-green to blue-and-gold was applied by
editing this file** (`6ad170c feat: rebrand to MoneyTrail with blue
and gold palette`). The current values are the rebrand values —
the older `--accent: #1a472a` and `--accent-2: #f4a261` were
overwritten.

The rest of the file is conventional CSS:

- A small `* { box-sizing: border-box; margin: 0; padding: 0; }`
  reset.
- Sticky navbar with `position: sticky; top: 0; z-index: 100;`.
- Sectioned styles for `.hero`, `.stat-band`, `.feature-grid`,
  `.testimonial-grid`, `.pricing-grid`, etc.
- Form and button styles (`.btn-primary`, `.btn-ghost`, `.btn-submit`).
- Profile-specific styles (`.profile-stats`, `.breakdown-table`,
  `.bar-track`, `.bar-fill`).
- Responsive tweaks at the bottom of the file.

There is no preprocessor (no SASS, no PostCSS). The token system
is plain CSS variables, which is modern enough for this size of
project.

### 8.2 `static/js/main.js`

```js
// main.js — students will add JavaScript here as features are built
```

A single comment. The project has two other places with
JavaScript:

- `landing.html`'s `{% block scripts %}` block has the video-modal
  controller inline (`landing.html:453-510`).
- `profile.html`'s `{% block scripts %}` block has the doughnut
  chart and the preset-preview nicety inline
  (`profile.html:194-279`).

This is consistent with the rest of the project's "place each
script close to where it is used" philosophy.

### 8.3 `static/img/`

- `hero.svg` — the hero illustration on the landing page (likely
  the Figma export).
- `figma-reference.png` — a reference image kept in the repo (see
  the `feature/10-ui-rebrand` commits; the Figma source is the
  design's source of truth).

---

## 9. Automated Tests

### 9.1 `tests/conftest.py` — the fixture

The conftest is unusual. Rather than using the standard
`pytest-flask` pattern of `app.test_client()`, it **builds a fresh
Flask instance per test** by copying the dev app's URL map onto a
new `Flask` object. The rationale is in the comment block at
`tests/conftest.py:7-14`:

> Importing `app` once at module-load time runs `app.py`'s
> top-level `init_db(app)` and `seed_db()` against the dev
> `expense_tracker.db`, which is fine. But Flask locks
> `teardown_appcontext` registration after the first request,
> so we can't call `init_db` again on the same Flask instance.

The fixtures:

- `app` — a fresh Flask instance pointed at a `tmp_path` SQLite
  file. Isolated per test.
- `client` — `app.test_client()`.
- `auth_client` — a `client` that has already POSTed to `/login`
  with the demo credentials.

### 9.2 `test_06-date-filter.py`

A 26-test suite covering the date filter. It is split into logical
groups via comment dividers:

- **Auth guard** — one test that `/profile` redirects when signed
  out.
- **Default view** — three tests that the unfiltered page is
  correct.
- **Preset behaviour** — five tests, one per preset, plus a check
  that the right pill is highlighted.
- **Custom range** — three tests including a single-day boundary
  test.
- **Validation errors** — two tests that bad input doesn't 500.
- **Filter affects every section** — two tests that the chart
  payload and the category badges respect the filter.
- **Form behaviour** — three tests that the form is a `GET` form
  and that the page works without JavaScript.
- **No data leak** — one test that creates a second user and
  asserts they see no demo-user data.
- **Currency symbol** — one test that the rupee symbol always
  appears.

### 9.3 `test_07_add_expense.py`

A 13-test suite for the add-expense feature. Same structural
organisation:

- **Auth guards** — both `GET` and `POST` are protected.
- **`GET` form** — five tests for the rendered form's fields.
- **`POST` happy path** — two tests, one checking the redirect
  and one checking the database row was actually inserted.
- **`POST` validation errors** — seven tests, one per error
  case (missing amount, zero amount, negative amount, invalid
  category, missing date, invalid date, empty description).
- **`POST` repopulates form on error** — one test for the
  "preserve user input on error" behaviour.
- **Unit tests on `insert_expense`** — three tests, including
  null and empty description handling.

The tests use a small regex helper (`_get_csrf_token`,
`test_07_add_expense.py:65-68`) to extract the CSRF token from
the rendered form before submitting.

---

## 10. Configuration and Tooling

### 10.1 `requirements.txt`

```
flask==3.1.3
werkzeug==3.1.6
pytest==8.3.5
pytest-flask==1.3.0
```

The versions are pinned exactly. New contributors should use a
virtual environment to avoid conflicts with system packages.

### 10.2 `.gitignore`

```
venv/
expense_tracker.db
__pycache__/
*.pyc
*.pyo
.env
.DS_Store
.claude/plans/
```

The first two are the most important: the SQLite file and the
Python virtual environment should never enter version control.

### 10.3 `CLAUDE.md`

Project-level notes for the AI assistant. Documents:

- The "step-by-step teaching scaffold" nature of the codebase.
- The fact that placeholders like `Step 3` exist where future
  code goes.
- Branding ("Spendly" in `CLAUDE.md`, "MoneyTrail" everywhere
  else — `CLAUDE.md` is mildly out of date; the rebrand renamed
  the app everywhere except this file).
- Run instructions (`python app.py`, port 5001).
- Architecture summary.
- Watch-outs (the deferred-load YouTube iframe, the `.gitignore`,
  the `5001` port choice).

### 10.4 Deployment

The most recent commits show deployment to **Railway** is the
expected target:

- `f6023ed trigger railway redeploy` — a no-op commit to force a
  rebuild.
- Railway's `PORT` env var is honoured by `app.py`'s entry
  point.

---

## 11. End-to-End Workflows

### 11.1 Sign-up → First expense

```
GET /register
  → render register.html (empty form, 200)

POST /register {name, email, password}
  → _validate_registration
  → INSERT INTO users
  → 302 /login

GET /login
  → render login.html (empty form, 200)

POST /login {email, password}
  → SELECT id, name, password_hash FROM users WHERE email=?
  → check_password_hash
  → session["user_id"]=row["id"]
  → session["user_name"]=row["name"]
  → 302 /profile

GET /profile
  → 5 SQL queries (no filter)
  → render profile.html

GET /expenses/add
  → session["csrf_token"] = secrets.token_hex(16)
  → render add.html

POST /expenses/add {amount, category, date, description, csrf_token}
  → CSRF check
  → validate fields
  → insert_expense()
  → 302 /profile
```

### 11.2 Filter the profile page

```
GET /profile?preset=last-7-days
  → _resolve_preset("last-7-days", today)
      → (today - 6 days, today)
  → _date_bounds(...) → " AND date >= ? AND date <= ?"
  → 4 expense queries with the WHERE bound applied
  → render profile.html with the active pill highlighted
```

### 11.3 Edit an expense

```
GET /expenses/42/edit
  → get_expense_by_id(42, user_id)
  → session["csrf_token"] = secrets.token_hex(16)
  → render edit.html with fields pre-populated

POST /expenses/42/edit {amount, category, date, description, csrf_token}
  → CSRF check
  → validate fields
  → update_expense(42, user_id, ...)
  → 302 /profile
```

### 11.4 Delete an expense

```
POST /expenses/42/delete
  → get_expense_by_id(42, user_id)  [ownership check]
  → delete_expense(42, user_id)
  → 302 /profile
```

The `<form>` on the profile page's table calls this with a
JavaScript `confirm()` dialog. The form is the only path to this
endpoint — `methods=["POST"]` only.

---

## Quick Reference: Code Paths by Concern

| Concern                 | Files / functions                                                                   |
|-------------------------|--------------------------------------------------------------------------------------|
| Schema                  | `database/db.py` — `SCHEMA`                                                         |
| Connection lifecycle    | `database/db.py` — `get_db`, `_close_db`, `init_db`                                  |
| Migrations              | None — schema is `CREATE TABLE IF NOT EXISTS` only                                  |
| Seeding                 | `database/db.py` — `seed_db`; `seed_user.py`; `seed_expenses.py`                    |
| Expense CRUD            | `database/queries.py` — `get_expense_by_id`, `insert_expense`, etc.                 |
| Auth (login/logout)     | `app.py` — `/login`, `/logout`, `_login_required`, `_redirect_if_authenticated`     |
| Session                 | `app.secret_key` (`app.py:20`); `session` from `flask`                              |
| Password hashing        | `werkzeug.security.generate_password_hash` / `check_password_hash`                  |
| CSRF                    | `app.py:485` (generation), `app.py:411-414` / `app.py:501-504` (verification)       |
| Date helpers            | `app.py` — `_resolve_preset`, `_parse_iso_date`, `_date_bounds`                     |
| Profile render          | `app.py` — `/profile`; `templates/profile.html`                                     |
| Front-end build         | None (no transpiler, no bundler)                                                    |
| Tests                   | `tests/conftest.py`; `tests/test_06-date-filter.py`; `tests/test_07_add_expense.py` |
| Deployment              | `app.py` — `if __name__ == "__main__":` reads `PORT` env var; Railway                |

---

*End of technical-explanation.md*
