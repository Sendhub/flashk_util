# -*- coding: utf-8 -*-

from flask import request
from flask.globals import current_app
import simplejson as json
from sh_util.json import defaultEncoder

def jsonify(*args, **kwargs):
    """Creates a :class:`~flask.Response` with the JSON representation of
    the given arguments with an `application/json` mimetype.  The arguments
    to this function are the same as to the :class:`dict` constructor.

    Example usage::

        @app.route('/_get_current_user')
        def get_current_user():
            return jsonify(username=g.user.username,
                           email=g.user.email,
                           id=g.user.id)

    This will send a JSON response like this to the browser::

        {
            "username": "admin",
            "email": "admin@localhost",
            "id": 42
        }

    This requires Python 2.6 or an installed version of simplejson.  For
    security reasons only objects are supported toplevel.  For more
    information about this, have a look at :ref:`json-security`.

    .. versionadded:: 0.2
    """
    status_code = kwargs.pop('status_code', None)

    response = current_app.response_class(
        json.dumps(
            dict(*args, **kwargs),
            indent=None if request.is_xhr else 4,
            default=defaultEncoder
        ),
        mimetype='application/json'
    )

    if status_code is not None:
        response.status_code = status_code

    return response

