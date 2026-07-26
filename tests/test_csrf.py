"""
Tests for flashk_util.csrf: double-submit-cookie CSRF protection.

Important: `csrf.py`'s `_csrf_protect` before_request hook explicitly no-ops
when `app.config["TESTING"]` is truthy ("This simplifies unit testing,
wherein CSRF seems to break."). So, unlike most other test files in this
suite, tests here that need CSRF enforcement to actually run build their own
Flask app with TESTING=False (and DEBUG=False, so unhandled exceptions
become 500 responses via the test client instead of propagating).
"""

import pytest
from flask import Flask

import flashk_util.csrf as csrf_mod


@pytest.fixture(autouse=True)
def _reset_exempt_views():
    """`_exemptViews` is a module-level list shared across the whole process.
    Clear it around each test so csrf_exempt registrations from one test
    can't leak into another (defensive; identity-based membership already
    makes this unlikely to matter across freshly-defined view functions,
    but keeps things deterministic)."""
    csrf_mod._exemptViews.clear()
    yield
    csrf_mod._exemptViews.clear()


def _make_app(**config):
    app = Flask(__name__)
    app.config.update(SECRET_KEY="test", TESTING=False, DEBUG=False)
    app.config.update(config)
    return app


def test_csrf_exempt_registers_and_returns_view_unchanged():
    def my_view():
        return "ok"

    result = csrf_mod.csrf_exempt(my_view)

    assert result is my_view
    assert my_view in csrf_mod._exemptViews


def test_get_request_succeeds_without_token_and_sets_cookie():
    app = _make_app()
    csrf_mod.csrf(app)

    @app.route("/data")
    def data():
        return "hello"

    client = app.test_client()
    resp = client.get("/data")

    assert resp.status_code == 200
    assert "CSRF-TOKEN" in resp.headers.get("Set-Cookie", "")


def test_post_without_token_is_rejected_with_400():
    app = _make_app()
    csrf_mod.csrf(app)

    @app.route("/submit", methods=["POST"])
    def submit():
        return "submitted"

    client = app.test_client()
    resp = client.post("/submit")

    assert resp.status_code == 400


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
def test_mutating_methods_all_require_csrf(method):
    app = _make_app()
    csrf_mod.csrf(app)

    @app.route("/submit", methods=["POST", "PUT", "PATCH", "DELETE"])
    def submit():
        return "submitted"

    client = app.test_client()
    resp = client.open("/submit", method=method)

    assert resp.status_code == 400


def test_post_with_matching_cookie_and_header_succeeds():
    app = _make_app()
    csrf_mod.csrf(app)

    @app.route("/data")
    def data():
        return "hello"

    @app.route("/submit", methods=["POST"])
    def submit():
        return "submitted"

    client = app.test_client()

    get_resp = client.get("/data")
    token = get_resp.headers.get("Set-Cookie").split("CSRF-TOKEN=")[1].split(";")[0]

    post_resp = client.post("/submit", headers={"CSRF-TOKEN": token})
    assert post_resp.status_code == 200
    assert post_resp.data == b"submitted"


def test_post_with_matching_cookie_and_x_prefixed_header_succeeds():
    app = _make_app()
    csrf_mod.csrf(app)

    @app.route("/data")
    def data():
        return "hello"

    @app.route("/submit", methods=["POST"])
    def submit():
        return "submitted"

    client = app.test_client()
    get_resp = client.get("/data")
    token = get_resp.headers.get("Set-Cookie").split("CSRF-TOKEN=")[1].split(";")[0]

    post_resp = client.post("/submit", headers={"X-CSRF-TOKEN": token})
    assert post_resp.status_code == 200


def test_post_with_matching_cookie_and_form_field_succeeds_without_header():
    app = _make_app()
    csrf_mod.csrf(app)

    @app.route("/data")
    def data():
        return "hello"

    @app.route("/submit", methods=["POST"])
    def submit():
        return "submitted"

    client = app.test_client()
    get_resp = client.get("/data")
    token = get_resp.headers.get("Set-Cookie").split("CSRF-TOKEN=")[1].split(";")[0]

    post_resp = client.post("/submit", data={"CSRF-TOKEN": token})
    assert post_resp.status_code == 200


def test_post_with_mismatched_cookie_and_header_is_rejected():
    app = _make_app()
    csrf_mod.csrf(app)

    @app.route("/data")
    def data():
        return "hello"

    @app.route("/submit", methods=["POST"])
    def submit():
        return "submitted"

    client = app.test_client()
    client.get("/data")  # sets a cookie

    post_resp = client.post("/submit", headers={"CSRF-TOKEN": "totally-different-value"})
    assert post_resp.status_code == 400


def test_csrf_exempt_view_bypasses_protection_entirely():
    app = _make_app()
    csrf_mod.csrf(app)

    @app.route("/exempt-submit", methods=["POST"])
    @csrf_mod.csrf_exempt
    def exempt_submit():
        return "submitted"

    client = app.test_client()
    resp = client.post("/exempt-submit")

    assert resp.status_code == 200
    assert resp.data == b"submitted"


def test_valid_internal_credentials_bypass_csrf():
    app = _make_app(INTERNAL_USERNAME="svc-user", INTERNAL_PASSWORD="svc-pass")
    csrf_mod.csrf(app)

    @app.route("/submit", methods=["POST"])
    def submit():
        return "submitted"

    client = app.test_client()
    resp = client.post("/submit?apiUsername=svc-user&apiPassword=svc-pass")

    assert resp.status_code == 200


def test_invalid_internal_credentials_still_rejected():
    app = _make_app(INTERNAL_USERNAME="svc-user", INTERNAL_PASSWORD="svc-pass")
    csrf_mod.csrf(app)

    @app.route("/submit", methods=["POST"])
    def submit():
        return "submitted"

    client = app.test_client()
    resp = client.post("/submit?apiUsername=svc-user&apiPassword=wrong-pass")

    assert resp.status_code == 400


def test_no_internal_credentials_configured_means_query_params_never_bypass():
    # INTERNAL_USERNAME/PASSWORD default to "" -- request_has_valid_credentials
    # short-circuits to False whenever either is falsy, so even a request
    # that happens to pass matching empty-string query params can't bypass.
    app = _make_app()
    csrf_mod.csrf(app)

    @app.route("/submit", methods=["POST"])
    def submit():
        return "submitted"

    client = app.test_client()
    resp = client.post("/submit?apiUsername=&apiPassword=")

    assert resp.status_code == 400


def test_preexisting_cookie_value_is_reused_not_regenerated():
    app = _make_app()
    csrf_mod.csrf(app)

    @app.route("/data")
    def data():
        return "hello"

    client = app.test_client()
    client.set_cookie("CSRF-TOKEN", "my-preexisting-token", domain="localhost")

    resp = client.get("/data")
    set_cookie = resp.headers.get("Set-Cookie", "")
    assert "CSRF-TOKEN=my-preexisting-token" in set_cookie


def test_csrf_token_domain_config_sets_cookie_domain():
    app = _make_app(CSRF_TOKEN_DOMAIN=".example.com")
    csrf_mod.csrf(app)

    @app.route("/data")
    def data():
        return "hello"

    client = app.test_client()
    resp = client.get("/data")

    assert "Domain=example.com" in resp.headers.get("Set-Cookie", "")


def test_custom_csrf_token_key_name():
    app = _make_app(CSRF_TOKEN="MY-CUSTOM-TOKEN")
    csrf_mod.csrf(app)

    @app.route("/data")
    def data():
        return "hello"

    @app.route("/submit", methods=["POST"])
    def submit():
        return "submitted"

    client = app.test_client()
    get_resp = client.get("/data")
    set_cookie = get_resp.headers.get("Set-Cookie", "")
    assert "MY-CUSTOM-TOKEN=" in set_cookie
    token = set_cookie.split("MY-CUSTOM-TOKEN=")[1].split(";")[0]

    post_resp = client.post("/submit", headers={"MY-CUSTOM-TOKEN": token})
    assert post_resp.status_code == 200


def test_csrf_token_available_to_jinja_templates():
    app = _make_app()
    csrf_mod.csrf(app)

    @app.route("/render")
    def render():
        from flask import render_template_string

        return render_template_string("{{ csrfToken() }}")

    client = app.test_client()
    resp = client.get("/render")

    assert resp.status_code == 200
    # The token rendered into the body must match the one set on the cookie.
    cookie_token = resp.headers.get("Set-Cookie").split("CSRF-TOKEN=")[1].split(";")[0]
    assert resp.data.decode() == cookie_token


def test_testing_config_short_circuits_csrf_protection_entirely():
    """`_csrf_protect` explicitly no-ops when app.config['TESTING'] is
    truthy ("This simplifies unit testing, wherein CSRF seems to break.").
    Every other test in this file deliberately sets TESTING=False so CSRF
    enforcement actually runs; this test exercises the opposite branch."""
    app = _make_app(TESTING=True)
    csrf_mod.csrf(app)

    @app.route("/submit", methods=["POST"])
    def submit():
        return "submitted"

    client = app.test_client()
    resp = client.post("/submit")  # no CSRF token supplied at all

    assert resp.status_code == 200


def test_on_csrf_callback_is_broken_due_to_missing_flask_match_request(monkeypatch):
    """POSSIBLE BUG (documented, not fixed): on CSRF failure, if an
    `on_csrf` callback was supplied to `csrf(app, on_csrf=...)`, the hook
    does:

        on_csrf(*app.match_request())

    `flask.Flask` has no `match_request` method (verified directly: it is
    not defined anywhere on the Flask class in this environment's Flask
    version, 3.1.2). This raises AttributeError instead of ever invoking
    the custom callback, turning what should be a graceful custom failure
    response into an unhandled-exception 500.
    """
    called = {}

    def on_csrf_cb(*a):
        called["args"] = a

    app = _make_app()
    csrf_mod.csrf(app, on_csrf=on_csrf_cb)

    @app.route("/submit", methods=["POST"])
    def submit():
        return "submitted"

    client = app.test_client()
    resp = client.post("/submit")

    assert resp.status_code == 500
    assert "args" not in called  # the callback was never actually reached
