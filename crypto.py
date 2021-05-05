# -*- coding: utf-8 -*-
# pylint: disable=E0401, E1101,E0402
"""Crypto module"""
import base64
import hmac
import hashlib
import time
import zlib
import simplejson as json
import settings
from . import baseconv

SEP = ':'


def b64_encode(_s):
    """encodes string as base64"""
    return base64.urlsafe_b64encode(_s).decode('utf-8').strip('=')


def b64_decode(_s):
    """decodes string as base64"""
    return base64.urlsafe_b64decode(_s + ('=' * (-len(_s) % 4)))  # s + padding


def salted_hmac(key_salt, value, secret):
    """salted hmac"""
    return hmac.new(hashlib.sha1(key_salt + secret).digest(), msg=value,
                    digestmod=hashlib.sha1)


def base64_hmac(salt_value_key):
    """encodes hmac"""
    return b64_encode(salted_hmac(salt_value_key[0], salt_value_key[1],
                                  salt_value_key[2]).digest())


def signature(value):
    """adds signature"""
    return base64_hmac((settings.SALT + 'signer',
                        value, settings.SECRET_KEY))


def unsign(signed_value, max_age):
    """unsign the signature value"""
    if SEP not in signed_value:
        raise Exception('Bad signature - no "%s" found in value' % SEP)
    value, sig = signed_value.rsplit(SEP, 1)

    computed_sig = signature(value)

    if computed_sig != sig:
        raise Exception('Signatures do not match')

    value2, timestamp = value.rsplit(SEP, 1)

    decoded_timestamp = int(baseconv.base62.decode(timestamp))

    age = time.time() - decoded_timestamp
    if age > max_age:
        raise Exception('Expired')

    return value2


def load_encoded_s(unsigned_value):
    """Takes an unsigned value and decompresses and deserializes it."""
    if len(unsigned_value) == 0 or unsigned_value[0] != '.':
        raise Exception('Invalid unsigned value, "{0}", was expecting '
                        'something which starts with '
                        'a "."'.format(unsigned_value))
    data = b64_decode(unsigned_value[1:])
    data2 = zlib.decompress(data)
    return json.loads(data2)


def dict2signed(data):
    """Takes a dictionary and produces a signed compressed value."""
    b64d = '.' + b64_encode(
        zlib.compress(json.dumps(data, separators=(',', ':'))))

    value = '%s%s%s' % (b64d, ':', baseconv.base62.encode(int(time.time())))

    signed = '%s%s%s' % (value, ':', base64_hmac(
        (settings.SALT + 'signer', value, settings.SECRET_KEY)))

    return signed
