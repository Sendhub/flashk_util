"""
Tests for flashk_util.response.

REAL BUG (documented, not fixed): `configure_flask_exception_handler` writes
directly into `app.error_handler_spec[None][code] = make_json_error`. In the
werkzeug/Flask version pinned for this repo (Flask 3.1.2), that dict is
expected to be a THREE-level structure:
`error_handler_spec[blueprint][code][exc_class] = handler` (verified
directly: registering a handler the normal way via `@app.errorhandler(404)`
produces `{None: {404: {NotFound: handler}}}`). Writing a bare callable at
the second level instead of a `{exc_class: handler}` dict means Flask's own
`_find_error_handler` crashes with `AttributeError: 'function' object has no
attribute 'get'` the first time ANY HTTP exception (including a plain 404)
is raised in an app configured this way.
"""

import pytest
from flask import Flask, abort
from werkzeug.exceptions import NotFound

import flashk_util.response as response_mod


def test_make_json_error_with_http_exception(app):
    with app.test_request_context():
        err = NotFound()
        resp = response_mod.make_json_error(err)

        assert resp.status_code == 404
        payload = resp.get_json()
        assert payload["code"] == 404
        assert "message" in payload


def test_make_json_error_with_generic_exception_defaults_to_500(app):
    with app.test_request_context():
        err = ValueError("something broke")
        resp = response_mod.make_json_error(err)

        assert resp.status_code == 500
        payload = resp.get_json()
        assert payload["message"] == "something broke"
        assert "code" not in payload


@pytest.mark.parametrize("exc_class,code", [(NotFound, 404)])
def test_make_json_error_message_matches_exception_str(app, exc_class, code):
    with app.test_request_context():
        err = exc_class()
        resp = response_mod.make_json_error(err)
        payload = resp.get_json()
        assert payload["message"] == str(err)


def test_configure_flask_exception_handler_is_broken_against_installed_flask():
    """POSSIBLE BUG (documented, not fixed): see module docstring above.
    Demonstrates that a plain abort(404) crashes with AttributeError inside
    Flask's own error-handling machinery once
    `configure_flask_exception_handler` has run, instead of returning the
    intended JSON 404 body.

    The failure is actually worse than an ordinary unhandled view exception:
    Flask's outer catch-all (`handle_exception`, invoked from `wsgi_app` for
    anything escaping `full_dispatch_request`) itself tries to look up a 500
    handler via the same broken `error_handler_spec` structure -- since
    `configure_flask_exception_handler` registered every `default_exceptions`
    code (including 500) the same broken way, that lookup fails too. The
    AttributeError therefore propagates all the way out through the WSGI
    layer uncaught, rather than the app degrading to a plain 500 response.
    """
    app = Flask(__name__)
    app.config.update(SECRET_KEY="test", TESTING=False, DEBUG=False)
    response_mod.configure_flask_exception_handler(app)

    @app.route("/boom")
    def boom():
        abort(404)

    client = app.test_client()
    with pytest.raises(AttributeError, match="'function' object has no attribute 'get'"):
        client.get("/boom")


def test_error_handler_spec_structure_mismatch_directly():
    """Isolates the exact bug: compare the shape
    `configure_flask_exception_handler` writes against the shape Flask's
    `_find_error_handler` actually reads."""
    app = Flask(__name__)
    response_mod.configure_flask_exception_handler(app)

    # What configure_flask_exception_handler actually wrote:
    assert callable(app.error_handler_spec[None][404])

    # What Flask itself writes/expects when you register handlers the
    # supported way (a nested {exc_class: handler} dict per code):
    app2 = Flask(__name__)

    @app2.errorhandler(404)
    def handler(e):
        return "custom", 404

    assert isinstance(app2.error_handler_spec[None][404], dict)
    assert NotFound in app2.error_handler_spec[None][404]
