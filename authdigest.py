# -*- coding: utf-8 -*-

"""
The authdigest module contains classes to support
digest authentication compliant with RFC 2617.


Usage
=====

    from flashk_util.authdigest import RealmDigestDb

    authDb = RealmDigestDb('test-realm')
    authDb.add_user('admin', 'test')

    def protectedResource(environ, start_reponse):
        request = Request(environ)
        if not authDb.is_authenticated(request):
            return authDb.challenge()

        return get_protected_response(request)


Copyright and Licensing
=======================

This implementation is based on the "RealmDigestDB"
implementation by the Werkzeug Team/Shane Holloway.

    See: https://github.com/shanewholloway/werkzeug/
    blob/master/werkzeug/contrib/authdigest.py

which is
    :copyright: (c) 2010 by the Werkzeug Team, see AUTHORS for more details.
    :license: BSD, see LICENSE at https://github.com/shanewholloway/
    werkzeug/blob/master/LICENSE for further details.
"""

import json
import hashlib
import os
import weakref
import werkzeug


class RealmDigestDb:
    """
    Realm Digest Credentials Database

    Database mapping user to hashed password.

    Passwords are hashed using realm key, and specified digest algorithm.

    :param realm: string identifing the hashing realm.
    :param algorithm: string identifying hash algorithm to use,
    default is 'md5'.
    """

    def __init__(self, realm, algorithm='md5'):
        self.realm = realm
        self.alg = self.new_algorithm(algorithm)
        self._db = self.new_db()

    @property
    def algorithm(self):
        """Returns algorithm"""
        return self.alg.algorithm

    def to_dict(self):
        """To dict"""
        _r = {
            'cfg': {
                'algorithm': self.alg.algorithm,
                'realm': self.realm
            },
            'db': self._db
        }
        return _r

    def to_json(self, **kw):
        """To json"""
        kw.setdefault('sort_keys', True)
        kw.setdefault('indent', 2)
        return json.dumps(self.to_dict(), **kw)

    def add_user(self, user, password):
        """Adding user"""
        _r = self.alg.hash_password(user, self.realm, password)
        self._db[user] = _r
        return _r

    def __contains__(self, user):
        return user in self._db

    def get(self, user, default=None):
        """To get the user data"""
        return self._db.get(user, default)

    def __getitem__(self, user):
        return self._db.get(user)

    def __setitem__(self, user, password):
        return self.add_user(user, password)

    def __delitem__(self, user):
        return self._db.pop(user, None)

    @staticmethod
    def new_db():
        """Returns dict"""
        return dict()

    @staticmethod
    def new_algorithm(algorithm):
        """Returns DigestAuthentication obj"""
        return DigestAuthentication(algorithm)

    def is_authenticated(self, request, **kw):
        """Check for authentication"""
        auth_result = AuthenticationResult(self)
        request.authentication = auth_result

        authorization = request.authorization
        if authorization is None:
            return auth_result.deny('initial', False)
        authorization.result = auth_result

        hash_pass = self[authorization.username]
        if hash_pass is None:
            return auth_result.deny('unknown_user')
        if not self.alg.verify(authorization, hash_pass, request.method,
                               **kw):
            return auth_result.deny('invalid_password')
        return auth_result.approve('success')

    challengeClass = werkzeug.Response

    def challenge(self, response=None, status=401):
        """Sets headers to response"""
        try:
            auth_req = response.www_authenticate
        except AttributeError:
            response = self.challengeClass(response, status)
            auth_req = response.www_authenticate
        else:
            if isinstance(status, int):
                response.status_code = status
            else:
                response.status = status

        auth_req.set_digest(self.realm, os.urandom(8).encode('hex'))
        return response


class AuthenticationResult:
    """
    Authentication Result object

    Created by RealmDigestDb.is_authenticated to operate as a boolean result,
    and storage of authentication information.
    """
    authenticated = None
    reason = None
    status = 500

    def __init__(self, auth_db):
        self.auth_db = weakref.ref(auth_db)

    def __repr__(self):
        return '<authenticated: %r reason: %r>' % (
            self.authenticated, self.reason)

    def __bool__(self):
        return bool(self.authenticated)

    def deny(self, reason, authenticated=False):
        """Denied authentication"""
        if bool(authenticated):
            raise ValueError(
                'Denied authenticated parameter must evaluate as False')
        self.authenticated = authenticated
        self.reason = reason
        self.status = 401
        return self

    def approve(self, reason, authenticated=True):
        """Approves authentication"""
        if not bool(authenticated):
            raise ValueError(
                'Approved authenticated parameter must evaluate as True')
        self.authenticated = authenticated
        self.reason = reason
        self.status = 200
        return self

    def challenge(self, response=None, force=False):
        """Db challenge"""
        if force or not self:
            return self.auth_db().challenge(response, self.status)
        return None


class DigestAuthentication:
    """
    Digest Authentication Algorithm

    Digest Authentication implementation.

    references:
        "HTTP Authentication: Basic and Digest Access Authentication".
        RFC 2617. http://tools.ietf.org/html/rfc2617
        "Digest access authentication"
        http://en.wikipedia.org/wiki/Digest_access_authentication
    """

    def __init__(self, algorithm='md5'):
        self.algorithm = algorithm.lower()
        self._h = self.hashAlgorithms[self.algorithm]

    def verify(self, authorization, hash_pass=None, method='GET', **kw):
        """Verifies authorization"""
        req_response = self.digest(authorization, hash_pass, method, **kw)
        if req_response:
            return authorization.response.lower() == req_response.lower()
        return None

    def digest(self, authorization, hash_pass=None, method='GET', **kw):
        """check qop"""
        if authorization is None:
            return None

        if hash_pass is None:
            ha1 = self._compute_ha1(authorization, kw['password'])
        else:
            ha1 = hash_pass

        ha2 = self._compute_ha2(authorization, method)

        if 'auth' in authorization.qop:
            res = self._compute_qop_auth(authorization, ha1, ha2)
        elif not authorization.qop:
            res = self._compute_qop_empty(authorization, ha1, ha2)
        else:
            raise ValueError('Unsupported qop: %r' % (authorization.qop,))
        return res

    def hash_password(self, username, realm, password):
        """Password hashing"""
        return self._h(username, realm, password)

    def _compute_ha1(self, auth, password=None):
        return self.hash_password(auth.username, auth.realm,
                                  password or auth.password)

    def _compute_ha2(self, auth, method='GET'):
        return self._h(method, auth.uri)

    def _compute_qop_auth(self, auth, ha1, ha2):
        return self._h(ha1, auth.nonce, auth.nc, auth.cnonce, auth.qop, ha2)

    def _compute_qop_empty(self, auth, ha1, ha2):
        return self._h(ha1, auth.nonce, ha2)

    hashAlgorithms = {}

    @classmethod
    def add_digest_hash_alg(cls, key, hash_obj):
        """Adding hashing algorithms"""
        key = key.lower()

        def H(*args):  # pylint: disable=C0103
            _x = ':'.join(map(str, args))
            return hash_obj(_x).hexdigest()

        H.__name__ = 'H_' + key
        cls.hashAlgorithms[key] = H
        return H


DigestAuthentication.add_digest_hash_alg('md5', hashlib.md5)
DigestAuthentication.add_digest_hash_alg('sha', hashlib.sha1)
