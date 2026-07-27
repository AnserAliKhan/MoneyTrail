import pytest
from flask import Flask

# Importing `app` once at module-load time runs app.py's top-level
# `init_db(app)` and `seed_db()` against the dev `expense_tracker.db`,
# which is fine — those functions are idempotent and the dev DB lives
# outside this conftest's scope. What we CAN'T do is call `init_db`
# again on that same Flask instance, because Flask locks
# `teardown_appcontext` registration after the first request.
#
# So the fixtures below build a *fresh* Flask instance per test that
# re-uses the already-imported route handlers (and helper functions)
# by copying them from the dev `app` onto a new instance. The new
# instance gets its own tmp-path SQLite DB, so tests are isolated.

import app as _app_module
from database.db import init_db, seed_db


def _build_fresh_app(db_path: str) -> Flask:
    """Create a new Flask instance mirroring the dev app's config and routes.

    Re-registers every view function and the `_login_required` /
    `_redirect_if_authenticated` decorators on the new instance, then
    points the new app at `db_path` via `init_db` + `seed_db`.
    """
    new_app = Flask(
        _app_module.app.import_name,
        template_folder=_app_module.app.template_folder,
        static_folder=_app_module.app.static_folder,
    )
    new_app.secret_key = _app_module.app.secret_key
    new_app.config["TESTING"] = True
    new_app.config["DATABASE"] = db_path

    # Re-register every view the dev app has by name. `add_url_rule`
    # only needs the rule + endpoint + view function — no need to
    # re-apply decorators, they're already on the function objects.
    for rule in _app_module.app.url_map.iter_rules():
        if rule.endpoint == "static":
            continue
        view = _app_module.app.view_functions[rule.endpoint]
        new_app.add_url_rule(
            str(rule),
            endpoint=rule.endpoint,
            view_func=view,
            methods=list(rule.methods - {"HEAD", "OPTIONS"}),
        )

    with new_app.app_context():
        init_db(new_app)
        seed_db()
    return new_app


@pytest.fixture
def app(tmp_path):
    db_path = str(tmp_path / "test.db")
    fresh = _build_fresh_app(db_path)
    yield fresh
    # No explicit teardown needed — pytest's tmp_path cleanup removes
    # the SQLite file; the in-memory app is garbage-collected.


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def auth_client(client):
    client.post("/login", data={"email": "demo@spendly.com", "password": "demo123"})
    return client
