from builtins import str
from flask import jsonify
from werkzeug.exceptions import HTTPException
from werkzeug.exceptions import default_exceptions


def make_json_error(ex):
    """
    Create a json response from an Exception. If the exception is an
    HTTPException, the response.status_code will be that of the
    HTTPException, otherwise it will be 500.
    :param ex:Exception instance
    :return:json response
    """

    if isinstance(ex, HTTPException):
        response = jsonify(message=str(ex), code=ex.code)
    else:
        response = jsonify(message=str(ex))

    response.status_code = (ex.code if isinstance(ex, HTTPException) else 500)
    return response


def configure_flask_exception_handler(app):
    """
    Set the exception handler for the default flask exceptions
    to return the expected json response.
    :param app:The flask app instance
    :return:
    """

    for code in list(default_exceptions.keys()):
        app.error_handler_spec[None][code] = make_json_error