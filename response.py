"""
Response module.
"""

from flask import jsonify
from werkzeug.exceptions import HTTPException, default_exceptions


def make_json_error(ex):
    """
    Create a JSON response from an Exception. If the exception is an HTTPException, the response.status_code will be that of the HTTPException, otherwise it will be 500.
    Args:
        ex: Exception instance.
    Returns:
        JSON response.
    """

    if isinstance(ex, HTTPException):
        response = jsonify(message=str(ex), code=ex.code)
    else:
        response = jsonify(message=str(ex))

    response.status_code = ex.code if isinstance(ex, HTTPException) else 500
    return response


def configure_flask_exception_handler(app):
    """
    Set the exception handler for the default flask exceptions to return the expected JSON response.
    Args:
        app: The flask app instance.
    """
    for code in list(default_exceptions.keys()):
        if None in app.error_handler_spec:
            app.error_handler_spec[None][code] = make_json_error
        else:
            app.error_handler_spec[None] = {}
            app.error_handler_spec[None][code] = make_json_error
