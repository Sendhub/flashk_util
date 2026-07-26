"""
Tests for flashk_util.authdigest (RFC 2617 digest authentication support).

Imported here as the bare top-level `authdigest` module (rather than
`flashk_util.authdigest`) to match how `flashk_util.auth.FlaskRealmDigestDb`
itself imports it (`import authdigest`, at the top of auth.py) -- both name
resolutions share the same cached module object via sys.modules once
`utils/flashk_util` is on sys.path (done in conftest.py), so the
`working_digest_hash` fixture's monkeypatch of `DigestAuthentication
.hash_algorithms` is visible from both this file and test_auth.py.

Two real, demonstrated bugs are documented below rather than fixed:
  1. The default hash closure passes an un-encoded `str` to `hashlib.md5`/
     `hashlib.sha1`, which requires bytes -- breaks every hashing operation.
  2. `RealmDigestDb.challenge()` calls `WWWAuthenticate.set_digest(...)`,
     a method that does not exist on the `WWWAuthenticate` class shipped
     with the werkzeug version installed in this environment (3.1.3) --
     `set_digest` resolves to `None` via that class's custom `__getattr__`,
     so calling it raises TypeError.
"""

import hashlib

import pytest

import authdigest


# ---------------------------------------------------------------------------
# REAL BUG: default hash closure
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("hash_obj", [hashlib.md5, hashlib.sha1])
def test_hash_closure_is_broken_for_unencoded_strings(hash_obj):
    """POSSIBLE BUG (documented, not fixed): `add_digest_hash_alg`'s inner
    closure does `hash_obj(_x).hexdigest()` where `_x` is a `str` produced
    by `":".join(map(str, args))`. `hashlib.md5`/`hashlib.sha1` require a
    bytes-like object, so this raises TypeError for every call. In practice
    this means `RealmDigestDb.add_user`, `DigestAuthentication.hash_password`,
    `.verify`, and `.digest` are all non-functional as shipped.
    """
    with pytest.raises(TypeError, match="Strings must be encoded before hashing"):
        hash_obj("some:unencoded:string").hexdigest()

    # Confirm this is exactly what the shipped closure does, end to end:
    db = authdigest.RealmDigestDb("test-realm", algorithm="md5" if hash_obj is hashlib.md5 else "sha")
    with pytest.raises(TypeError, match="Strings must be encoded before hashing"):
        db.add_user("admin", "secret")


# ---------------------------------------------------------------------------
# REAL BUG: challenge() relies on a removed werkzeug API
# ---------------------------------------------------------------------------


def test_challenge_is_broken_against_installed_werkzeug():
    """POSSIBLE BUG (documented, not fixed): `RealmDigestDb.challenge()` does

        auth_req.set_digest(self.realm, binascii.hexlify(os.urandom(8)).decode())

    where `auth_req` is a `werkzeug.datastructures.WWWAuthenticate` instance.
    That class no longer defines `set_digest` in the werkzeug version pinned
    for this repo (3.1.3) -- attribute access falls through its
    `__getattr__` and returns `None` instead of raising AttributeError, so
    the subsequent call raises TypeError ('NoneType' object is not
    callable). This means any request that should receive a proper 401
    digest challenge instead raises an unhandled exception.
    """
    db = authdigest.RealmDigestDb("test-realm")
    with pytest.raises(TypeError):
        db.challenge()

    import werkzeug

    with pytest.raises(TypeError):
        db.challenge(response=werkzeug.Response())


def test_challenge_status_assignment_branches_before_hitting_the_bug():
    """Exercises both branches of the pre-existing-response status
    assignment (int vs. non-int `status`) in `challenge()`, which run
    successfully before the `set_digest` bug is hit on the next line."""
    import werkzeug

    db = authdigest.RealmDigestDb("test-realm")

    resp_int_status = werkzeug.Response()
    with pytest.raises(TypeError):
        db.challenge(response=resp_int_status, status=403)
    assert resp_int_status.status_code == 403

    resp_str_status = werkzeug.Response()
    with pytest.raises(TypeError):
        db.challenge(response=resp_str_status, status="403 FORBIDDEN")
    assert resp_str_status.status == "403 FORBIDDEN"


# ---------------------------------------------------------------------------
# RealmDigestDb: dict-like interface (unaffected by the hashing bug once a
# working hash implementation is substituted)
# ---------------------------------------------------------------------------


def test_add_user_and_dict_like_access(working_digest_hash):
    db = authdigest.RealmDigestDb("test-realm")
    ha1 = db.add_user("admin", "secret")

    assert ha1 == hashlib.md5(b"admin:test-realm:secret").hexdigest()
    assert "admin" in db
    assert "nobody" not in db
    assert db["admin"] == ha1
    assert db.get("admin") == ha1
    assert db.get("missing") is None
    assert db.get("missing", "default") == "default"


def test_setitem_and_delitem(working_digest_hash):
    db = authdigest.RealmDigestDb("test-realm")
    db["bob"] = "pw123"
    assert "bob" in db
    assert db["bob"] == hashlib.md5(b"bob:test-realm:pw123").hexdigest()

    del db["bob"]
    assert "bob" not in db
    # Deleting a non-existent user is a no-op, not an error.
    del db["never-existed"]


def test_algorithm_property_and_sha_variant(working_digest_hash):
    db_md5 = authdigest.RealmDigestDb("r1")
    assert db_md5.algorithm == "md5"

    db_sha = authdigest.RealmDigestDb("r2", algorithm="sha")
    assert db_sha.algorithm == "sha"
    h = db_sha.add_user("u", "p")
    assert h == hashlib.sha1(b"u:r2:p").hexdigest()


def test_to_dict_and_to_json(working_digest_hash):
    db = authdigest.RealmDigestDb("test-realm")
    db.add_user("admin", "secret")

    as_dict = db.to_dict()
    assert as_dict["cfg"] == {"algorithm": "md5", "realm": "test-realm"}
    assert "admin" in as_dict["db"]

    as_json = db.to_json()
    import json as stdlib_json

    parsed = stdlib_json.loads(as_json)
    assert parsed == as_dict


# ---------------------------------------------------------------------------
# DigestAuthentication: qop branching
# ---------------------------------------------------------------------------


def test_digest_qop_auth_branch(working_digest_hash):
    from types import SimpleNamespace

    db = authdigest.RealmDigestDb("test-realm")
    ha1 = db.add_user("admin", "secret")
    alg = db.alg

    ha2 = alg._h("GET", "/protected")
    expected_response = alg._h(ha1, "nonce123", "00000001", "cnonce456", "auth", ha2)

    auth = SimpleNamespace(
        username="admin",
        realm="test-realm",
        uri="/protected",
        nonce="nonce123",
        nc="00000001",
        cnonce="cnonce456",
        qop="auth",
        response=expected_response,
    )
    assert alg.digest(auth, hash_pass=ha1, method="GET") == expected_response
    assert alg.verify(auth, hash_pass=ha1, method="GET") is True

    auth_wrong = SimpleNamespace(**{**auth.__dict__, "response": "not-the-right-response"})
    assert alg.verify(auth_wrong, hash_pass=ha1, method="GET") is False


def test_digest_empty_qop_branch(working_digest_hash):
    from types import SimpleNamespace

    db = authdigest.RealmDigestDb("test-realm")
    ha1 = db.add_user("admin", "secret")
    alg = db.alg

    ha2 = alg._h("GET", "/x")
    expected_response = alg._h(ha1, "nonceE", ha2)

    auth = SimpleNamespace(username="admin", realm="test-realm", uri="/x", nonce="nonceE", qop="", response=expected_response)
    assert alg.digest(auth, hash_pass=ha1, method="GET") == expected_response
    assert alg.verify(auth, hash_pass=ha1, method="GET") is True


def test_digest_unsupported_qop_raises(working_digest_hash):
    from types import SimpleNamespace

    db = authdigest.RealmDigestDb("test-realm")
    alg = db.alg
    auth = SimpleNamespace(username="admin", realm="test-realm", uri="/x", nonce="n", qop="int", response="x")

    with pytest.raises(ValueError, match="Unsupported qop"):
        alg.digest(auth, hash_pass="dummy-ha1", method="GET")


def test_digest_returns_none_when_authorization_is_none(working_digest_hash):
    db = authdigest.RealmDigestDb("test-realm")
    assert db.alg.digest(None) is None
    assert db.alg.verify(None) is None


def test_digest_computes_ha1_from_password_when_hash_pass_not_supplied(working_digest_hash):
    """When `digest()` is called without a precomputed `hash_pass`, it
    derives HA1 itself via `_compute_ha1`, which needs `password` in kw."""
    from types import SimpleNamespace

    db = authdigest.RealmDigestDb("test-realm")
    alg = db.alg
    auth = SimpleNamespace(username="admin", realm="test-realm", uri="/x", nonce="n", qop="", password="secret")

    ha1 = hashlib.md5(b"admin:test-realm:secret").hexdigest()
    ha2 = alg._h("GET", "/x")
    expected = alg._h(ha1, "n", ha2)

    result = alg.digest(auth, hash_pass=None, method="GET", password="secret")
    assert result == expected


def test_compute_ha1_falls_back_to_authorization_password(working_digest_hash):
    from types import SimpleNamespace

    db = authdigest.RealmDigestDb("test-realm")
    alg = db.alg
    auth = SimpleNamespace(username="admin", realm="test-realm", password="secret")
    ha1 = alg._compute_ha1(auth)
    assert ha1 == hashlib.md5(b"admin:test-realm:secret").hexdigest()


# ---------------------------------------------------------------------------
# RealmDigestDb.is_authenticated: full control-flow coverage
# ---------------------------------------------------------------------------


def _build_authorization(username, realm, uri, nonce, nc, cnonce, qop, ha1, method="GET"):
    from types import SimpleNamespace

    db_tmp = authdigest.RealmDigestDb(realm)
    alg = db_tmp.alg
    ha2 = alg._h(method, uri)
    if qop:
        response = alg._h(ha1, nonce, nc, cnonce, qop, ha2)
    else:
        response = alg._h(ha1, nonce, ha2)
    kwargs = dict(username=username, realm=realm, uri=uri, nonce=nonce, qop=qop, response=response)
    if qop:
        kwargs.update(nc=nc, cnonce=cnonce)
    return SimpleNamespace(**kwargs)


def test_is_authenticated_success(working_digest_hash):
    from types import SimpleNamespace

    db = authdigest.RealmDigestDb("test-realm")
    ha1 = db.add_user("admin", "secret")
    auth = _build_authorization("admin", "test-realm", "/protected", "nonce1", "00000001", "cnonce1", "auth", ha1)
    request = SimpleNamespace(authorization=auth, method="GET")

    result = db.is_authenticated(request)

    assert bool(result) is True
    assert result.reason == "success"
    assert result.status == 200
    assert request.authentication is result
    assert auth.result is result


def test_is_authenticated_no_authorization_header(working_digest_hash):
    from types import SimpleNamespace

    db = authdigest.RealmDigestDb("test-realm")
    request = SimpleNamespace(authorization=None, method="GET")

    result = db.is_authenticated(request)

    assert bool(result) is False
    assert result.reason == "initial"
    assert result.status == 401


def test_is_authenticated_unknown_user(working_digest_hash):
    from types import SimpleNamespace

    db = authdigest.RealmDigestDb("test-realm")
    auth = _build_authorization("ghost", "test-realm", "/x", "n", "1", "c", "auth", "irrelevant-ha1")
    request = SimpleNamespace(authorization=auth, method="GET")

    result = db.is_authenticated(request)

    assert bool(result) is False
    assert result.reason == "unknown_user"
    assert result.status == 401


def test_is_authenticated_invalid_password(working_digest_hash):
    from types import SimpleNamespace

    db = authdigest.RealmDigestDb("test-realm")
    ha1 = db.add_user("admin", "secret")
    auth = _build_authorization("admin", "test-realm", "/protected", "nonce1", "00000001", "cnonce1", "auth", ha1)
    auth.response = "deliberately-wrong"
    request = SimpleNamespace(authorization=auth, method="GET")

    result = db.is_authenticated(request)

    assert bool(result) is False
    assert result.reason == "invalid_password"
    assert result.status == 401


# ---------------------------------------------------------------------------
# AuthenticationResult
# ---------------------------------------------------------------------------


def test_authentication_result_deny_and_approve():
    db = authdigest.RealmDigestDb("test-realm")
    result = authdigest.AuthenticationResult(db)

    assert bool(result) is False  # default unset state
    result.deny("bad_creds")
    assert bool(result) is False
    assert result.reason == "bad_creds"
    assert result.status == 401

    result.approve("good_creds")
    assert bool(result) is True
    assert result.reason == "good_creds"
    assert result.status == 200


def test_authentication_result_deny_rejects_truthy_authenticated():
    db = authdigest.RealmDigestDb("test-realm")
    result = authdigest.AuthenticationResult(db)
    with pytest.raises(ValueError, match="Denied authenticated parameter must evaluate as False"):
        result.deny("bad", authenticated=True)


def test_authentication_result_approve_rejects_falsy_authenticated():
    db = authdigest.RealmDigestDb("test-realm")
    result = authdigest.AuthenticationResult(db)
    with pytest.raises(ValueError, match="Approved authenticated parameter must evaluate as True"):
        result.approve("bad", authenticated=False)


def test_authentication_result_repr():
    db = authdigest.RealmDigestDb("test-realm")
    result = authdigest.AuthenticationResult(db)
    result.approve("ok")
    assert repr(result) == "<authenticated: True reason: 'ok'>"


def test_authentication_result_challenge_delegates_to_auth_db(working_digest_hash):
    db = authdigest.RealmDigestDb("test-realm")
    result = authdigest.AuthenticationResult(db)
    result.deny("bad")

    # Not authenticated -> should attempt to delegate to db.challenge(), which
    # itself raises TypeError due to the werkzeug incompatibility documented
    # in test_challenge_is_broken_against_installed_werkzeug above.
    with pytest.raises(TypeError):
        result.challenge()


def test_authentication_result_challenge_is_noop_when_authenticated_and_not_forced():
    db = authdigest.RealmDigestDb("test-realm")
    result = authdigest.AuthenticationResult(db)
    result.approve("ok")

    assert result.challenge() is None


def test_authentication_result_holds_weakref_to_auth_db():
    """auth_db is stored as a weakref; once the original RealmDigestDb is
    garbage collected, auth_db() returns None."""
    import gc

    db = authdigest.RealmDigestDb("test-realm")
    result = authdigest.AuthenticationResult(db)
    assert result.auth_db() is db

    del db
    gc.collect()
    assert result.auth_db() is None
