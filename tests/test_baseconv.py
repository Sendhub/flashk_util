"""
Tests for flashk_util.baseconv: base-N integer <-> string conversion.
"""

import pytest

from flashk_util import baseconv


@pytest.mark.parametrize(
    "converter",
    [
        baseconv.base2,
        baseconv.base16,
        baseconv.base36,
        baseconv.base56,
        baseconv.base62,
        baseconv.base64,
    ],
    ids=["base2", "base16", "base36", "base56", "base62", "base64"],
)
@pytest.mark.parametrize("value", [0, 1, 9, 42, 1234, 999999, 2**31, 2**63])
def test_round_trip_positive(converter, value):
    encoded = converter.encode(value)
    assert converter.decode(encoded) == value


@pytest.mark.parametrize(
    "converter",
    [
        baseconv.base2,
        baseconv.base16,
        baseconv.base36,
        baseconv.base56,
        baseconv.base62,
        baseconv.base64,
    ],
    ids=["base2", "base16", "base36", "base56", "base62", "base64"],
)
@pytest.mark.parametrize("value", [-1, -42, -1234, -999999])
def test_round_trip_negative_default_sign(converter, value):
    """Negative integer inputs round-trip correctly for every module-level
    converter: encode() detects negativity via a hardcoded '-' check against
    str(value) (always true for a real negative int, regardless of
    self.sign), then prefixes the result with self.sign; decode() correctly
    strips self.sign again."""
    encoded = converter.encode(value)
    assert encoded.startswith(converter.sign)
    assert converter.decode(encoded) == value


def test_base62_alphabet_order_digit_zero():
    assert baseconv.base62.encode(0) == "0"
    assert baseconv.base62.decode("0") == 0


def test_repr():
    assert repr(baseconv.base62) == f"<BaseConverter: base62 ({baseconv.BASE62_ALPHABET})>"
    assert repr(baseconv.base2) == "<BaseConverter: base2 (01)>"


def test_sign_char_in_digits_raises_value_error():
    with pytest.raises(ValueError, match="Sign character found in converter base digits."):
        baseconv.BaseConverter("0123456789-", sign="-")


def test_docstring_example_base20():
    """Verifies the example given in the module's own docstring."""
    base20 = baseconv.BaseConverter("0123456789abcdefghij")
    assert base20.encode(1234) == "31e"
    assert base20.decode("31e") == 1234
    assert base20.encode(-1234) == "-31e"
    assert base20.decode("-31e") == -1234


def test_custom_sign_encode_of_plain_negative_int_works():
    """A BaseConverter with a non-default `sign` still round-trips a genuine
    negative *integer* input correctly, because str(-1234)[0] == '-' matches
    the hardcoded sign check inside encode()->convert()."""
    base11 = baseconv.BaseConverter("0123456789-", sign="$")
    encoded = base11.encode(-1234)
    assert encoded == "$-22"
    assert base11.decode("$-22") == -1234


def test_custom_sign_encode_of_custom_sign_prefixed_string_is_broken():
    """POSSIBLE BUG (documented, not fixed): the module's own docstring shows

        >>> base11.encode('$1234')
        '$-22'

    as a valid usage pattern for custom-sign converters (encoding a string
    that is itself prefixed with the converter's own `sign` character).
    In the real implementation, `BaseConverter.encode()` hardcodes the
    literal '-' character when calling `convert()` instead of passing
    `self.sign`:

        neg, value = self.convert(i, self.decimal_digits, self.digits, "-")

    So for a converter with a non-default sign (here '$'), encode() never
    recognizes the leading '$' as the sign marker, doesn't strip it, and
    then fails while treating '$' as one of the base digits.
    """
    base11 = baseconv.BaseConverter("0123456789-", sign="$")
    with pytest.raises(ValueError, match="substring not found"):
        base11.encode("$1234")


def test_decode_always_returns_int_not_custom_sign_string():
    """The module docstring also claims base11.decode('$-22') == '$1234'
    (implying encode/decode round-trip back to the original custom-sign
    string). In reality decode() always returns `int(value)` -- it never
    reconstructs a custom-sign-prefixed string. Documenting actual behavior."""
    base11 = baseconv.BaseConverter("0123456789-", sign="$")
    result = base11.decode("$-22")
    assert result == -1234
    assert isinstance(result, int)
