"""
Tests for flashk_util.crypto.

Several functions in this module are demonstrably broken as currently
written (confirmed by direct execution, not just static reading -- see the
docstrings on the affected tests below). Per instructions, these are
documented with tests that assert the ACTUAL (buggy) behavior rather than
silently patched. They are flagged again in the final report.
"""

import datetime
from decimal import Decimal

import pytest

from flashk_util import crypto


# ---------------------------------------------------------------------------
# b64_encode / b64_decode
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw",
    [b"", b"a", b"ab", b"abc", b"hello world!!", b"\x00\x01\x02\xff\xfe", b"x" * 100],
)
def test_b64_round_trip(raw):
    encoded = crypto.b64_encode(raw)
    assert isinstance(encoded, bytes)
    assert b"=" not in encoded
    assert crypto.b64_decode(encoded) == raw


def test_b64_encode_is_urlsafe():
    # Bytes chosen so the base64 output would normally contain '+' and '/'
    # in standard (non-urlsafe) base64; urlsafe swaps those for '-' and '_'.
    raw = bytes(range(256))
    encoded = crypto.b64_encode(raw)
    assert b"+" not in encoded
    assert b"/" not in encoded
    assert crypto.b64_decode(encoded) == raw


# ---------------------------------------------------------------------------
# is_protected_type / force_bytes
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value,expected",
    [
        (None, True),
        (5, True),
        (5.5, True),
        (Decimal("1.5"), True),
        (datetime.datetime(2020, 1, 1), True),
        (datetime.date(2020, 1, 1), True),
        (datetime.time(1, 2, 3), True),
        ("a string", False),
        ([1, 2, 3], False),
        ({"a": 1}, False),
        (object(), False),
    ],
)
def test_is_protected_type(value, expected):
    assert crypto.is_protected_type(value) is expected


def test_force_bytes_from_str_default_utf8():
    assert crypto.force_bytes("abc") == b"abc"
    assert crypto.force_bytes("café") == "café".encode("utf-8")


def test_force_bytes_bytes_passthrough_same_encoding():
    original = b"already-bytes"
    assert crypto.force_bytes(original, encoding="utf-8") == original


def test_force_bytes_bytes_reencoded_when_encoding_differs():
    original = "café".encode("utf-8")
    reencoded = crypto.force_bytes(original, encoding="latin-1")
    assert reencoded == "café".encode("latin-1")


def test_force_bytes_memoryview():
    assert crypto.force_bytes(memoryview(b"abc")) == b"abc"


def test_force_bytes_strings_only_preserves_protected_type():
    # strings_only=True: protected (non-string-like) types pass through
    # unchanged rather than being stringified+encoded.
    assert crypto.force_bytes(5, strings_only=True) == 5
    assert crypto.force_bytes(None, strings_only=True) is None


def test_force_bytes_generic_object_str_and_encodes():
    assert crypto.force_bytes(1234) == b"1234"


# ---------------------------------------------------------------------------
# salted_hmac / base64_hmac / constant_time_compare
# ---------------------------------------------------------------------------


def test_salted_hmac_is_deterministic_for_same_inputs():
    h1 = crypto.salted_hmac("salt1", "value1", secret="shared-secret")
    h2 = crypto.salted_hmac("salt1", "value1", secret="shared-secret")
    assert h1.digest() == h2.digest()


def test_salted_hmac_differs_with_different_secret():
    h1 = crypto.salted_hmac("salt1", "value1", secret="secret-a")
    h2 = crypto.salted_hmac("salt1", "value1", secret="secret-b")
    assert h1.digest() != h2.digest()


def test_salted_hmac_differs_with_different_salt():
    h1 = crypto.salted_hmac("salt1", "value1", secret="shared-secret")
    h2 = crypto.salted_hmac("salt2", "value1", secret="shared-secret")
    assert h1.digest() != h2.digest()


def test_salted_hmac_uses_settings_secret_key_by_default(monkeypatch):
    import settings

    monkeypatch.setattr(settings, "SECRET_KEY", "from-settings", raising=False)
    h_default = crypto.salted_hmac("salt", "value")
    h_explicit = crypto.salted_hmac("salt", "value", secret="from-settings")
    assert h_default.digest() == h_explicit.digest()


def test_salted_hmac_invalid_algorithm_raises():
    with pytest.raises(crypto.InvalidAlgorithm, match="not-a-real-algo"):
        crypto.salted_hmac("salt", "value", secret="x", algorithm="not-a-real-algo")


def test_base64_hmac_deterministic_and_matches_salted_hmac():
    sig = crypto.base64_hmac("salt", "value", "key")
    expected = crypto.b64_encode(crypto.salted_hmac("salt", "value", "key").digest()).decode()
    assert sig == expected


def test_base64_hmac_differs_for_different_values():
    sig1 = crypto.base64_hmac("salt", "value-one", "key")
    sig2 = crypto.base64_hmac("salt", "value-two", "key")
    assert sig1 != sig2


def test_constant_time_compare_equal():
    assert crypto.constant_time_compare("abc", "abc") is True


def test_constant_time_compare_not_equal():
    assert crypto.constant_time_compare("abc", "abd") is False


def test_constant_time_compare_normalizes_str_and_bytes():
    assert crypto.constant_time_compare(b"abc", "abc") is True


# ---------------------------------------------------------------------------
# unsign() -- REAL BUG (documented, not fixed)
# ---------------------------------------------------------------------------


def test_unsign_missing_separator_raises_bad_signature():
    with pytest.raises(crypto.BadSignature, match='No ":" found in value'):
        crypto.unsign("no-separator-here")


def test_unsign_is_broken_for_well_formed_input():
    """POSSIBLE BUG (documented, not fixed): `unsign()` does

        constant_time_compare(sig, signature(value))

    but `signature` here is `inspect.signature` (imported at the top of the
    module as `from inspect import signature`) -- there is no local
    HMAC-signing helper named `signature` defined anywhere in this module
    (only `_legacy_signature` exists, used as the second `or` operand).
    Calling `inspect.signature("some string")` immediately raises TypeError
    because a plain string isn't an inspectable callable. Since this
    expression is evaluated eagerly as an argument to `constant_time_compare`,
    it blows up before the `or _legacy_signature(...)` fallback is ever
    reached -- `unsign()` cannot successfully validate ANY signed value,
    even one produced by the legacy path, and always raises TypeError
    instead of either returning the original value or raising BadSignature.
    """
    with pytest.raises(TypeError):
        crypto.unsign("somevalue:somesignature")


# ---------------------------------------------------------------------------
# load_encoded_s() -- REAL BUG (documented, not fixed)
# ---------------------------------------------------------------------------


def test_load_encoded_s_rejects_empty_and_non_dot_prefixed_values():
    with pytest.raises(Exception, match="was expecting something which starts"):
        crypto.load_encoded_s("")
    with pytest.raises(Exception, match="was expecting something which starts"):
        crypto.load_encoded_s("no-leading-dot")


def test_load_encoded_s_is_broken_for_both_str_and_bytes_input():
    """POSSIBLE BUG (documented, not fixed): `load_encoded_s` cannot
    successfully decode a well-formed value of either input type:

    - As `str`: the leading-character check `unsigned_value[0] != "."`
      works, but `unsigned_value[1:]` is then passed to `b64_decode`,
      which does `_s + pad` where `pad = b"=" * ...` is `bytes` -- so
      `str + bytes` raises TypeError.
    - As `bytes`: `b64_decode` would work (bytes + bytes pad), but the
      leading-character check `unsigned_value[0] != "."` compares an
      `int` (indexing bytes yields an int) against the `str` "." , which
      is always True/not-equal, so the function unconditionally raises
      "Invalid unsigned value" before ever reaching `b64_decode`.

    There is no input type for which this function currently succeeds,
    even though `dict2signed` (the producer for `load_encoded_s`'s
    intended input) is separately broken too -- see test_crypto.py's
    dict2signed tests.
    """
    import zlib

    import simplejson as json

    payload = {"a": 1, "b": "x"}
    compressed = zlib.compress(json.dumps(payload, separators=(",", ":")).encode())

    encoded_str = "." + crypto.b64_encode(compressed).decode()
    with pytest.raises(TypeError):
        crypto.load_encoded_s(encoded_str)

    encoded_bytes = b"." + crypto.b64_encode(compressed)
    with pytest.raises(Exception, match="was expecting something which starts"):
        crypto.load_encoded_s(encoded_bytes)


# ---------------------------------------------------------------------------
# dict2signed() -- REAL BUGS (documented, not fixed)
# ---------------------------------------------------------------------------


def test_dict2signed_is_broken_zlib_compress_needs_bytes():
    """POSSIBLE BUG (documented, not fixed): `dict2signed` does

        b64d = "." + b64_encode(zlib.compress(json.dumps(data, separators=(",", ":"))))

    `json.dumps(...)` returns a `str`, but `zlib.compress` requires a
    bytes-like object -- this raises TypeError on every call, before the
    function can even get to its second bug (see below).
    """
    with pytest.raises(TypeError, match="bytes-like object is required"):
        crypto.dict2signed({"a": 1})


def test_base64_hmac_call_inside_dict2signed_has_a_second_independent_bug():
    """POSSIBLE BUG (documented, not fixed): even if the zlib.compress bug
    above were fixed, `dict2signed`'s signing line would still fail:

        signed = f"{value}:{base64_hmac((settings.SALT + 'signer', value, settings.SECRET_KEY))}"

    Note the extra parentheses -- this calls `base64_hmac` with a single
    positional argument (a 3-tuple), instead of three separate positional
    arguments. `base64_hmac(salt, value, key, algorithm="sha1")` has no
    default for `value`/`key`, so this raises TypeError for missing
    required arguments. Demonstrated directly here since dict2signed's
    first bug (above) prevents execution from ever reaching this line.
    """
    with pytest.raises(TypeError, match="missing 2 required positional arguments"):
        crypto.base64_hmac(("salt-part", "value-part", "key-part"))
