# MoneyTrail — How It All Works

> A non-technical walk-through of the MoneyTrail expense tracker. This document
> traces how the project was built, step by step, and explains how every piece
> fits together to produce a working personal-finance web app. It is written
> so that someone with no programming background can read it end-to-end and
> walk away with a complete mental model of the system.

---

## Table of Contents

1. [What MoneyTrail Is](#1-what-moneytrail-is)
2. [The Big Picture: How a Web App Works](#2-the-big-picture-how-a-web-app-works)
3. [The Tech Stack (In Plain English)](#3-the-tech-stack-in-plain-english)
4. [The Folder Layout](#4-the-folder-layout)
5. [The Development Timeline](#5-the-development-timeline)
6. [Feature Deep Dives](#6-feature-deep-dives)
7. [How Data Flows Through the App](#7-how-data-flows-through-the-app)
8. [Security, Sessions, and CSRF](#8-security-sessions-and-csrf)
9. [How the App Is Tested](#9-how-the-app-is-tested)
10. [Running It Yourself](#10-running-it-yourself)
11. [Glossary](#11-glossary)

---

## 1. What MoneyTrail Is

MoneyTrail is a small web application that lets a person:

- **Create an account** with their name, email, and password.
- **Log expenses** — every rupee they spend, tagged with a category
  (Food, Transport, Bills, Health, Entertainment, Shopping, Other), a date,
  and an optional note.
- **See their spending** visualised on a personal profile page: total
  spent, number of transactions, top category, a category breakdown, and
  a doughnut chart.
- **Filter** the profile page by preset ranges (this month, last month,
  last 7 days, last 30 days) or by any custom date range they choose.
- **Edit or delete** any expense they have previously logged.

Visually, the app is dressed in a "paper / cream / forest-green" palette
branded as **MoneyTrail**, and the entire UI is designed to feel calm and
uncluttered — closer to a notebook than to a spreadsheet.

---

## 2. The Big Picture: How a Web App Works

If you've never seen a web app from the inside, here's the simplest model:

1. **You** (the user) open a browser and visit a URL like `http://localhost:5001/`.
2. **Your browser** sends a *request* — a tiny, structured message — to a
   program running on a computer called a *server*.
3. **The server** (in our case, a Python program called Flask) receives
   the request, decides what to do with it, and produces a *response*.
4. The response — usually a page of HTML, CSS, and JavaScript — is sent
   back to your browser, which renders it as the page you see.

The whole of MoneyTrail is one such program. Every page (the marketing
homepage, the login form, your profile, etc.) is what the server *decides*
to send back when it receives a request for a particular URL.

The server doesn't just send the same page to everyone. When you log in,
the server knows who you are, and when you ask to see your profile, it
looks up *your* expenses specifically.

---

## 3. The Tech Stack (In Plain English)

A "tech stack" is just the set of tools used to build something. For
MoneyTrail, every tool is small and well-known:

| Layer            | Tool                  | What it does, in human terms                                                           |
|------------------|-----------------------|----------------------------------------------------------------------------------------|
| Language         | **Python 3**          | The programming language the server is written in.                                     |
| Web framework    | **Flask 3.1.3**       | A library that handles the boring parts of web requests and responses.                 |
| Web helpers      | **Werkzeug 3.1.6**    | Bundled with Flask; provides password hashing utilities.                               |
| Database         | **SQLite**            | A single-file database — no separate server to install. One `.db` file = the database. |
| Templates        | **Jinja2**            | The template language Flask uses to mix data into HTML pages.                          |
| Styling          | **Hand-written CSS**  | One file (`static/css/style.css`) defines the entire visual identity.                  |
| Fonts            | **DM Serif Display / DM Sans** (Google Fonts) | Two typefaces that give the app its "calm notebook" feel.              |
| Icons            | **Lucide**            | A small icon set loaded from a public CDN, used for arrows, charts, shields, etc.     |
| Charts           | **Chart.js** (CDN)    | A JavaScript library that draws the doughnut chart on the profile page.                |
| Testing          | **pytest + pytest-flask** | Two libraries that let us run automated tests against the app.                      |
| Deployment       | **Railway**           | A cloud platform that re-builds and re-deploys the app whenever code is pushed.        |

There is **no front-end framework** like React or Vue. Every page is
rendered server-side — Flask builds the HTML, the browser just displays it.
The only JavaScript on most pages is small and self-contained: a video
modal on the homepage, a "preset preview" nicety on the profile page, and
the doughnut chart.

---

## 4. The Folder Layout

```
expense-tracker/
├── app.py                      # The whole Flask application: routes + helpers
├── CLAUDE.md                   # Project-level notes for the AI assistant
├── requirements.txt            # The four Python libraries the app needs
├── seed_user.py                # Helper script: create one fake Indian user
├── seed_expenses.py            # Helper script: create fake expenses for a user
├── .gitignore                  # Tells git which files to skip (db, venv, etc.)
│
├── database/
│   ├── __init__.py             # Empty (makes the folder a Python package)
│   ├── db.py                   # Schema, connection helpers, demo-data seeding
│   └── queries.py              # Reusable query functions (insert/get/update/delete)
│
├── templates/                  # HTML pages (Jinja2 templates)
│   ├── base.html               # Layout: navbar, footer, design tokens, blocks
│   ├── landing.html            # Marketing home page
│   ├── login.html              # Sign-in form
│   ├── register.html           # Create-account form
│   ├── profile.html            # The user's personal dashboard
│   ├── dashboard.html          # A minimal "you are signed in" placeholder
│   ├── analytics.html          # A "coming soon" placeholder
│   ├── terms.html              # Terms of Use (final copy, do not regenerate)
│   ├── privacy.html            # Privacy Policy (final copy, do not regenerate)
│   └── expenses/
│       ├── add.html            # Form to log a new expense
│       └── edit.html           # Form to edit an existing expense
│
├── static/                     # Files served to the browser as-is
│   ├── css/style.css           # The single stylesheet
│   ├── js/main.js              # Placeholder for future page scripts
│   └── img/                    # Hero illustration + a Figma reference image
│
├── tests/                      # Automated tests
│   ├── conftest.py             # Shared fixtures: test app, client, auth client
│   ├── test_06-date-filter.py  # Tests for the date-filter feature
│   └── test_07_add_expense.py  # Tests for the add-expense feature
│
└── expense_tracker.db          # The SQLite database file (gitignored)
```

A few notes that often confuse newcomers:

- **Templates** are HTML files with extra syntax (`{% ... %}`, `{{ ... }}`)
  that lets Flask inject real data into them at request time. For example,
  `{{ user["name"] }}` becomes your actual name when the page is rendered.
- **Static** files are served without any modification. The browser
  downloads the CSS exactly as it lives on disk.
- **The `database/` folder is a Python package** — that's why it has an
  `__init__.py` (even though that file is empty). It lets us write
  `from database.db import get_db`.

---

## 5. The Development Timeline

The repository's git history is a clean record of how the project grew
from a single empty commit to a working app. Reading it top-to-bottom
(earliest to latest) is a great way to understand the order in which
features were layered on.

> Reading the project this way matters because each commit was a
> small, reviewable unit of work. There were no "big bang" merges.

### Phase 0 — Landing the Project (early commits)

| Commit         | What it added                                                                                                  |
|----------------|----------------------------------------------------------------------------------------------------------------|
| `Initial commit` | The first empty version of the repo — just a folder structure.                                              |
| `landing page:privacy and TC links added` | The first marketing page, plus a placeholder for legal pages.                        |
| `added privacy policy page and route`     | The Privacy Policy page was wired up at `/privacy`.                                 |
| `landing page refined` + `youtube link added` | The hero got a "See how it works" button that opens a YouTube modal.              |

At this point the app was a single-page marketing site with a legal
disclaimer or two. There was no database, no login, no expenses — just
a styled front door.

### Phase 1 — Database (Step 1: `feature/database-setup`)

The first real engineering step. Two files were added under `database/`:

- **`database/db.py`** — declares the SQL schema, opens SQLite
  connections, and seeds one demo user plus 8 sample expenses.
- **`database/queries.py`** — small reusable functions for inserting,
  fetching, updating, and deleting expenses.

This is the moment the app became "stateful." Before this commit, every
page reset on refresh; after it, the app had a memory.

### Phase 2 — Registration (Step 2: `feature/registration`)

A new user can now sign up:

- The `/register` route was given a real handler that accepts `POST`
  requests, validates the input (name + valid email + password of
  at least 8 characters), hashes the password, and inserts the new user.
- The `register.html` template was already wired to POST to `/register`
  — the backend catching up to the front end.

### Phase 3 — Login & Logout (Step 3: `feature/login-logout`)

With users in the database, the next step was letting them sign in:

- `/login` got a real POST handler that looks up the user by email and
  verifies the password (using `werkzeug.security.check_password_hash`).
- On success, the server stores the user's id in a **session** — a small
  piece of data that the browser sends back with every request, so the
  server can recognise the user across pages.
- `/logout` was wired up: it just clears the session.

The `_login_required` decorator was introduced here too. It's a tiny
piece of code that says "if no one is signed in, redirect to /login."
It sits on top of every protected route (profile, dashboard, etc.) so
that the same check doesn't have to be repeated.

### Phase 4 — Profile Page UI (Step 4: `feature/profile-page-design`)

A big visual step. A new `profile.html` template was added with a clean
header showing the user's initials, name, email, and member-since date,
plus a placeholder for the stats that would come next.

### Phase 5 — Profile Page Backend + Charts (Step 5: `feature/backend-routes-profile-page`)

The "coming soon" sections of the profile page were filled in:

- The `/profile` route learned to read the signed-in user's expenses from
  the database, sum them, count them, find the top category, and group
  by category.
- A doughnut chart powered by Chart.js was wired up, drawing on the
  browser using the per-category totals.
- The `Modification to profile page charts` commit tidied the rendering.

### Phase 6 — Date Filter (Step 6: `feature/date-filter`)

The user can now narrow their profile page to a specific date range:

- A filter bar was added with five preset pills (All time, This month,
  Last month, Last 7 days, Last 30 days) and two date inputs (From / To).
- The `/profile` route learned to read the filter from the query string
  and apply the bounds uniformly to every database query it ran.
- A small JavaScript nicety fills the date inputs with the preset's
  window so users see what they are about to filter to. (The page still
  works without JavaScript — the buttons are real form submits.)

This commit also came with its own test file,
`tests/test_06-date-filter.py`.

### Phase 7 — Add Expense (Step 7: `feature/add-expense`)

Until this step, the only way to put an expense into the database was
to run a seed script. The user can now do it themselves:

- A new `/expenses/add` route was added (GET shows the form, POST
  saves the expense).
- A new template, `templates/expenses/add.html`, was added with a clean
  four-field form.
- The form is **CSRF-protected** — the server generates a one-time
  token when it renders the form and checks it again on submission, so
  a malicious site can't trick the user's browser into submitting it.
- The corresponding test file, `tests/test_07_add_expense.py`, was added.

### Phase 8 — Edit Expense (Step 8: `feature/edit-expense`)

The same shape, but for editing:

- A new `/expenses/<id>/edit` route was added.
- The form lives in `templates/expenses/edit.html` and is pre-populated
  with the existing values.
- Only the owner of an expense can edit it — the query is scoped by
  `user_id`, so a forged URL with someone else's expense id will return
  404.

### Phase 9 — Delete Expense (Step 9: `feature/delete-expense`)

A small but essential step:

- A new `/expenses/<id>/delete` route was added (POST only — deletes
  are never triggered by a casual link click).
- The "All Expenses" table on the profile page got Edit / Delete actions.
- Ownership is enforced the same way as for edits.

### Phase 10 — Rebrand to MoneyTrail (`feature/10-ui-rebrand`)

The app's name was changed from "Spendly" to "MoneyTrail" and the colour
palette was switched from forest green + amber to a more distinctive
"deep blue + gold" combination.

- All visible references to "Spendly" were renamed.
- The CSS design tokens at the top of `style.css` were updated to the new
  palette.
- Marketing copy was re-tuned.
- The `terms.html` and `privacy.html` files already said "MoneyTrail"
  (the legal copy was authored under the new name from the start), so
  this commit made the rest of the app match.

### Phase 11 — Deployment trigger

The most recent commit, `f6023ed trigger railway redeploy`, is a single
no-op change made to nudge the Railway cloud platform into rebuilding
and re-deploying the live site. This is the operational counterpart to
the actual development work — the way a finished feature gets to a
public URL.

---

## 6. Feature Deep Dives

Now that you've seen *when* each feature was added, here's *how* each one
works internally.

### 6.1 Account Registration

1. The user visits `/register`. Flask renders `register.html` with a
   three-field form (name, email, password).
2. The user fills the form and clicks "Create account." The browser
   submits a POST to `/register`.
3. The server runs `_validate_registration(name, email, password)`,
   which checks:
   - name is not empty,
   - email contains `@` and a dot after it,
   - password is at least 8 characters.
4. If anything is missing, the same form is re-rendered with an error
   message above the fields.
5. If everything checks out, the password is hashed using
   `werkzeug.security.generate_password_hash` (so the database never
   sees the real password), and a new row is inserted into the `users`
   table.
6. If the email is already taken, SQLite raises an `IntegrityError`
   (because the column is `UNIQUE`); the server catches that and shows
   a friendly "An account with that email already exists." error.
7. On success, the user is redirected to `/login`.

### 6.2 Login & Logout

1. The user submits the login form. The server looks up the row by
   email.
2. If a row is found, the server calls
   `werkzeug.security.check_password_hash(stored, given)`. **Notice**
   that the same generic error message is shown for both "no such user"
   and "wrong password" — that way a stranger cannot probe the database
   to find out which emails are registered.
3. On success, the server writes `user_id` and `user_name` into the
   **session**. The session is a Flask concept: a small signed cookie
   stored in the browser. Every subsequent request carries it, so the
   server can identify the user without re-asking for a password.
4. The user is redirected to `/profile` (the dashboard).
5. `/logout` simply clears the session and redirects to the landing page.

### 6.3 The Profile Page

The profile page is the centre of the user experience. It does several
things in one trip to the server:

1. **Parse the date filter** from the URL (`?preset=...`, `?from=...`,
   `?to=...`). Unknown or empty values fall back to "no filter."
2. **Validate** the dates — bad inputs are recorded as errors, and
   the page falls back to an unfiltered view rather than crashing.
3. **Look up the user** by id to show their name, email, and
   member-since date.
4. **Run four SQL queries** against the `expenses` table, all scoped to
   the current `user_id` and (if a filter is set) the date range:
   - `SUM(amount)` for the total spent,
   - `COUNT(*)` for the number of transactions,
   - `SUM(amount) GROUP BY category ORDER BY total DESC LIMIT 1` for the
     top category,
   - `SUM(amount) GROUP BY category` for the full breakdown.
5. **Render** the page with the four pieces of data, a "Spending by
   category" table, an "All Expenses" table with Edit / Delete actions,
   and a doughnut chart drawn by Chart.js.

The doughnut chart is the only thing on the page that is rendered by
JavaScript rather than Flask. Flask serialises the per-category data
into a JSON blob inside the page; Chart.js then takes that and draws.

### 6.4 Date Filter

The filter bar is intentionally a plain HTML `<form method="get">` —
it has no JavaScript dependency. The five preset pills are real submit
buttons that include their preset name in the form data; clicking one
navigates to a URL like `/profile?preset=last-7-days`.

Behind the scenes:

- **Preset resolution** (`_resolve_preset`) expands a preset name into
  a `(from, to)` date pair using today's date.
- **Explicit dates** typed into the From/To inputs win over the preset
  if both are supplied.
- **Reversed-range guard** — if `from > to`, the server falls back to
  no filter and shows a friendly error, instead of returning 0 results
  silently.
- **Malformed dates** — instead of crashing, the server records the
  error and falls back gracefully.

The filter is **applied uniformly** to every expenses query. That means
the "Total spent" tile, the "Top category" tile, the category breakdown
table, the expense list, and the chart all reflect the same window.

### 6.5 Add Expense

1. The user visits `/expenses/add`. The server generates a one-time
   CSRF token and stores it in the session, then renders the form.
2. The user fills the form (amount, category, date, optional note)
   and clicks "Save Expense."
3. The server checks the CSRF token. If it doesn't match, the request
   is rejected with a 403 — a defence against cross-site request
   forgery, where a malicious site could trick the user's browser
   into submitting the form on their behalf.
4. The server validates the input: amount must be a positive number,
   category must be from the fixed list, date must be a real date in
   `YYYY-MM-DD` format.
5. If anything is invalid, the form is re-rendered with the user's
   previous values still filled in and an error message at the top.
6. If everything is valid, the server calls `insert_expense` from
   `database/queries.py` to save the row, then redirects to
   `/profile`.

### 6.6 Edit & Delete Expense

Both work the same way as Add, with the same CSRF and validation
rules, plus an **ownership check**: the query always includes
`AND user_id = ?`. A user can only ever see and modify their own
expenses, even if they craft a URL with someone else's expense id
in it.

### 6.7 The Coming-Soon Pages

`/dashboard` and `/analytics` are intentionally minimal:

- `/dashboard` is a small "Welcome, you are signed in" card with a
  Sign-out button. It's kept around for the original "first version of
  the user's home" idea.
- `/analytics` is a polished "Coming Soon" page describing the future
  feature (spending trends, month comparison, budget goals). The
  routing, layout, and copy are all in place; the analytics logic is
  what will come next.

### 6.8 Landing Page & Marketing

The landing page (`/`) is a single long, scrollable marketing page
with these sections, in order:

- **Hero** — headline, sub-headline, two buttons (Start tracking /
  See how it works), and a Figma-style dashboard preview.
- **Stat band** — three numbers ("50K+ users," "₨2M+ tracked monthly,"
  "4.9 ★") as social proof.
- **Features** — a 4-card grid (log in seconds, see the patterns,
  filter by period, private & secure).
- **Three steps** — sign up, log expenses, watch the picture form.
- **Testimonials** — three short quotes from fictional users.
- **Pricing** — two cards, both "₨0 / forever" (the app is free).
- **Email CTA** — a "subscribe to monthly insights" form.

The "See how it works" link opens a YouTube modal. The iframe uses a
**deferred-load pattern**: the `src` attribute is empty until the user
clicks, then it is set to the YouTube embed URL (with `autoplay=1`).
When the user closes the modal, the `src` is cleared so the video stops
playing — saving bandwidth and avoiding the awkward case of a video
that keeps playing in the background after the modal is closed.

---

## 7. How Data Flows Through the App

Here is a typical round trip — a user named Aisha signs in and adds an
expense.

```
  Browser                              Flask (app.py)                   SQLite
   │                                          │                            │
   │  1. POST /login                          │                            │
   │  ─────────────────────────────────────►  │                            │
   │                                          │  2. SELECT user by email  │
   │                                          │  ─────────────────────►  │
   │                                          │  ◄───── user row ─────    │
   │                                          │  3. verify password       │
   │                                          │  4. session["user_id"]=…  │
   │  5. 302 → /profile                       │                            │
   │  ◄─────────────────────────────────────  │                            │
   │                                          │                            │
   │  6. GET /profile                         │                            │
   │  ─────────────────────────────────────►  │                            │
   │                                          │  7. SELECT expenses       │
   │                                          │     WHERE user_id=…       │
   │                                          │  ─────────────────────►  │
   │                                          │  ◄───── rows ────────    │
   │  8. 200 + profile.html (rendered)        │                            │
   │  ◄─────────────────────────────────────  │                            │
   │                                          │                            │
   │  9. GET /expenses/add                    │                            │
   │  ─────────────────────────────────────►  │                            │
   │  10. 200 + add.html (with CSRF token)    │                            │
   │  ◄─────────────────────────────────────  │                            │
   │                                          │                            │
   │  11. POST /expenses/add (form data)      │                            │
   │  ─────────────────────────────────────►  │                            │
   │                                          │  12. validate input        │
   │                                          │  13. check CSRF            │
   │                                          │  14. INSERT expense        │
   │                                          │  ─────────────────────►  │
   │  15. 302 → /profile                      │                            │
   │  ◄─────────────────────────────────────  │                            │
   │                                          │                            │
   │  16. GET /profile (re-visit)             │                            │
   │  ─────────────────────────────────────►  │                            │
   │  17. updated profile.html                │                            │
   │  ◄─────────────────────────────────────  │                            │
```

Every flow is shaped the same way: a browser request, a server
decision, zero or more database queries, and a response.

---

## 8. Security, Sessions, and CSRF

Because MoneyTrail handles real (if personal) data, several small but
important precautions are in place:

- **Passwords are hashed, not stored.** The `users.password_hash`
  column never holds a real password. When a user signs in, the server
  hashes what they typed and compares the two hashes — the original
  password is never recoverable from the database.
- **Sessions are signed.** Flask signs the session cookie with
  `app.secret_key`. If someone tampers with the cookie, the signature
  no longer matches and the server rejects it. (For a production
  deployment, the secret key should come from an environment variable
  rather than a literal in the code.)
- **CSRF tokens on mutating forms.** Add and Edit both require a
  one-time token that the server generates when it shows the form and
  re-checks on submission. This stops a third-party site from making
  the user's browser submit a form they didn't intend to submit.
- **Ownership checks on expenses.** Every expense query includes
  `AND user_id = ?`, so a user can never see, edit, or delete another
  user's expenses — even by guessing URL ids.
- **The same error message for "no such user" and "wrong password."**
  This prevents an attacker from using the login form to discover
  which emails are registered.
- **`.gitignore` excludes the database file**, the venv folder, and
  any `.env` file. Sensitive material never gets committed by accident.

---

## 9. How the App Is Tested

Two test files live in `tests/`:

- `test_06-date-filter.py` — covers the date filter on the profile
  page: preset behaviour, custom ranges, validation errors, and
  ownership isolation.
- `test_07_add_expense.py` — covers the add-expense feature: auth
  guards, form rendering, valid submissions, and the various
  validation error paths.

A shared `tests/conftest.py` provides three fixtures that every test
uses:

- `app` — builds a brand-new Flask app pointed at a temporary SQLite
  file (so tests don't pollute the dev database).
- `client` — returns a Flask test client (no real network needed).
- `auth_client` — returns a test client that has already signed in as
  the demo user.

The pattern is the same in every test: build a request with the
client, assert on the status code and the response body, and on
behalf-of cases, assert directly against the database that the right
row was inserted.

---

## 10. Running It Yourself

The project ships with a `requirements.txt` listing four libraries.
To run it on your own machine:

```bash
# 1. Create and activate a virtual environment
python -m venv venv
# Windows:
venv\Scripts\activate
# macOS / Linux:
source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Start the dev server
python app.py
```

The server listens on **port 5001**. Visit `http://localhost:5001/`
in your browser. The very first time you do this, a SQLite database
file (`expense_tracker.db`) is created and seeded with one demo user
and 8 sample expenses.

The seeded credentials are:

- **Email:** `demo@spendly.com`
- **Password:** `demo123`

Two helper scripts are also available:

- `python seed_user.py` — adds a fresh fake user (with a plausible
  Indian name and a generated email like `priya.sharma42@gmail.com`).
- `python seed_expenses.py <user_id> <count> <months>` — adds
  realistic expenses for that user. Example:
  `python seed_expenses.py 1 50 6` adds 50 expenses spread over the
  last 6 months.

To run the automated tests:

```bash
pytest
```

---

## 11. Glossary

- **App context** — a Flask concept that makes the active application
  and its configuration available to code. Used here so that the
  database helpers can look up the configured DB path.
- **CSRF (Cross-Site Request Forgery)** — an attack where a malicious
  site tricks a logged-in user's browser into submitting a form to
  your server. A one-time token in the form blocks this.
- **Decorator** — in Python, a function that wraps another function to
  add behaviour. `_login_required` is a decorator; routes can be
  "decorated" with it to add a sign-in check.
- **Doughnut chart** — a circular chart with a hole in the middle.
  Same idea as a pie chart, slightly less aggressive.
- **Foreign key** — a column whose value must match a row in another
  table. `expenses.user_id` is a foreign key to `users.id`, so an
  expense can never exist without a valid owner.
- **Hashing** — a one-way transformation. Easy to compute, hard to
  reverse. Passwords are stored as hashes, not in plain text, so even
  if the database is leaked, the passwords are still protected.
- **Jinja2** — Flask's templating language. Lets you embed `{{ ... }}`
  expressions and `{% ... %}` statements inside HTML.
- **PRAGMA** — a SQLite-specific way of tweaking engine settings.
  `PRAGMA foreign_keys = ON` turns on foreign-key enforcement for the
  current connection.
- **Query string** — the part of a URL after a `?`, like
  `?preset=last-7-days`. The server reads it to know what filter to
  apply.
- **Session** — a small piece of state stored by the server (or, in
  Flask's default case, signed and sent to the browser as a cookie).
  Used here to remember "who is signed in."
- **SQLite** — the simplest kind of relational database. The whole
  database is a single file on disk. Perfect for a small project.
- **Template** — an HTML file with extra syntax that lets Flask
  substitute real data in when the page is rendered.
- **Teardown** — a callback that Flask runs at the end of a request
  (or app context). Here, it closes the per-request database
  connection so connections don't leak.

---

*End of explanation.md — last updated alongside the project as of the
"rebrand to MoneyTrail" commit and the subsequent deployment trigger.*
