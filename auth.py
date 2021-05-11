# -*- coding: utf-8 -*-
""" authentication check"""
# pylint: disable=E0401,R0903
from functools import wraps
import flask
import authdigest


class FlaskRealmDigestDb(authdigest.RealmDigestDb):
    """Class to check authentication """
    def require_auth(self, func):
        """decorator function to check authentication"""
        @wraps(func)
        def decorated(*args, **kwargs):
            request = flask.request
            if not self.isAuthenticated(request):
                return self.challenge()

            return func(*args, **kwargs)

        return decorated
