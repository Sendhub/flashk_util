# -*- coding: utf-8 -*-

import base64, hmac, hashlib, time, settings, re, zlib, simplejson as json
from . import baseconv

sep = ':'

b64_encode = lambda s: base64.urlsafe_b64encode(s).strip('=')

b64_decode = lambda s: base64.urlsafe_b64decode(s + ('=' * (-len(s) % 4))) # s + padding

def salted_hmac(key_salt, value, secret):
    return hmac.new(hashlib.sha1(key_salt + secret).digest(), msg=value, digestmod=hashlib.sha1)

base64_hmac = lambda (salt, value, key): b64_encode(salted_hmac(salt, value, key).digest())

signature = lambda value: base64_hmac((settings.SALT + 'signer', value, settings.SECRET_KEY))

#_signedValueCleanerRe = re.compile(r'''"?(.*)"?''')

def unsign(signed_value, max_age):
    #signed_value = _signedValueCleanerRe.sub(r'\1', signed_value)
    if sep not in signed_value:
        raise Exception('Bad signature - no "%s" found in value' % sep)
    value, sig = signed_value.rsplit(sep, 1)

    #print 'value=%s, sig=%s' % (value, sig)
    computed_sig = signature(value)

    if computed_sig != sig:
        raise Exception('Signatures do not match')

    #print 'computed_sig=%s' % computed_sig

    value2, timestamp = value.rsplit(sep, 1)

    decoded_timestamp = int(baseconv.base62.decode(timestamp))
    #print 'timestamp=%s, decoded_timestamp=%s' % (timestamp, decoded_timestamp)

    age = time.time() - decoded_timestamp
    if age > max_age:
        raise Exception('Expired')

    return value2

def loadEncodedS(unsigned_value):
    """Takes an unsigned value and decompresses and deserializes it."""
    import zlib, simplejson as json
    if len(unsigned_value) is 0 or unsigned_value[0] != '.':
        raise Exception(
            'Invalid unsigned value, "{0}", was expecting something which starts with a "."'.format(unsigned_value)
        )
    data = b64_decode(unsigned_value[1:])
    #print 'data=%s' % data
    data2 = zlib.decompress(data)
    #print 'data2=%s' % data2
    return json.loads(data2)


def dict2signed(data):
    """Takes a dictionary and produces a signed compressed value."""
    b64d = '.' + b64_encode(zlib.compress(json.dumps(data, separators=(',', ':'))))

    value = '%s%s%s' % (b64d, ':', baseconv.base62.encode(int(time.time())))

    signed = '%s%s%s' % (value, ':', base64_hmac((settings.SALT + 'signer', value, settings.SECRET_KEY)))

    return signed


