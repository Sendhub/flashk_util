# -*- coding: utf-8 -*-

"""
A small Flask module for adding CSRF protection.

:copyright: (c) 2010 by Steve Losh.
:license: MIT, see LICENSE for more details.

NB: Based on http://sjl.bitbucket.org/flask-csrf/ with subsequent modifications to suit SendHub's needs.

To allow custom CSRF header to be used in place of cookie or form post, set app.conf['CSRF_TOKEN'] to the header/cookie
name you want to use.
"""

import logging
from uuid import uuid4
from flask import abort, request, session, g
from werkzeug.routing import NotFound
import settings

_exemptViews = []


def csrfExempt(view):
    _exemptViews.append(view)
    return view


def csrf(app, onCsrf=None):
    csrfTokenKey = app.config.get('CSRF_TOKEN', 'CSRF-TOKEN')
    csrfTokenDomain = app.config.get('CSRF_TOKEN_DOMAIN', 'example.com')

    def searchCsrfInHeaders():
        """Searches through a set of key-value pairs for a CSRF token."""
        maybeHeader = filter(
            lambda tup: tup[0].lower() in (csrfTokenKey.lower(), 'x-{0}'.format(csrfTokenKey.lower())),
            request.headers
        )
        return maybeHeader[0][1] if maybeHeader and len(maybeHeader[0]) > 1 else None

    @app.before_request
    def _csrfCheckExemptions():
        try:
            dest = app.view_functions.get(request.endpoint)
            g._csrfExempt = dest in _exemptViews
        except NotFound:
            g._csrfExempt = False
    
    @app.before_request
    def _csrfProtect():
        # This simplifies unit testing, wherein CSRF seems to break.
        if app.config.get('TESTING'):
            return

        if not g._csrfExempt:
            # NB: Don't enforce CSRF if there was no referer.  This frees API clients from worrying about it but
            # enforces it for browser clients.
            if request.method in ('POST', 'PUT', 'PATCH', 'DELETE') and 'Referer' in request.headers:
                csrfToken = request.cookies.get(csrfTokenKey, None)
                if (not csrfToken and not searchCsrfInHeaders()) or \
                    (csrfToken != searchCsrfInHeaders() and csrfToken != request.form.get(csrfTokenKey, None)):
                    if onCsrf and callable(onCsrf):
                        logging.debug(u'Invoking custom CSRF failure handler')
                        onCsrf(*app.match_request())

                    logging.error(u'CSRF verification failed, aborting request')
                    abort(400)

    @app.after_request
    def _setCsrfCookie(response):
        """Set a CSRF cookie if one has been generated during this request."""
        if hasattr(request, csrfTokenKey):
            csrfToken = getattr(request, csrfTokenKey)
            logging.debug(u'Setting CSRF token in response cookie: {0}:{1}'.format(csrfTokenKey, csrfToken))
            response.set_cookie(csrfTokenKey, csrfToken, domain=csrfTokenDomain)
        return response
    
    def generateCsrfToken():
        if not hasattr(request, csrfTokenKey):
            # Prefer a pre-existing CSRF token when one is already in the cookie.
            csrfToken = request.cookies.get(csrfTokenKey, None) or str(uuid4())
            setattr(request, csrfTokenKey, csrfToken)
            logging.debug(u'Generated a new CSRF token: {0}'.format(csrfToken))
        return getattr(request, csrfTokenKey)
    
    app.jinja_env.globals['csrfToken'] = generateCsrfToken

