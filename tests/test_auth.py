"""
Tests for flashk_util.auth (FlaskRealmDigestDb.require_auth decorator).

REAL BUG (documented, not fixed): `require_auth`'s wrapped function calls

    if not self.isAuthenticated(request):

but `authdigest.RealmDigestDb` (the class `FlaskRealmDigestDb` subclasses)
defines this method as `is_authenticated` (snake_case) -- `git log -p` on
authdigest.py shows the method was renamed `isAuthenticated -> is_authenticated`
in a past refactor, but the call site in auth.py was never updated to match.
As a result, EVERY request to a `require_auth`-protected view raises
`AttributeError: 'FlaskRealmDigestDb' object has no attribute
'isAuthenticated'. Did you mean: 'is_authenticated'?` and gets turned into
an unhandled-exception 500 by Flask -- regardless of whether valid
credentials were supplied. This fails closed (no unauthorized access is
granted) but the protection is completely unusable: legitimate,
correctly-authenticated requests are blocked too.
"""

import pytest

import flashk_util.auth as auth_mod


def test_require_auth_preserves_function_metadata():
    """@wraps(func) should keep the wrapped view's __name__/__doc__."""
    db = auth_mod.FlaskRealmDigestDb("test-realm")

    def my_view():
        """My view docstring."""
        return "ok"

    decorated = db.require_auth(my_view)

    assert decorated.__name__ == "my_view"
    assert decorated.__doc__ == "My view docstring."
    assert decorated.__wrapped__ is my_view


def test_require_auth_crashes_on_any_request_due_to_isauthenticated_typo(app):
    """Demonstrates the real bug described in the module docstring above:
    the decorator is unconditionally broken, for both unauthenticated and
    (properly credentialed) authenticated requests."""
    db = auth_mod.FlaskRealmDigestDb("test-realm")

    @app.route("/protected")
    @db.require_auth
    def protected():
        return "secret-data"

    client = app.test_client()

    # `app` fixture sets TESTING=True, which makes Flask propagate
    # unhandled exceptions to the caller instead of converting them into a
    # 500 response -- so we assert on the raised AttributeError directly.

    # No Authorization header at all.
    with pytest.raises(AttributeError, match="isAuthenticated"):
        client.get("/protected")

    # Even a well-formed (if bogus) Authorization header hits the same
    # crash, because it happens before any credential checking occurs.
    with pytest.raises(AttributeError, match="isAuthenticated"):
        client.get(
            "/protected",
            headers={"Authorization": 'Digest username="admin", realm="test-realm", nonce="n", uri="/protected", response="x"'},
        )


def test_require_auth_decorator_logic_in_isolation(app, monkeypatch):
    """Isolates `require_auth`'s own branching logic (call-through when
    authenticated, invoke challenge() when not) from the two independently
    broken collaborators (`is_authenticated`'s method-name mismatch here,
    and `challenge()`'s werkzeug incompatibility documented in
    test_authdigest.py). We patch in an `isAuthenticated` method matching
    what the decorator actually calls, and a stub `challenge()`, purely to
    verify auth.py's own control flow is otherwise sound.
    """
    db = auth_mod.FlaskRealmDigestDb("test-realm")

    monkeypatch.setattr(db, "isAuthenticated", lambda request: True, raising=False)
    monkeypatch.setattr(db, "challenge", lambda: ("challenged", 401), raising=False)

    @app.route("/protected-ok")
    @db.require_auth
    def protected_ok():
        return "secret-data"

    client = app.test_client()
    resp = client.get("/protected-ok")
    assert resp.status_code == 200
    assert resp.data == b"secret-data"

    # Now flip to unauthenticated -> should invoke challenge() instead of
    # the wrapped view.
    monkeypatch.setattr(db, "isAuthenticated", lambda request: False, raising=False)

    resp2 = client.get("/protected-ok")
    assert resp2.status_code == 401
    assert resp2.data == b"challenged"


def test_flask_realm_digest_db_is_a_realm_digest_db():
    import authdigest

    db = auth_mod.FlaskRealmDigestDb("some-realm")
    assert isinstance(db, authdigest.RealmDigestDb)
    assert db.realm == "some-realm"
