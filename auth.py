# -*- coding: utf-8 -*-

from functools import wraps
import flask
from . import authdigest

class FlaskRealmDigestDb(authdigest.RealmDigestDb):
    def requireAuth(self, f):
        @wraps(f)
        def decorated(*args, **kwargs):
            request = flask.request
            if not self.isAuthenticated(request):
                return self.challenge()

            return f(*args, **kwargs)

        return decorated

