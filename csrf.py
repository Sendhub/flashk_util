"""
A small Flask module for adding CSRF protection.

:copyright: (c) 2010 by Steve Losh.
:license: MIT, see LICENSE for more details.

NB: Based on http://sjl.bitbucket.org/flask-csrf/ with subsequent modifications to suit SendHub's needs.

To allow custom CSRF header to be used in place of cookie or form post, set app.conf['CSRF_TOKEN'] to the header/cookie name you want to use.
"""

import logging

from flask import abort, g, request

_exemptViews = []


def csrf_exempt(view):
    """
    Exempt view from CSRF protection.
    """
    _exemptViews.append(view)
    return view


def csrf(app, on_csrf=None):
    """
    Group the CSRF token generation.
    """
    csrf_token_key = app.config.get("CSRF_TOKEN", "CSRF-TOKEN")
    csrf_token_domain = app.config.get("CSRF_TOKEN_DOMAIN", None)

    internal_username = app.config.get("INTERNAL_USERNAME", "")
    internal_password = app.config.get("INTERNAL_PASSWORD", "")

    def request_has_valid_credentials():
        """Check if request includes valid query parameter credentials."""
        if not internal_username or not internal_password:
            return False

        api_username = request.args.get("apiUsername", "").strip()
        api_password = request.args.get("apiPassword", "").strip()

        if api_username == internal_username and api_password == internal_password:
            logging.debug("CSRF exempted via valid query parameter credentials")
            return True

        return False

    def search_csrf_in_headers():
        """
        Search through a set of key-value pairs for a CSRF token.
        """
        maybe_header = [tup for tup in request.headers if tup[0].lower() in (csrf_token_key.lower(), f"x-{csrf_token_key.lower()}")]
        return maybe_header[0][1] if maybe_header and len(maybe_header[0]) > 1 else None

    @app.before_request
    def _csrf_check_exemptions():
        """
        Check CSRF exemptions.
        """
        # Moved to function level - only used here
        from werkzeug.exceptions import NotFound

        try:
            dest = app.view_functions.get(request.endpoint)
            g.csrf_exempt = dest in _exemptViews
        except NotFound:
            g.csrf_exempt = False

    @app.before_request
    def _csrf_protect():
        """
        CSRF protection method.
        """
        # This simplifies unit testing, wherein CSRF seems to break.
        if app.config.get("TESTING"):
            return

        if not g.csrf_exempt:
            # NB: Do not enforce CSRF if there was no referer.
            # This frees API clients from worrying about it but
            # enforces it for browser clients.
            if request.method in ("POST", "PUT", "PATCH", "DELETE"):
                csrf_token = request.cookies.get(csrf_token_key, None)
                if (not csrf_token and not search_csrf_in_headers()) or (csrf_token != search_csrf_in_headers() and csrf_token != request.form.get(csrf_token_key, None)):

                    if request_has_valid_credentials():
                        return

                    if on_csrf and callable(on_csrf):
                        logging.debug("Invoking custom CSRF failure handler")
                        on_csrf(*app.match_request())

                    logging.error("CSRF verification failed, aborting request")
                    abort(400)

    @app.after_request
    def _set_csrf_cookie(response):
        """Set a CSRF cookie if one has been generated during this request."""
        if hasattr(request, csrf_token_key):
            csrf_token = getattr(request, csrf_token_key)
            crsf_token_debug = f"Setting CSRF token in response cookie: {csrf_token_key}:{csrf_token}"
            logging.debug(crsf_token_debug)
            maybe_csrf_domain = {"domain": csrf_token_domain} if csrf_token_domain is not None else {}
            response.set_cookie(csrf_token_key, csrf_token, **maybe_csrf_domain)
        return response

    def generate_csrf_token():
        """Generate a CSRF token"""
        if not hasattr(request, csrf_token_key):
            # Prefer a pre-existing CSRF token when
            # one is already in the cookie.
            from uuid import uuid4

            csrf_token = request.cookies.get(csrf_token_key, None) or str(uuid4())
            setattr(request, csrf_token_key, csrf_token)
            new_csrf_token = f"Generated a new CSRF token: {csrf_token}"
            logging.debug(new_csrf_token)
        return getattr(request, csrf_token_key)

    app.jinja_env.globals["csrfToken"] = generate_csrf_token
