import secrets
import sqlite3
import sys
from datetime import date, datetime, timedelta
from functools import wraps

from flask import Flask, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from database.db import CATEGORIES, get_db, init_db, seed_db
from database.queries import insert_expense

app = Flask(__name__)

# Required to sign session cookies. The dev key is fine for local use;
# in production this must come from an environment variable so it isn't
# checked into the repo.
# TODO: replace with env var in production
app.secret_key = "dev-secret-change-me"


# ------------------------------------------------------------------ #
# Database initialization                                              #
# ------------------------------------------------------------------ #

# Ensure the schema exists and the demo data is seeded before the first
# request hits a route. Both functions are idempotent, so this is safe
# on every startup.
with app.app_context():
    init_db(app)
    seed_db()


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

def _validate_registration(name: str, email: str, password: str) -> str | None:
    """Return an error message string, or None if all fields are valid."""
    if not name:
        return "Please enter your name."
    if "@" not in email or "." not in email.split("@")[-1]:
        return "Please enter a valid email address."
    if len(password) < 8:
        return "Password must be at least 8 characters."
    return None


def _login_required(view):
    """Gate a view on a signed-in session.

    Redirects to /login if there is no user_id in the session. The
    functools.wraps preserves the wrapped view's __name__ so Flask's
    url_for() can still resolve the endpoint by name.
    """
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def _redirect_if_authenticated(view):
    """Send already-signed-in users away from the auth pages.

    If a session is present, GET and POST both bounce to the landing
    page. Signed-out users fall through to the wrapped view unchanged.
    """
    @wraps(view)
    def wrapped(*args, **kwargs):
        if session.get("user_id"):
            return redirect(url_for("landing"))
        return view(*args, **kwargs)
    return wrapped


@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
@_redirect_if_authenticated
def register():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""

        error = _validate_registration(name, email, password)
        if error:
            return render_template("register.html", error=error)

        db = get_db()
        try:
            db.execute(
                "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
                (name, email, generate_password_hash(password)),
            )
            db.commit()
        except sqlite3.IntegrityError:
            return render_template("register.html", error="An account with that email already exists.")

        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
@_redirect_if_authenticated
def login():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""

        if not email or not password:
            return render_template("login.html", error="Please enter your email and password.")

        db = get_db()
        row = db.execute(
            "SELECT id, name, password_hash FROM users WHERE email = ?",
            (email,),
        ).fetchone()

        # Single error message for both "no such user" and "wrong password"
        # so we don't leak which accounts exist.
        if row is None or not check_password_hash(row["password_hash"], password):
            return render_template("login.html", error="Invalid email or password.")

        session["user_id"] = row["id"]
        session["user_name"] = row["name"]
        # Returning users land on their profile — see their stats and
        # the category breakdown without bouncing through the marketing
        # page first. The /login GET handler is still gated by
        # _redirect_if_authenticated, so already-signed-in users who
        # hit /login directly still go to / (landing) as before.
        return redirect(url_for("profile"))

    return render_template("login.html")


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/logout")
def logout():
    # Idempotent — clearing an empty session is fine.
    session.clear()
    return redirect(url_for("landing"))


@app.route("/dashboard")
@_login_required
def dashboard():
    return render_template("dashboard.html", user_name=session.get("user_name"))


@app.route("/analytics")
@_login_required
def analytics():
    return render_template("analytics.html")


# ------------------------------------------------------------------ #
# Profile filter helpers                                                #
# ------------------------------------------------------------------ #

# Preset → (label, range-builder). Returning None for both endpoints
# means "no filter applied". `today` is passed in so the function stays
# pure (easier to reason about and trivial to unit-test later).
_PRESETS = {
    "all":         "All time",
    "this-month":  "This month",
    "last-month":  "Last month",
    "last-30-days": "Last 30 days",
    "last-7-days": "Last 7 days",
}


def _resolve_preset(preset: str, today: date) -> tuple[date | None, date | None]:
    """Expand a preset name to a (from, to) date pair.

    Unknown / empty presets fall back to (None, None) — i.e. no filter.
    """
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
    # "all" and anything unknown → unbounded
    return (None, None)


def _parse_iso_date(raw: str, errors: list[str], field: str) -> date | None:
    """Parse a YYYY-MM-DD string. On ValueError, append to errors and return None.

    Empty / whitespace strings return None without appending — those mean
    "this side is unbounded", which is a valid state.
    """
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        errors.append(f"{field}: '{raw}' is not a valid YYYY-MM-DD date.")
        return None


def _date_bounds(from_date: date | None, to_date: date | None) -> tuple[str, list[str]]:
    """Build the `AND date ...` fragment + bound params for a WHERE clause.

    SQLite text-comparison on ISO `YYYY-MM-DD` strings is correct, so
    `>=` and `<=` work without any conversion.
    """
    clauses: list[str] = []
    params: list[str] = []
    if from_date is not None:
        clauses.append("date >= ?")
        params.append(from_date.isoformat())
    if to_date is not None:
        clauses.append("date <= ?")
        params.append(to_date.isoformat())
    return (" AND ".join(clauses), params)


def _first_of_month(d: date) -> date:
    return d.replace(day=1)


@app.route("/profile")
@_login_required
def profile():
    # ----- Parse & validate the date filter from the query string -----
    # Preset shortcuts expand to a (from, to) pair; explicit from/to win
    # over the preset so the "Apply" button doesn't need to clear it.
    raw_preset = (request.args.get("preset") or "all").strip()
    raw_from = (request.args.get("from") or "").strip()
    raw_to = (request.args.get("to") or "").strip()

    errors: list[str] = []
    explicit_from = _parse_iso_date(raw_from, errors, "From")
    explicit_to = _parse_iso_date(raw_to, errors, "To")

    # Preset contributes defaults for whichever side the user left blank.
    today = date.today()
    preset_from, preset_to = _resolve_preset(raw_preset, today)

    from_date = explicit_from if explicit_from is not None else preset_from
    to_date = explicit_to if explicit_to is not None else preset_to

    # Reversed-range guard. We catch this before running any queries so
    # the user gets feedback and the page falls back to no filter.
    if from_date is not None and to_date is not None and from_date > to_date:
        from_date = None
        to_date = None
        errors.append("Start date must be on or before end date.")

    filter_error = errors[0] if errors else None

    # `active_preset` drives which pill is highlighted in the filter bar.
    # "custom" means the user submitted explicit from/to — neither a
    # preset button nor the empty state is highlighted; the date inputs
    # carry the active-state hint instead.
    if raw_from or raw_to:
        active_preset = "custom"
    elif raw_preset in _PRESETS and raw_preset != "all":
        active_preset = raw_preset
    else:
        active_preset = "all"

    # ----- Apply the bounds uniformly to every expenses query -----
    bounds_sql, bounds_params = _date_bounds(from_date, to_date)
    # Always AND with at least an empty string so the final SQL stays
    # valid even when no bounds are set.
    where_suffix = f" AND {bounds_sql}" if bounds_sql else ""
    user_id = session["user_id"]
    user_params = (user_id, *bounds_params)

    db = get_db()
    user = db.execute(
        "SELECT id, name, email, created_at FROM users WHERE id = ?",
        (session["user_id"],),
    ).fetchone()

    total_row = db.execute(
        f"SELECT COALESCE(SUM(amount), 0) AS total FROM expenses "
        f"WHERE user_id = ?{where_suffix}",
        user_params,
    ).fetchone()
    total_spent = total_row["total"]

    tx_count = db.execute(
        f"SELECT COUNT(*) AS n FROM expenses WHERE user_id = ?{where_suffix}",
        user_params,
    ).fetchone()["n"]

    top_row = db.execute(
        f"SELECT category, SUM(amount) AS total FROM expenses "
        f"WHERE user_id = ?{where_suffix} "
        f"GROUP BY category ORDER BY total DESC LIMIT 1",
        user_params,
    ).fetchone()
    top_category = top_row["category"] if top_row else None

    # Per-category breakdown for the "Spending by category" table on
    # the profile page. Same shape as the top-category query but without
    # LIMIT 1, so we can show every category the user has spent in.
    # Returns an empty list for a user with no expenses — the template
    # renders the empty-state copy in that case.
    category_rows = db.execute(
        f"SELECT category, SUM(amount) AS total FROM expenses "
        f"WHERE user_id = ?{where_suffix} "
        f"GROUP BY category ORDER BY total DESC",
        user_params,
    ).fetchall()

    # Individual expenses for the detailed table with descriptions
    expense_rows = db.execute(
        f"SELECT id, amount, category, date, description FROM expenses "
        f"WHERE user_id = ?{where_suffix} "
        f"ORDER BY date DESC",
        user_params,
    ).fetchall()

    # Convert sqlite3.Row objects to dicts so they can be JSON-serialized
    # for the Chart.js pie chart in the template.
    category_rows = [dict(row) for row in category_rows]

    # Format total as ₨X,XXX.XX (Pakistani rupee, two decimals, thousands separator).
    formatted_total = f"₨{total_spent:,.2f}"

    # Initials for the avatar: first char of each of the first two
    # whitespace-separated words, uppercased. Falls back to "?" for
    # whitespace-only or empty names (defensive — the registration
    # validator already rejects empty names).
    parts = (user["name"] or "").split()
    initials = "".join(p[0] for p in parts[:2]).upper() or "?"

    # Format member-since as e.g. "18 July 2026". SQLite stores it as
    # "YYYY-MM-DD HH:MM:SS" (datetime('now')). Falls back to the raw prefix
    # if parsing fails (shouldn't, but defensive).
    member_since = "—"
    if user["created_at"]:
        try:
            parsed = datetime.strptime(user["created_at"], "%Y-%m-%d %H:%M:%S")
            # %-d is Unix-only; %#d is the Windows equivalent. We branch on
            # the platform rather than using strftime()-with-strip, which is
            # less readable.
            day_fmt = "%#d" if sys.platform.startswith("win") else "%-d"
            member_since = parsed.strftime(f"{day_fmt} %B %Y")
        except ValueError:
            member_since = user["created_at"][:10]

    return render_template(
        "profile.html",
        user=user,
        total_spent=total_spent,
        formatted_total=formatted_total,
        tx_count=tx_count,
        top_category=top_category,
        member_since=member_since,
        initials=initials,
        category_rows=category_rows,
        expense_rows=expense_rows,
        active_preset=active_preset,
        from_value=raw_from,
        to_value=raw_to,
        filter_error=filter_error,
        filter_active=active_preset != "all",
        presets=_PRESETS,
        # Echoed back into the optional JS so the preset-preview nicety
        # can populate the date inputs without a roundtrip.
        preset_ranges={
            "all":          (None, None),
            "this-month":   (_first_of_month(today).isoformat(), today.isoformat()),
            "last-month":   (
                _first_of_month(_first_of_month(today) - timedelta(days=1)).isoformat(),
                (_first_of_month(today) - timedelta(days=1)).isoformat(),
            ),
            "last-30-days": ((today - timedelta(days=29)).isoformat(), today.isoformat()),
            "last-7-days":  ((today - timedelta(days=6)).isoformat(), today.isoformat()),
        },
    )


@app.route("/expenses/add", methods=["GET", "POST"])
@_login_required
def add_expense():
    """Add a new expense - GET shows form, POST processes submission."""
    if request.method == "POST":
        # Validate CSRF token
        submitted_token = request.form.get("csrf_token")
        stored_token = session.get("csrf_token")
        if not submitted_token or submitted_token != stored_token:
            return "CSRF token validation failed", 403

        # Get and validate form data
        amount_raw = (request.form.get("amount") or "").strip()
        category = (request.form.get("category") or "").strip()
        date_raw = (request.form.get("date") or "").strip()
        description = (request.form.get("description") or "").strip()

        errors = []

        # Validate amount - must be a positive number
        try:
            amount = float(amount_raw)
            if amount <= 0:
                errors.append("Amount must be greater than zero.")
        except ValueError:
            errors.append("Please enter a valid amount.")

        # Validate category - must be from the fixed list
        if not category:
            errors.append("Please select a category.")
        elif category not in CATEGORIES:
            errors.append("Invalid category selected.")

        # Validate date - must be valid YYYY-MM-DD
        expense_date = None
        if not date_raw:
            errors.append("Please select a date.")
        else:
            try:
                expense_date = datetime.strptime(date_raw, "%Y-%m-%d").date()
            except ValueError:
                errors.append("Please enter a valid date in YYYY-MM-DD format.")

        # If there are errors, re-render the form
        if errors:
            return render_template(
                "expenses/add.html",
                error="; ".join(errors),
                amount=amount_raw,
                category=category,
                date=date_raw,
                description=description,
                today=date.today().isoformat(),
                categories=CATEGORIES,
            )

        # All valid - insert the expense with error handling
        try:
            insert_expense(
                user_id=session["user_id"],
                amount=amount,
                category=category,
                date=expense_date.isoformat(),
                description=description,
            )
        except Exception:
            return render_template(
                "expenses/add.html",
                error="Failed to save expense. Please try again.",
                amount=amount_raw,
                category=category,
                date=date_raw,
                description=description,
                today=date.today().isoformat(),
                categories=CATEGORIES,
            )

        return redirect(url_for("profile"))

    # GET request - generate CSRF token and show the form
    session["csrf_token"] = secrets.token_hex(16)
    return render_template(
        "expenses/add.html",
        today=date.today().isoformat(),
        categories=CATEGORIES,
    )


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    app.run(debug=True, port=5001)
