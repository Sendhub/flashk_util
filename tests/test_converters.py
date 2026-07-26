"""
Tests for flashk_util.converters.RegexConverter (a werkzeug URL map
converter allowing regex patterns in Flask routes, e.g.
``@app.route('/<regex("[0-9]+"):id>')``).

Note request.py defines an identical `RegexConverter` class; that copy is
exercised in test_request.py.
"""

from werkzeug.routing import Map

from flashk_util.converters import RegexConverter


def test_stores_regex_from_first_extra_arg():
    url_map = Map()
    conv = RegexConverter(url_map, r"[0-9]+")
    assert conv.regex == r"[0-9]+"


def test_is_a_base_converter_usable_in_flask_routing():
    """Full integration: register the converter on a real Flask app and
    confirm it actually constrains route matching as a regex would."""
    from flask import Flask

    app = Flask(__name__)
    app.url_map.converters["regex"] = RegexConverter

    @app.route('/items/<regex("[0-9]+"):item_id>')
    def get_item(item_id):
        return f"item:{item_id}"

    client = app.test_client()

    numeric = client.get("/items/42")
    assert numeric.status_code == 200
    assert numeric.data == b"item:42"

    non_numeric = client.get("/items/abc")
    assert non_numeric.status_code == 404


def test_multiple_extra_args_only_first_is_used_as_regex():
    url_map = Map()
    conv = RegexConverter(url_map, r"\d+", "ignored-second-arg")
    assert conv.regex == r"\d+"
