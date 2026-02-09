"""
Authentication check.
"""

import authdigest


class FlaskRealmDigestDb(authdigest.RealmDigestDb):
    """
    Class to check authentication.
    """

    def require_auth(self, func):
        """
        Decorator function to check authentication.
        """
        # Moved to function level to avoid potential circular imports

        from functools import wraps

        import flask

        @wraps(func)
        def decorated(*args, **kwargs):
            request = flask.request
            if not self.isAuthenticated(request):
                return self.challenge()

            return func(*args, **kwargs)

        return decorated
