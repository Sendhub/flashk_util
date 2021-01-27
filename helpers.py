# -*- coding: utf-8 -*-
# pylint: disable=E0401, E1101
"""Flask utilities and generalized helper functionality."""

import unicodedata
import simplejson as json
import settings
from flask import request
from flask.globals import current_app
from werkzeug.datastructures import Headers
from sh_util.json import default_encoder



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
            default=default_encoder
        ),
        mimetype='application/json'
    )

    if status_code is not None:
        response.status_code = status_code

    return response


def get_view_window_params(*params):
    """Convenience method to access `offset`, `limit`, `sort`,
    and `order` request result set specifiers."""
    out = []
    for param in params:
        assert param in ('offset', 'limit', 'sort',
                         'order'), 'Requested parameter "{0}" ' \
                                   'is not available'.format(param)
        value = None
        if param == 'offset':
            if param in request.args and request.args[param].isdigit():
                offset_value = request.args.get(param)
            else:
                offset_value = 0
            value = int(offset_value)

        elif param == 'limit':
            if param in request.args and request.args[param].isdigit():
                limit_value = request.args.get(param)
            else:
                limit_value = settings.pagingDefaultLimit
            value = int(limit_value)

        elif param == 'sort':
            value = request.args.get(param) if param in request.args else None

        elif param == 'order':
            value = request.args.get(
                param) if param in request.args else 'desc'
        out.append(value)
    return out


def _escape_quotes(key, _dict):
    """
    Safely escape quotes of each item that goes in a row
    @param key: The key of the dictionary to pull from.
    @param _dict: The target dictionary holding the data
    @return:
    """
    value = _dict.get(key, '')
    # if the key exists but has a None value, just use the empty string.
    value = value if value is not None else ''
    value = value if isinstance(value, str) else str(value)
    value = value.replace('"', '""')
    return value


def csvify(*_args, **kwargs):
    """
    Creates a :class:`~flask.Response` with the CSV representation
    of the given arguments with an `text/csv` mimetype.

    Example usage::
        @app.route('/_get_logs')
        def get_current_user():
            return csvify(
                as_download=True,
                headers=['date', 'message'],
                rows=[
                    {
                        'date': '2012-12-12',
                        'message': 'foo'
                    },
                    {
                        'date': '2011-11-11',
                        'message': 'bar'
                    },
                ]
            )

    This will send a CSV file response like this to the client::

        date,message
        2012-12-12,foo
        2011-11-11,bar
    """
    headers = [str(header) for header in kwargs.pop('headers', [])]
    assert len(headers) > 0, 'Cannot write CSV without Headers!'
    rows = kwargs.pop('rows', [])

    def generate_csv():
        """Write the header and the iterate over the rows."""
        ####################################################################
        # write the header
        yield '{}\n'.format(','.join(headers))
        ####################################################################
        # Write the body of the document
        # ----> First generate the format string reused for each row in the csv
        #       file such that row_string = '{},{},{},{},...\n'
        row_string = '{}\n'.format(','.join(['"{}"' for _header in headers]))
        # ---> Then use that format string as the output to the next row
        for row in rows:
            # Get a value for each header, making sure to escape quotes and
            # normalize for unicode along the way
            csv_line = [_escape_quotes(header, row) for header in headers]
            csv_line = row_string.format(*csv_line)
            yield unicodedata.normalize('NFKD', csv_line).encode('ascii',
                                                                 'ignore')

    filename = kwargs.pop('filename', 'file.csv')
    as_download = kwargs.pop('as_download', False)
    response_headers = None
    if as_download:
        response_headers = Headers([('Content-Disposition',
                                     "attachment;filename={filename}".format(
                                         filename=filename))])

    return current_app.response_class(generate_csv(), mimetype='text/csv',
                                      headers=response_headers)
