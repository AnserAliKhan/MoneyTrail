# MoneyTrail — Analysis, Issues, and Stack Review

> A candid review of the MoneyTrail codebase as it stands. This
> document identifies UI issues, backend issues, security concerns,
> inefficient code, and gives an opinionated take on whether the
> current tech stack is the right one. Issues are sorted by severity
> within each section, and each entry has a concrete
> `file_path:line_number` reference so the suggestions can be acted
> on directly.

> **Severity legend:** 🔴 critical · 🟠 high · 🟡 medium · 🔵 low / nits

---

## Table of Contents

1. [Security](#1-security)
2. [Backend Correctness and Robustness](#2-backend-correctness-and-robustness)
3. [Database Design](#3-database-design)
4. [Performance and Efficiency](#4-performance-and-efficiency)
5. [UI / UX Issues](#5-ui--ux-issues)
6. [Code Hygiene and Maintainability](#6-code-hygiene-and-maintainability)
7. [Testing Gaps](#7-testing-gaps)
8. [Tech Stack: Is This the Right One?](#8-tech-stack-is-this-the-right-one)
9. [Recommended Next Steps](#9-recommended-next-steps)

---

## 1. Security

### 🟠 S1. `secret_key` is a hard-coded literal

`app.py:20`

```python
app.secret_key = "dev-secret-change-me"
```

If the app is ever deployed as-is, anyone who has read the
repository (or `git log`) can forge session cookies. A
`# TODO: replace with env var in production` comment exists, but
the production migration has not happened.

**Fix:** read from `os.environ.get("SECRET_KEY")` and raise at
startup if it's missing in production.

```python
app.secret_key = os.environ.get("SECRET_KEY")
if not app.secret_key:
    raise RuntimeError("SECRET_KEY is required in production")
```

### 🟠 S2. `/logout` is `GET`, not `POST`

`app.py:158-162`

```python
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))
```

Because this is a `GET`, any third-party site that loads an
`<img src="https://moneytrail.example/logout">` (or a similar
"drive-by logout" technique) can sign a user out without their
consent. Compare to `/expenses/<id>/delete`, which is correctly
`POST`-only.

**Fix:** make it `POST` and add a CSRF token + a small "Sign out"
form in the navbar.

### 🟠 S3. CSRF protection is incomplete

`app.py:405-490` (add) and `app.py:493-591` (edit) verify the CSRF
token only on `POST`. The pattern is:

```python
submitted_token = request.form.get("csrf_token")
stored_token = session.get("csrf_token")
if not submitted_token or submitted_token != stored_token:
    return "CSRF token validation failed", 403
```

The check is present but **ad-hoc**: there is no helper, no
template macro, and no `<meta>` tag. It is easy to forget when
adding a new form. Compare with the Flask-WTF or Flask-SeaSurf
ecosystem, which provide a single decorator to apply CSRF
globally.

**Additionally:** the token is stored in `session` but never
rotated. The same token is reused for as long as the session
lives. Strict CSRF practice rotates the token on every form
render.

**Fix:** adopt a single CSRF helper (`@csrf_protect` decorator +
`csrf_token()` template global) so the rule is enforced in one
place.

### 🟠 S4. `/register` and `/login` allow unlimited brute-force attempts

`app.py:84-141`

There is no rate limiting on either endpoint. An attacker can
script thousands of login attempts per second. The application
relies entirely on Werkzeug's password hashing (which is
intentionally slow) to make each attempt expensive, but that
isn't enough at scale.

**Fix:** introduce rate limiting — either at the reverse proxy
(nginx, Cloudflare) or in-app via `flask-limiter`.

### 🟡 S5. CSRF and session cookie flags are not hardened

`app.py:14`

```python
app = Flask(__name__)
```

`SESSION_COOKIE_SECURE`, `SESSION_COOKIE_HTTPONLY`, and
`SESSION_COOKIE_SAMESITE` are not set. The session cookie is
therefore transmitted over plain HTTP if the site is ever
served without TLS, is accessible to any JavaScript on the
page, and is sent in cross-site requests by default.

**Fix:**

```python
app.config.update(
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
)
```

### 🟡 S6. The login error message is good, but timing is not constant

`app.py:127-130` shows a single error message for both
"no such user" and "wrong password" — good. But the two code
paths take different amounts of time (the no-such-user path
returns immediately; the wrong-password path runs
`check_password_hash`, which is intentionally slow). A
network-side timing attack can still distinguish them.

**Fix:** run `check_password_hash` against a fixed dummy hash
when the user does not exist, so both paths take the same time.

### 🟡 S7. `category` is a free-text field in the database

`db.py:53-61` defines `CATEGORIES` as a Python tuple, but the
column is just `TEXT NOT NULL`. Application code validates
input against the tuple (`app.py:435-436`), which is fine in
the current code, but the database itself will accept any
string. A future bug or a direct SQL write could create
"Foo123" as a category.

**Fix:** add a `CHECK` constraint in the schema:

```sql
category TEXT NOT NULL CHECK (category IN (
    'Food', 'Transport', 'Bills', 'Health',
    'Entertainment', 'Shopping', 'Other'
))
```

### 🟡 S8. The CSRF token in templates uses an empty-string fallback

`templates/expenses/add.html:21` and `edit.html:21`:

```html
<input type="hidden" name="csrf_token" value="{{ session.get('csrf_token', '') }}">
```

If for any reason the session does not have a token (e.g. a
race during login or a back-button), the form silently submits
an empty string, which the server then correctly rejects with
a 403 — but the user sees a bare "CSRF token validation
failed" message rather than a friendly retry.

**Fix:** ensure the GET handler always sets the token, and
consider showing a user-friendly error instead of a raw 403.

### 🔵 S9. The YouTube iframe has a hard-coded video id

`templates/landing.html:440` hard-codes
`data-src="https://www.youtube.com/embed/dQw4w9WgXcQ"`. This is
the Rickroll video — likely a placeholder, but it should be
replaced with a real product video before launch.

### 🔵 S10. The favicon is a data URI

`templates/base.html:7` — fine for a small project, but worth
replacing with a proper SVG asset once one is designed.

---

## 2. Backend Correctness and Robustness

### 🟠 B1. `app.py` mixes routes, helpers, validators, decorators, and queries

`app.py` is 614 lines long and contains every route in the
project. This makes it hard to navigate and review. As more
features land, this file will become unmanageable.

**Fix:** split into a `routes/` package — one module per
resource (`auth.py`, `profile.py`, `expenses.py`, etc.). The
helper functions (date, validators, decorators) belong in a
`utils.py` or `services/` module.

### 🟠 B2. The `app.py` import-time side effects

`app.py:30-32`:

```python
with app.app_context():
    init_db(app)
    seed_db()
```

This runs every time the module is imported. That is fine for
the dev server and for Railway, but it means:

- Importing `app` for tests (e.g. in `tests/conftest.py`) writes
  to the dev database, which is then unimported in fixtures.
- The current conftest works around this with a custom
  "build a fresh Flask" routine that copies the URL map
  (`tests/conftest.py:20-53`). This is a sign that the
  bootstrap is in the wrong place.

**Fix:** move `init_db` and `seed_db` to an explicit
`create_app()` factory function:

```python
def create_app():
    app = Flask(__name__)
    app.config.from_object("config.Config")
    with app.app_context():
        init_db(app)
        seed_db()
    return app
```

This also unlocks per-test app instances trivially.

### 🟠 B3. No migrations

The schema lives in a Python string. Adding a column or a new
table means manually running `ALTER TABLE` against the
production database. There is no migration history, no
rollback, no environment parity check.

**Fix:** adopt Flask-Migrate (which wraps Alembic). The
initial migration can be autogenerated from the existing
`SCHEMA` string.

### 🟡 B4. The `/profile` handler runs four SQL queries in sequence

`app.py:298-342` issues five separate queries
(`SELECT user`, `SUM(amount)`, `COUNT(*)`, top category,
per-category, individual rows) in series. They are not pipelined
and not run in the same transaction.

**Fix options:**

- Combine the aggregates into one or two queries using
  conditional aggregation.
- Run them inside a single connection (Flask already gives you
  one connection per request — verify it's being reused).
- For higher traffic, pre-compute a per-user materialised summary
  that's updated when an expense is added/edited/deleted.

### 🟡 B5. The date filter falls back to "no filter" on any error

`app.py:272-275`:

```python
if from_date is not None and to_date is not None and from_date > to_date:
    from_date = None
    to_date = None
    errors.append("Start date must be on or before end date.")
```

This is a reasonable default, but it silently widens the
visible result set. A user with `from=2026-07-15&to=2026-07-01`
intuitively expects to see no rows, not "all 8 of last month's
expenses." The test suite verifies the current behaviour
(`test_06-date-filter.py:253-274`), so the contract is clear,
but the UX could be confusing.

**Fix:** keep the filter applied (return zero rows) and just
show the error message — don't silently widen the window.

### 🟡 B6. `_parse_iso_date` and `_date_bounds` ignore timezones

`app.py:212-242`. `date` and `datetime` are used naively. A
user in Karachi logging an expense at 11pm and viewing their
profile in New York will see the expense dated a day later
because of naive datetime comparisons. Not currently a problem
for a single-region product, but worth flagging.

**Fix:** store all dates in UTC and render in the user's
timezone. Use `zoneinfo` (Python 3.9+ stdlib).

### 🟡 B7. The `description` field has a 200-char limit in the form but not the database

`templates/expenses/add.html:58` and `edit.html:58` use
`maxlength="200"`. The database column has no `LENGTH` cap.
That's fine, but the inconsistency is a minor smell — the
limit is enforced in the browser, not on the server.

**Fix:** add a server-side `len(description) <= 200` check in
the validation block, or remove the cap from the form.

### 🟡 B8. No upper bound on the `amount` field

`templates/expenses/add.html:25-32`. `step="0.01" min="0.01"`
are HTML hints only. A malicious or careless user could POST
`amount=99999999999999` and corrupt the totals. The
`COALESCE(SUM(amount), 0)` won't fail, but downstream display
could break.

**Fix:** add a server-side cap, e.g. `amount <= 1_000_000`.

### 🔵 B9. The `dashboard` page is essentially dead

`templates/dashboard.html` and `app.py:165-168` are a placeholder
that says "Your dashboard is coming in a later step." Now that
the profile page is rich, the dashboard route should either be
removed or repurposed. Right now it is reachable from a link
in the profile page (`templates/profile.html:185`) and shows
"Welcome, X. Sign out."

**Fix:** redirect `/dashboard` to `/profile`, or build it out.

### 🔵 B10. `Member since` formatting branches on platform

`app.py:366-369` checks `sys.platform.startswith("win")` to
choose between `%-d` and `%#d`. This is fine, but a cleaner
option is `parsed.strftime("%-d %B %Y")` after replacing with
a manual zero-strip — or just use `babel` or `pendulum` for
locale-aware formatting.

---

## 3. Database Design

### 🟠 D1. No cascading delete

`db.py:38-46` defines the foreign key but does not specify
`ON DELETE CASCADE`. If a `users` row is ever deleted, the
`expenses.user_id` foreign-key constraint will reject the
delete (because `PRAGMA foreign_keys = ON`), and there is no
UI path to delete a user. This is fine for the current product
(no "delete account" feature), but it is a sharp edge if one
is added later.

**Fix:** when implementing account deletion, decide on
`ON DELETE CASCADE` (delete expenses with the user) or
`ON DELETE RESTRICT` (block deletion while expenses exist), and
be explicit about the choice.

### 🟡 D2. No indexes beyond the implicit primary key

`db.py:37-46`. The `expenses` table has no index on
`user_id`, `date`, or `category`. The current data volumes
are tiny, so this is invisible. At 10K+ expenses per user,
the `WHERE user_id = ?` filter in `/profile` will start to
hurt.

**Fix:**

```sql
CREATE INDEX IF NOT EXISTS idx_expenses_user_id
    ON expenses(user_id);
CREATE INDEX IF NOT EXISTS idx_expenses_user_date
    ON expenses(user_id, date);
```

### 🟡 D3. `category` is a `TEXT` with no `CHECK` constraint

See S7. The categories are validated in application code
only. A `CHECK` constraint is one line of SQL and would make
the database a second line of defence.

### 🟡 D4. `amount` is `REAL` (IEEE-754 double)

`db.py:40`. Using `REAL` for currency is a known anti-pattern
because of rounding. For a personal-expense tracker the
inaccuracies are usually invisible (a few paise), but at
larger sums the rounding errors compound.

**Fix options:**

- Store amounts in **paise** (integer cents) and divide by 100
  on display. This is the approach used by most fintech apps.
- Or use SQLite's `NUMERIC` type with explicit `DECIMAL`-style
  rounding in Python.

### 🔵 D5. The `created_at` column is stored as text

`db.py:34` and `db.py:44` use `TEXT NOT NULL DEFAULT
(datetime('now'))`. ISO text sorts correctly, so this is
fine, but you lose the ability to do native date arithmetic
(e.g. "show me expenses added in the last hour"). If the
product ever needs that, switch to ISO text + a `DATETIME()`
cast in queries.

### 🔵 D6. The `demo` user has no password policy

`db.py:166-169` seeds `demo@spendly.com` with the password
`demo123` — only 7 characters, below the application
validator's 8-character rule. The seeder bypasses the
validator, so the database ends up with a user whose password
doesn't meet the rule the app enforces.

**Fix:** have the seeder hash a password that passes the
validator, or skip the password check by setting the rule
explicitly for the demo user.

---

## 4. Performance and Efficiency

### 🟡 P1. The profile page re-runs the same five queries on every visit

`app.py:298-342`. There is no caching. Every visit — including
refreshes — runs the same SELECTs.

**Fix:** add a small per-user, per-filter cache (e.g. via
`functools.lru_cache` keyed on `(user_id, from_date, to_date)`),
or precompute a per-user summary in a `user_stats` table that
is updated when expenses change.

### 🟡 P2. `format(total_spent)` happens in Python for every render

`app.py:349` runs `f"₨{total_spent:,.2f}"` on every render. At
scale this is fine, but combined with P1 it adds up.

### 🟡 P3. `category_rows = [dict(row) for row in category_rows]`

`app.py:346`. This is a Python-level conversion from
`sqlite3.Row` to `dict` so the data can be JSON-serialised
for the Chart.js blob. Done on every render.

**Fix:** for larger datasets, send only the two columns the
chart needs (`category`, `total`) as a JSON list of lists, not
a list of dicts. Cheaper to serialise, smaller payload.

### 🟡 P4. The landing page loads three external resources synchronously

`templates/base.html:8-11`:

```html
<script src="https://unpkg.com/lucide@latest"></script>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=DM+Serif+Display..." rel="stylesheet">
```

This adds at least two DNS lookups and a font download to every
page load — including pages that don't actually use Lucide
icons (e.g. `/login`, `/register`). The chart script is also
loaded from a CDN only on the profile page, which is correct.

**Fix:**

- Inline Lucide (or switch to per-page `<script>` includes).
- Use `font-display: swap` (already implicit in the URL but
  worth verifying) and preload only the weights you actually
  use.
- Consider self-hosting the fonts to avoid the extra TLS
  round-trip.

### 🔵 P5. The CSS file is one large file

`static/css/style.css` is a single hand-written file. There is
no bundling, no minification, no purging. For a project this
size, that's fine. If it grows, run it through `purgecss` to
strip unused selectors.

### 🔵 P6. No HTTP caching headers

Static files are served by Flask's dev server with default
headers. In production behind a reverse proxy, `Cache-Control:
public, max-age=31536000, immutable` on hashed assets would
be the right call. Currently there is nothing in the
deployment story that sets these.

---

## 5. UI / UX Issues

### 🟡 U1. The navbar has no "active" indicator on `/expenses/add` or `/expenses/<id>/edit`

`templates/base.html:24-32` only highlights `Profile` and
`Analytics`. While the user is on the Add or Edit Expense
form, no link is highlighted. A small thing, but it makes
the page feel dislocated.

### 🟡 U2. The "All Expenses" table has no pagination

`templates/profile.html:124-152`. A user with 500 expenses sees
all 500 rows on a single page. There is no client-side or
server-side pagination.

**Fix:** add `LIMIT ? OFFSET ?` to the query in `app.py:337-342`
and "Previous / Next" links in the template.

### 🟡 U3. The "Top category" tile shows the category name with no context

`templates/profile.html:75-84`. If the user has spent ₨4,200 on
Food out of a total of ₨6,000, the tile says "Food" with no
amount. Showing the amount or the percentage would make the
tile immediately useful.

### 🟡 U4. The delete confirmation is browser-native and unstyled

`templates/profile.html:145`:

```html
<form onsubmit="return confirm('Delete this expense?')">
    <button type="submit" class="btn-delete">Delete</button>
</form>
```

`window.confirm()` is functional but ugly and inconsistent with
the rest of the design system. A small custom modal would match
the rest of the app.

### 🟡 U5. The Add Expense form has no client-side validation feedback

`templates/expenses/add.html`. The browser uses HTML5
validation (`required`, `min="0.01"`, `type="number"`), but
there's no visual feedback when the user enters an invalid
amount. On submit, the server returns an error and re-renders
the page, but the in-page state is clunky.

### 🟡 U6. The doughnut chart colours are hard-coded in JavaScript

`templates/profile.html:230-238`. The seven category colours
live in a JavaScript object inside the page. They are not in
sync with the design tokens in `style.css`. If a brand refresh
changes a colour, this object must be updated by hand.

**Fix:** render the colour list from a single Python source of
truth (e.g. a dict imported from `database.db`) and pass it to
the template as JSON.

### 🟡 U7. The "Member since" format is locale-specific but uses English month names

`app.py:366-369` produces e.g. "18 July 2026" regardless of
the user's preferred language. For an audience in Pakistan or
India, a localised format ("18 Jul 2026" or Urdu/Hindi names)
would be more welcoming.

### 🟡 U8. The "Member since" date is duplicated on the profile page

`templates/profile.html:16` and `templates/profile.html:181-182`
both render `member_since`. Once is in the header pill, once
in the "info list" at the bottom. The bottom block is
arguably redundant — the header pill already conveys the same
information.

### 🟡 U9. The base template loads Chart.js on every page

`templates/base.html` only loads Lucide and the stylesheet.
Chart.js is correctly loaded only inside `profile.html`'s
`{% block scripts %}`. But the page also re-injects
`unpkg.com/lucide@latest` at `templates/profile.html:194`,
which means Lucide is loaded **twice** on the profile page.

**Fix:** remove the second `<script>` in `profile.html`.

### 🟡 U10. The `<a>` tag wraps the brand but the parent has no `aria-label`

`templates/base.html:19-22` — accessibility nit. Screen readers
will read "M MoneyTrail" because the icon span and the name
span are both text.

**Fix:** add `aria-label="MoneyTrail home"` to the anchor.

### 🔵 U11. The favicon is a generic monogram "M"

`templates/base.html:7` — fine, but a more distinctive mark
would help brand recognition in the browser tab.

### 🔵 U12. The analytics "Coming Soon" page links to `/profile` for "Back to Profile"

`templates/analytics.html:174` — minor, but the icon-arrow SVG
is a left arrow on a "back" link. Looks correct, but worth
double-checking the SVG.

### 🔵 U13. The pricing cards are both free

`templates/landing.html:374-411` shows two pricing cards, both
₨0. That's an honest representation of a free product, but a
single card would be more direct.

### 🔵 U14. The footer says "© 2026 MoneyTrail Systems Inc."

`templates/base.html:73`. The legal pages call it
"MoneyTrail," but the `terms.html` mailto is
`support@spendly.app` — an artefact of the pre-rebrand. Worth
updating to a MoneyTrail-branded address.

### 🔵 U15. The "Sign out" link uses a `GET`

`templates/base.html:28` — same issue as S2. A `POST` form is
the correct primitive.

### 🔵 U16. The YouTube iframe is hidden with `visibility: hidden` instead of `display: none`

`templates/landing.html:21-23`. The iframe is still in the
layout, so tab order can still hit it. A small `inert` attribute
on the modal would help.

---

## 6. Code Hygiene and Maintainability

### 🟡 C1. `app.py` is 614 lines and growing

See B1. The project is small enough today, but a single file
holding every route and helper is a maintenance risk.

### 🟡 C2. The tests directory has tests for only two features

`tests/` covers date filter (Step 6) and add expense (Step 7).
There are no tests for:

- Registration (Step 2)
- Login / logout (Step 3)
- Profile page rendering (Step 5)
- Edit expense (Step 8)
- Delete expense (Step 9)
- The seed scripts
- The `_resolve_preset` / `_parse_iso_date` / `_date_bounds`
  helpers (these are pure functions — easy to unit-test)
- The `insert_expense` / `update_expense` / `delete_expense`
  query helpers

This means the regression risk on every change is high.

### 🟡 C3. There is no `__init__.py` exporting anything

`database/__init__.py` is empty. Routes import from
`database.db` and `database.queries` directly. A small
re-export module would let consumers import
`from database import get_db, insert_expense` cleanly.

### 🟡 C4. Inconsistent type hints

`app.py` mixes `str | None` (PEP 604) with older typing. Both
work on Python 3.10+. Not a problem, but a `from __future__
import annotations` at the top of each file would let you use
the new style throughout without runtime cost.

### 🟡 C5. Several routes are placeholders

`app.py:165-175` defines `/dashboard` and `/analytics` as
minimal placeholders. `templates/dashboard.html` and
`templates/analytics.html` are 26 and 183 lines respectively,
mostly scaffolding. A README section or a TODO list describing
the next concrete step would help.

### 🟡 C6. The favicon inline SVG and the Lucide CDN are loaded even on the legal pages

`templates/terms.html` and `templates/privacy.html` extend
`base.html`, so they load the same nav, footer, and external
resources. The legal pages don't need Lucide icons or the
Chart.js script, but they pay the cost anyway.

### 🔵 C7. `if __name__ == "__main__":` has a bare `port=5001` default

`app.py:613`. Railway sets the `PORT` env var, so this works.
But the comment doesn't explain that Railway is the assumed
target.

### 🔵 C8. No `pyproject.toml` or `setup.cfg`

The project uses `requirements.txt` and that's it. There is no
package metadata, no `[tool.pytest.ini_options]`, no
configurable entry point beyond `python app.py`.

### 🔵 C9. `tests/conftest.py` is heavily commented

`tests/conftest.py:1-14` has a 14-line block comment explaining
the rationale for the custom fixture. The comment is excellent
— keep it. But a small `tests/README.md` could capture the
rationale once, in one place, instead of inline at the top of
the conftest.

---

## 7. Testing Gaps

### 🟡 T1. No tests for the auth flow

The most security-sensitive code (login, logout, registration,
CSRF) has no tests. `tests/test_07_add_expense.py` has CSRF
token extraction utilities that could be reused.

### 🟡 T2. No tests for the `database/queries.py` helpers

`insert_expense`, `update_expense`, `delete_expense`,
`get_expense_by_id` are all pure(ish) functions with simple
contracts. They should each have a unit test.

### 🟡 T3. No tests for `seed_db` or the seed scripts

`seed_user.py` and `seed_expenses.py` have logic for collision
handling and random date generation that should be tested
separately from the routes that consume them.

### 🟡 T4. No end-to-end "smoke" test

There is no test that asserts a fresh DB → register → login →
add expense → profile flow works end to end. A single
integration test covering this path would catch a wide class
of regressions.

### 🔵 T5. Tests use `b"..."` substring assertions on HTML

`test_07_add_expense.py:34-47` searches the response body for
specific byte strings. That works but is brittle — a
whitespace change in the template breaks the test. Tools like
`beautifulsoup4` or `selectolax` would give more robust
selectors.

---

## 8. Tech Stack: Is This the Right One?

This is the question that will draw the most debate. My honest
take:

### What works well

- **Flask + SQLite is the right size for a personal expense
  tracker.** A heavier framework (Django) would impose a lot of
  ceremony for a 600-line `app.py`. A lighter one (FastAPI) would
  lose the form-rendering + template engine that makes the
  marketing pages trivial.
- **Server-rendered Jinja2 templates** are perfect for a content
  site with a small amount of interactivity. No SPA needed.
- **Hand-written CSS with design tokens** is exactly the right
  call for a single-developer project. No Tailwind, no
  CSS-in-JS, no build step.
- **Chart.js via CDN** is the cheapest possible way to draw a
  doughnut chart.
- **Werkzeug's password hashing** is industry-standard and free.
- **pytest + pytest-flask** is the standard Python testing stack
  and the right choice.
- **Railway** is a good fit for a small Flask app — it picks up
  the `PORT` env var, runs the dev server, and re-deploys on
  push. Zero ops.

### What could be better

- **No migrations.** The schema lives in a string. This works
  for a single-developer project, but the day someone else
  touches the schema, they will need to be told. Adopt
  `Flask-Migrate` (Alembic) now, while the schema is small.
- **No CSRF helper.** Hand-rolled CSRF works but is easy to
  forget. Use `Flask-WTF` (which gives you both CSRF and form
  validation) or `Flask-SeaSurf` (CSRF only).
- **No rate limiter.** Add `Flask-Limiter` before exposing the
  login form to the internet.
- **No environment-driven config.** `app.secret_key` is a
  literal. A `Config` class loaded from env vars is the
  standard Flask idiom and would make the production story
  clean.
- **SQLite for the database.** This is fine for development and
  for a single-user product. The day you want to support
  concurrent users, real-time backups, or analytics queries
  over years of history, you'll want to migrate. SQLite's
  `WAL` mode and `Litestream` for backups can take you a long
  way first.
- **The frontend has no build step.** That's a strength for
  simplicity, but a small build step (esbuild or Vite) would
  let you split the JavaScript into modules and stop inlining
  large `<script>` blocks inside templates.
- **`amount REAL` is the wrong type for money.** Store integer
  paise and format in the UI.

### What I'd keep

- **Flask, not Django or FastAPI.** The size matches the
  problem.
- **Jinja2 server-side rendering, not a SPA.** The marketing
  pages benefit from SEO; the profile page has no need for
  client-side routing.
- **SQLite, not Postgres, for now.** Single-user product,
  single-server deploy. SQLite is the right answer until
  traffic or write volume demands otherwise.
- **Hand-written CSS, not Tailwind.** The design is bespoke and
  small enough to maintain by hand.
- **Railway, not Kubernetes.** No team to operate K8s, no
  scale to require it.

### What I'd add

- **Flask-Migrate** (for migrations)
- **Flask-WTF** or **Flask-SeaSurf** (for CSRF and form
  validation)
- **Flask-Limiter** (for rate limiting)
- **A `Config` class** with environment-variable loading
- **A real "delete account" flow** (with cascading delete or
  user anonymisation)
- **A small SPA build step** (esbuild) if the JavaScript grows
  past one file

### What I would not do

- **Rewrite in a different language.** Python is fine.
- **Adopt a front-end framework.** The interactivity is
  minimal.
- **Move to a "headless" architecture.** Server-rendered HTML
  is a feature, not a bug.
- **Adopt a microservices setup.** This is a single-user
  product.

### TL;DR

The current stack is **about 80% right**. The 20% that needs
attention is operational hygiene: migrations, CSRF, rate
limiting, env-driven config. Once those are in, the stack will
scale comfortably to thousands of users on a single Railway
instance. The day it doesn't is the day you'd reach for a
managed Postgres, a CDN, and a Redis cache — but that day is
not today.

---

## 9. Recommended Next Steps

Ordered roughly by ROI-per-effort:

1. **Move `secret_key` to an env var** (S1). 5 minutes.
2. **Add `SESSION_COOKIE_SECURE` / `HTTPONLY` / `SAMESITE`** (S5).
   5 minutes.
3. **Make `/logout` a `POST`** (S2). 30 minutes, including the
   form change in `base.html`.
4. **Add Flask-Migrate** (B3). 1 hour, plus generating the
   initial migration.
5. **Add Flask-Limiter** (S4). 30 minutes for the login route.
6. **Add `CHECK` constraint on `category`** (S7/D3). 5 minutes,
   one SQL line.
7. **Add a server-side cap on `amount`** (B8). 10 minutes.
8. **Index `(user_id, date)` on `expenses`** (D2). 1 line of
   SQL.
9. **Implement a `Config` class** (hygiene). 30 minutes.
10. **Adopt Flask-WTF** for CSRF + form validation (S3). 1–2
    hours, including template updates.
11. **Pagination on `/profile`** (U2). 1 hour.
12. **Cache the profile aggregates** (P1). 1–2 hours.
13. **Tests for auth, queries, seeds** (C2/T1–T3). 1 day.
14. **A custom delete-confirmation modal** (U4). 1–2 hours.

If the team is small, focus on items 1–6 first — they are the
ones that protect the production deployment. The rest is
polish.

---

*End of analysis-review.md*
