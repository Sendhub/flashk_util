"""
Shared pytest fixtures and environment bootstrap for the flashk_util test suite.

``flashk_util`` is vendored into this repo (``utils/flashk_util``) as a git
submodule with no tests of its own. Its modules assume two things that don't
hold true out of the box in a bare pytest run:

1. Bare, self-referential imports such as ``import authdigest`` (see
   ``auth.py``) assume flashk_util *is* the repository root, which is only
   true when the submodule is checked out standalone. We add
   ``utils/flashk_util`` to ``sys.path`` so those bare imports resolve. Note
   this means the module imported as bare ``authdigest`` and the module
   imported as ``flashk_util.authdigest`` (via the vendoring alias set up by
   the repo-root ``sitecustomize.py``) end up as two distinct module objects
   even though they're the same source file -- harmless for testing as long
   as a given test is internally consistent about which one it exercises.

2. A bare ``import settings`` resolves to the repo-root ``settings.py``
   shim, which re-exports ``src.config``. ``src.config`` eagerly constructs
   a Kazoo client (among other things) at import time and raises if required
   env vars are absent. We set test-safe defaults before anything imports
   settings, mirroring the pattern already used in the main admin test suite
   (``tests/conftest.py``).
"""

import os
import sys

import pytest

_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
_FLASHK_UTIL_DIR = os.path.dirname(_TESTS_DIR)

if _FLASHK_UTIL_DIR not in sys.path:
    sys.path.insert(0, _FLASHK_UTIL_DIR)

os.environ.setdefault("KAZOO_BASE_API_KEY", "test-kazoo-api-key")
os.environ.setdefault("KAZOO_BASE_URL", "https://kazoo.test.invalid")
os.environ.setdefault("KAZOO_SENDHUB_ACCOUNT_ID", "test-account-id")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-flashk-util-tests")

import settings  # noqa: E402  (repo root is on sys.path via sitecustomize)

# Guarantee the attributes flashk_util modules read off `settings` at call
# time are present and known, regardless of what a partial/erroring
# src.config import left behind (see landmine #2 above).
settings.SECRET_KEY = getattr(settings, "SECRET_KEY", "") or "test-secret-key-for-flashk-util-tests"
settings.SALT = getattr(settings, "SALT", "") or "app.api.v1.auth.sessions.signed_cookies"
settings.pagingDefaultLimit = getattr(settings, "pagingDefaultLimit", None) or 10


@pytest.fixture
def app():
    """A minimal, isolated Flask app for request-context-dependent tests."""
    from flask import Flask

    flask_app = Flask(__name__)
    flask_app.config.update(SECRET_KEY="test-flask-secret", TESTING=True)
    return flask_app


@pytest.fixture
def working_digest_hash(monkeypatch):
    """Patch flashk_util.authdigest's hash algorithm table with a *working*
    implementation for the duration of a test.

    REAL BUG (documented, not fixed in source): `authdigest.DigestAuthentication
    .add_digest_hash_alg`'s inner closure does

        return hash_obj(_x).hexdigest()

    where `_x` is a plain `str` and `hash_obj` is `hashlib.md5`/`hashlib.sha1`.
    hashlib requires bytes, so this raises
    ``TypeError: Strings must be encoded before hashing`` for *every* call --
    add_user, hash_password, verify, digest, etc. are all broken as shipped.

    This fixture patches in a corrected closure (adds `.encode()`) purely so
    the surrounding orchestration logic (RealmDigestDb's dict-like interface,
    AuthenticationResult, DigestAuthentication's qop branching,
    is_authenticated's control flow) can be exercised and verified
    independently of that one broken leaf function. The raw bug itself is
    separately, directly demonstrated by
    test_authdigest.py::test_hash_closure_is_broken_for_unencoded_strings.
    """
    import hashlib

    import authdigest as bare_authdigest

    def make_working_h(hash_obj):
        def h(*args):
            joined = ":".join(map(str, args))
            return hash_obj(joined.encode()).hexdigest()

        return h

    monkeypatch.setitem(bare_authdigest.DigestAuthentication.hash_algorithms, "md5", make_working_h(hashlib.md5))
    monkeypatch.setitem(bare_authdigest.DigestAuthentication.hash_algorithms, "sha", make_working_h(hashlib.sha1))
    return bare_authdigest
