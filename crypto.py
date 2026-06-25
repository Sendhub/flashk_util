"""
Crypto module.
"""

import base64
import datetime
import hashlib
import hmac
import zlib
from decimal import Decimal
from inspect import signature

import simplejson as json

SEP = ":"

_PROTECTED_TYPES = (
    type(None),
    int,
    float,
    Decimal,
    datetime.datetime,
    datetime.date,
    datetime.time,
)


class BadSignature(Exception):
    """
    Signature does not match.
    """

    pass


def b64_encode(_s):
    """
    Encode string as base64.
    """
    return base64.urlsafe_b64encode(_s).strip(b"=")


def b64_decode(_s):
    """
    Decode string as base64.
    """
    pad = b"=" * (-len(_s) % 4)
    return base64.urlsafe_b64decode(_s + pad)


def is_protected_type(obj):
    """
    Determine if the object instance is of a protected type.

    Objects of protected types are preserved as-is when passed to force_str(strings_only=True).
    """
    return isinstance(obj, _PROTECTED_TYPES)


def force_bytes(s, encoding="utf-8", strings_only=False, errors="strict"):
    """
    Similar to smart_bytes, except that lazy instances are resolved to strings, rather than kept as lazy objects.

    If strings_only is True, do not convert (some) non-string-like objects.
    """
    # Handle the common case first for performance reasons.
    if isinstance(s, bytes):
        if encoding == "utf-8":
            return s
        else:
            return s.decode("utf-8", errors).encode(encoding, errors)
    if strings_only and is_protected_type(s):
        return s
    if isinstance(s, memoryview):
        return bytes(s)
    return str(s).encode(encoding, errors)


class InvalidAlgorithm(ValueError):
    """Algorithm is not supported by hashlib."""

    pass


def salted_hmac(key_salt, value, secret=None, *, algorithm="sha1"):
    """
    Return the HMAC of 'value', using a key generated from key_salt and a
    secret (which defaults to settings.SECRET_KEY). Default algorithm is SHA1,
    but any algorithm name supported by hashlib.new() can be passed.

    A different key_salt should be passed in for every application of HMAC.
    """
    # Moved to function level to avoid circular import issues
    import settings

    if secret is None:
        secret = settings.SECRET_KEY

    key_salt = force_bytes(key_salt)
    secret = force_bytes(secret)
    try:
        hasher = getattr(hashlib, algorithm)
    except AttributeError as e:
        raise InvalidAlgorithm("%r is not an algorithm accepted by the hashlib module." % algorithm) from e
    # We need to generate a derived key from our base key.  We can do this by
    # passing the key_salt and our base key through a pseudo-random function.
    key = hasher(key_salt + secret).digest()
    # If len(key_salt + secret) > block size of the hash algorithm, the above
    # line is redundant and could be replaced by key = key_salt + secret, since
    # the hmac module does the same thing for keys longer than the block size.
    # However, we need to ensure that we *always* do this.
    return hmac.new(key, msg=force_bytes(value), digestmod=hasher)


def base64_hmac(salt, value, key, algorithm="sha1"):
    """encodes hmac"""
    return b64_encode(salted_hmac(salt, value, key, algorithm=algorithm).digest()).decode()


def constant_time_compare(val1, val2):
    """Return True if the two strings are equal, False otherwise."""
    # Moved to function level - only used here
    import secrets

    return secrets.compare_digest(force_bytes(val1), force_bytes(val2))


def _legacy_signature(value):
    # RemovedInDjango40Warning.
    # Moved to function level to avoid circular import issues

    import settings

    legacy_algorithm = "sha1"
    return base64_hmac(settings.SALT + "signer", value, settings.SECRET_KEY, algorithm=legacy_algorithm)


def unsign(signed_value):
    """unsign the signature value"""
    legacy_algorithm = "sha1"
    if SEP not in signed_value:
        raise BadSignature(f'No "{SEP}" found in value')
    value, sig = signed_value.rsplit(SEP, 1)
    if constant_time_compare(sig, signature(value)) or (legacy_algorithm and constant_time_compare(sig, _legacy_signature(value))):
        return value
    raise BadSignature(f'Signature "{sig}" does not match')


def load_encoded_s(unsigned_value):
    """Takes an unsigned value and decompresses and deserializes it."""
    if len(unsigned_value) == 0 or unsigned_value[0] != ".":
        raise Exception(f'Invalid unsigned value, "{unsigned_value}", was expecting something which starts with a "."')
    data = b64_decode(unsigned_value[1:])
    data2 = zlib.decompress(data)
    return json.loads(data2)


def dict2signed(data):
    """Takes a dictionary and produces a signed compressed value."""
    b64d = "." + b64_encode(zlib.compress(json.dumps(data, separators=(",", ":"))))
    # Moved to function level to avoid circular import issues
    import time

    import settings

    from . import baseconv

    value = f"{b64d}:{baseconv.base62.encode(int(time.time()))}"

    signed = f"{value}:{base64_hmac((settings.SALT + 'signer', value, settings.SECRET_KEY))}"

    return signed
