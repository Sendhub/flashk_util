"""
request module
Taken from:  https://gist.github.com/1094140
"""
__author__ = 'brock'

from functools import wraps
from flask import request, current_app
from werkzeug.routing import BaseConverter
from werkzeug.exceptions import HTTPException


def jsonp(func):
    """Wraps JSONified output for JSONP requests."""

    @wraps(func)
    def decorated_function(*args, **kwargs):
        callback = request.args.get('callback', False)
        if callback:
            data = str(func(*args, **kwargs).data)
            content = str(callback) + '(' + data + ')'
            mimetype = 'application/javascript'
            return current_app.response_class(content, mimetype=mimetype)
        return func(*args, **kwargs)

    return decorated_function


def get_param_as_int(_request, key, default):
    """
    Safely pulls a key from the request and converts it to an integer
    @param _request: The HttpRequest object
    @param key: The key from request.args containing the desired value
    @param default: The value to return if the key does not exist
    @return: The value matching the key, or if it does not exist,
    the default value provided.
    """
    if key in _request.args and _request.args[key].isdigit():
        return int(_request.args.get(key))
    return default


def get_client_ip(_request):
    """
    Pull the requested client IP address from the X-Forwarded-For request
    header. If there is more than one IP address in the value, it will return
    the first one.

    For more info, see: 'def access_route' in
    https://github.com/mitsuhiko/werkzeug/blob/master/werkzeug/wrappers.py

    :param _request:
    :return str: The client IP address, or none if neither the X-Forwarded-For
       header, nor REMOTE_ADDR are present in the environment.
    """
    if _request.access_route:
        ip_addr = _request.access_route[0]
    else:
        ip_addr = None
    return ip_addr


class RegexConverter(BaseConverter):
    """class to convert the regex"""
    def __init__(self, url_map, *items):
        super().__init__(url_map)
        self.regex = items[0]


class ShHTTPException(HTTPException):
    """SendHub HTTPException"""
    def get_body(self, environ=None):
        """Get the HTML body."""
        return '%(description)s' % {
            'description': self.get_description(environ)}

    def get_headers(self, environ=None):
        """Always return errors as json"""
        return [('Content-Type', 'application/json')]


class BadRequest(ShHTTPException):
    """*400* `Bad Request`

    Raise if the browser sends something to the application the application
    or server cannot handle.
    """
    code = 400
    description = (
        '<p>The browser (or proxy) sent a request that this server could '
        'not understand.</p>'
    )


class Unauthorized(ShHTTPException):
    """*401* `Unauthorized`

    Raise if the user is not authorized.  Also used if you want to use HTTP
    basic auth.
    """
    code = 401
    description = (
        '<p>The server could not verify that you are authorized to access '
        'the URL requested.  You either supplied the wrong credentials (e.g. '
        'a bad password), or your browser doesn\'t understand how to supply '
        'the credentials required.</p><p>In case you are allowed to request '
        'the document, please check your user-id and password and try '
        'again.</p>'
    )


class Forbidden(ShHTTPException):
    """*403* `Forbidden`

    Raise if the user doesn't have the permission for the requested resource
    but was authenticated.
    """
    code = 403
    description = (
        '<p>You don\'t have the permission to access the requested resource. '
        'It is either read-protected or not readable by the server.</p>'
    )


class NotFound(ShHTTPException):
    """*404* `Not Found`

    Raise if a resource does not exist and never existed.
    """
    code = 404
    description = (
        '<p>The requested URL was not found on the server.</p>'
        '<p>If you entered the URL manually please check your spelling and '
        'try again.</p>'
    )


class Conflict(ShHTTPException):
    """*409* `Conflict`

    Raise to signal that a request cannot be completed because it conflicts
    with the current state on the server.

    .. versionadded:: 0.7
    """
    code = 409
    description = (
        '<p>A conflict happened while processing the request.  The resource '
        'might have been modified while the request was being processed.'
    )


class _NotImplemented(ShHTTPException):
    """*501* `Not Implemented`

    Raise if the application does not support the action requested by the
    browser.
    """
    code = 501
    description = (
        '<p>The server does not support the action requested by the '
        'browser.</p>'
    )


def paginate(_request, objects, total, _offset, _limit):
    """Function to return the pagination response"""
    def get_url(_offset, _limit):
        return '{}?&offset={}&limit={}'.format(_request.path, _offset, _limit)

    response = {
        'meta': {
            'total': total,
            'limit': _limit,
            'next': get_url(_offset + _limit, _limit)
            if _offset + _limit < total else None,
            'previous': get_url(_offset - _limit, _limit)
            if _offset - _limit >= 0 else None,
            'offset': _offset,
        },
        'objects': objects
    }

    return response
