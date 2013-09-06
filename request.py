__author__ = 'brock'

"""
Taken from:  https://gist.github.com/1094140
"""

from functools import wraps
from flask import request, current_app


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
        else:
            return func(*args, **kwargs)
    return decorated_function


def getParamAsInt(request, key, default):
    """
    Safely pulls a key from the request and converts it to an integer
    @param request: The HttpRequest object
    @param key: The key from request.args containing the desired value
    @param default: The value to return if the key does not exist
    @return: The value matching the key, or if it does not exist, the default value provided.
    """
    if key in request.args and request.args[key].isdigit():
        return int(request.args.get(key))
    else:
        return default

def getClientIP(request):

    if not request.headers.getlist("X-Forwarded-For"):
        ip = request.remote_addr
    else:
        ip = request.headers.getlist("X-Forwarded-For")[0]

    return ip