"""
Tests for flashk_util.request: jsonp decorator, request-arg helpers,
SendHub HTTPException subclasses, and paginate().
"""

import json

import pytest
from flask import Flask
from werkzeug.routing import Map

from flashk_util.request import (
    BadRequest,
    Conflict,
    Forbidden,
    NotFound,
    RegexConverter,
    ShHTTPException,
    Unauthorized,
    _NotImplemented,
    get_client_ip,
    get_param_as_int,
    jsonp,
    paginate,
)

# ---------------------------------------------------------------------------
# jsonp
# ---------------------------------------------------------------------------


def _jsonp_app():
    app = Flask(__name__)
    app.config.update(SECRET_KEY="test", TESTING=True)

    @app.route("/data")
    @jsonp
    def data():
        from flask import jsonify

        return jsonify(value=42)

    return app


def test_jsonp_wraps_response_when_callback_param_present():
    """POSSIBLE BUG (documented, not fixed): `jsonp` builds the wrapped body
    via `data = str(func(*args, **kwargs).data)`. `.data` on a Flask
    response is `bytes`, and `str(some_bytes)` produces Python's bytes
    *repr* (e.g. `"b'{\"value\":42}\\n'"`), not the decoded text. The
    resulting JSONP body is therefore not valid, executable JavaScript --
    a browser would hit a SyntaxError on the stray `b'...'` wrapper -- even
    though the endpoint returns 200 with the "correct" `application/
    javascript` mimetype. This test documents the actual (buggy) body
    shape rather than the intended one.
    """
    client = _jsonp_app().test_client()
    resp = client.get("/data?callback=myCallback")

    assert resp.status_code == 200
    assert resp.mimetype == "application/javascript"
    body = resp.data.decode()
    assert body == 'myCallback(b\'{"value":42}\\n\')'


def test_jsonp_passes_through_unwrapped_without_callback_param():
    client = _jsonp_app().test_client()
    resp = client.get("/data")

    assert resp.status_code == 200
    assert resp.mimetype == "application/json"
    assert resp.get_json() == {"value": 42}


# ---------------------------------------------------------------------------
# get_param_as_int
# ---------------------------------------------------------------------------


def test_get_param_as_int_returns_int_for_digit_param(app):
    with app.test_request_context("/?limit=25"):
        from flask import request

        assert get_param_as_int(request, "limit", 10) == 25


def test_get_param_as_int_returns_default_when_missing(app):
    with app.test_request_context("/"):
        from flask import request

        assert get_param_as_int(request, "limit", 10) == 10


def test_get_param_as_int_returns_default_when_non_digit(app):
    with app.test_request_context("/?limit=abc"):
        from flask import request

        assert get_param_as_int(request, "limit", 10) == 10


def test_get_param_as_int_rejects_negative_looking_values_as_non_digit(app):
    """`str.isdigit()` is False for a leading '-', so a "negative" query
    param falls back to the default rather than becoming a negative int."""
    with app.test_request_context("/?limit=-5"):
        from flask import request

        assert get_param_as_int(request, "limit", 10) == 10


# ---------------------------------------------------------------------------
# get_client_ip
# ---------------------------------------------------------------------------


def test_get_client_ip_uses_first_entry_of_x_forwarded_for(app):
    with app.test_request_context("/", headers={"X-Forwarded-For": "1.2.3.4, 5.6.7.8"}):
        from flask import request

        assert get_client_ip(request) == "1.2.3.4"


def test_get_client_ip_falls_back_to_remote_addr(app):
    with app.test_request_context("/", environ_base={"REMOTE_ADDR": "9.9.9.9"}):
        from flask import request

        assert get_client_ip(request) == "9.9.9.9"


def test_get_client_ip_returns_none_when_no_route_info(app):
    with app.test_request_context("/"):
        from flask import request

        assert get_client_ip(request) is None


# ---------------------------------------------------------------------------
# RegexConverter
# ---------------------------------------------------------------------------


def test_regex_converter_stores_pattern():
    conv = RegexConverter(Map(), r"[a-z]+")
    assert conv.regex == r"[a-z]+"


# ---------------------------------------------------------------------------
# ShHTTPException subclasses
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "exc_class,code",
    [
        (BadRequest, 400),
        (Unauthorized, 401),
        (Forbidden, 403),
        (NotFound, 404),
        (Conflict, 409),
        (_NotImplemented, 501),
    ],
)
def test_exception_classes_have_expected_codes(exc_class, code):
    assert exc_class.code == code
    assert issubclass(exc_class, ShHTTPException)


def test_sh_http_exception_get_body_returns_raw_description(app):
    """get_body() must return the description as-is, NOT routed through
    get_description() — the werkzeug default HTML-escapes and <p>-wraps it,
    which breaks JSON parsing for callers even though get_headers() declares
    Content-Type: application/json."""
    with app.test_request_context("/"):
        err = NotFound()
        assert err.get_body() == err.description
        assert err.get_body() != err.get_description()


def test_sh_http_exception_get_body_preserves_json_description(app):
    """A JSON-serialized description (e.g. from ErrorResponse) must survive
    get_body() unescaped and unwrapped, so callers expecting
    Content-Type: application/json get an actually-parseable body."""
    with app.test_request_context("/"):
        payload = {"message": "trial-over", "dev_message": "", "code": "", "more_info": ""}
        err = NotFound(json.dumps(payload))
        body = err.get_body()
        assert body == json.dumps(payload)
        assert json.loads(body) == payload


def test_sh_http_exception_get_body_handles_none_description(app):
    with app.test_request_context("/"):
        err = NotFound()
        err.description = None
        assert err.get_body() == ""


def test_sh_http_exception_get_headers_forces_json_content_type(app):
    with app.test_request_context("/"):
        err = BadRequest()
        headers = err.get_headers()
        assert headers == [("Content-Type", "application/json")]


def test_sh_http_exception_is_raisable_and_catchable():
    with pytest.raises(NotFound):
        raise NotFound()


# ---------------------------------------------------------------------------
# paginate
# ---------------------------------------------------------------------------


def test_paginate_middle_page_has_both_next_and_previous(app):
    with app.test_request_context("/things"):
        from flask import request

        result = paginate(request, objects=["a", "b"], total=10, _offset=4, _limit=2)

    assert result["objects"] == ["a", "b"]
    assert result["meta"]["total"] == 10
    assert result["meta"]["limit"] == 2
    assert result["meta"]["offset"] == 4
    assert result["meta"]["next"] == "/things?&offset=6&limit=2"
    assert result["meta"]["previous"] == "/things?&offset=2&limit=2"


def test_paginate_first_page_has_no_previous(app):
    with app.test_request_context("/things"):
        from flask import request

        result = paginate(request, objects=[], total=10, _offset=0, _limit=2)

    assert result["meta"]["previous"] is None
    assert result["meta"]["next"] == "/things?&offset=2&limit=2"


def test_paginate_last_page_has_no_next(app):
    with app.test_request_context("/things"):
        from flask import request

        result = paginate(request, objects=[], total=4, _offset=2, _limit=2)

    assert result["meta"]["next"] is None
    assert result["meta"]["previous"] == "/things?&offset=0&limit=2"
