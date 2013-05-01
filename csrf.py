# -*- coding: utf-8 -*-

"""
A small Flask module for adding CSRF protection.

:copyright: (c) 2010 by Steve Losh.
:license: MIT, see LICENSE for more details.

NB: Based on http://sjl.bitbucket.org/flask-csrf/ with subsequent modifications to suit SendHub's needs.

To allow custom CSRF header to be used in place of cookie or form post, set app.conf['CSRF_HEADER'] to the header name
you want to use.
"""

import logging
from uuid import uuid4
from flask import abort, request, session, g
from werkzeug.routing import NotFound

_exemptViews = []


def csrfExempt(view):
    _exemptViews.append(view)
    return view


def csrf(app, onCsrf=None):
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
                maybeHeader = filter(lambda tup: tup[0].lower() == app.config['CSRF_HEADER'].lower(), request.headers) \
                    if 'CSRF_HEADER' in app.config else tuple()

                csrfToken = request.cookies.get('_csrfToken', None)

                if not csrfToken or ((not maybeHeader or len(maybeHeader[0]) < 2 or csrfToken != maybeHeader[0][1]) and
                    csrfToken != request.form.get('_csrfToken', None)):
                    if onCsrf and callable(onCsrf):
                        logging.debug(u'Invoking custom CSRF failure handler')
                        onCsrf(*app.match_request())

                    logging.error(u'CSRF verification failed, aborting request')
                    abort(400)

    @app.after_request
    def _setCsrfCookie(response):
        """Set a CSRF cookie if one has been generated during this request."""
        if hasattr(request, '_csrfToken'):
            logging.debug(u'Setting the CSRF token in a cookie of the response')
            response.set_cookie('_csrfToken', request._csrfToken)
        return response
        
    
    def generateCsrfToken():
        if not hasattr(request, '_csrfToken'):
            request._csrfToken = str(uuid4())
            logging.debug(u'Generated a new CSRF token: {0}'.format(request._csrfToken))
        return request._csrfToken
    
    app.jinja_env.globals['csrfToken'] = generateCsrfToken

