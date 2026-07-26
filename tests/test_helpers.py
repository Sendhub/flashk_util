"""
Tests for flashk_util.helpers: jsonify, get_view_window_params, csvify.
"""

import pytest
from flask import Flask

import flashk_util.helpers as helpers


@pytest.fixture
def helpers_app():
    flask_app = Flask(__name__)
    flask_app.config.update(SECRET_KEY="test", TESTING=True)
    return flask_app


# ---------------------------------------------------------------------------
# jsonify
# ---------------------------------------------------------------------------


def test_jsonify_pretty_prints_by_default(helpers_app):
    with helpers_app.test_request_context("/"):
        resp = helpers.jsonify(a=1, b="x")

    assert resp.mimetype == "application/json"
    assert resp.get_data() == b'{\n    "a": 1,\n    "b": "x"\n}'


def test_jsonify_compact_for_xhr_requests(helpers_app):
    with helpers_app.test_request_context("/", headers={"X-Requested-With": "XMLHttpRequest"}):
        resp = helpers.jsonify(a=1)

    assert resp.get_data() == b'{"a": 1}'


def test_jsonify_status_code_override(helpers_app):
    with helpers_app.test_request_context("/"):
        resp = helpers.jsonify(a=1, status_code=201)

    assert resp.status_code == 201


def test_jsonify_default_status_code_is_200(helpers_app):
    with helpers_app.test_request_context("/"):
        resp = helpers.jsonify(a=1)

    assert resp.status_code == 200


def test_jsonify_uses_default_encoder_for_datetime(helpers_app):
    import datetime

    with helpers_app.test_request_context("/", headers={"X-Requested-With": "XMLHttpRequest"}):
        resp = helpers.jsonify(when=datetime.datetime(1970, 1, 1, 0, 0, 1))

    # default_encoder converts datetimes to milliseconds-since-epoch strings.
    assert resp.get_data() == b'{"when": "1000"}'


# ---------------------------------------------------------------------------
# get_view_window_params
# ---------------------------------------------------------------------------


def test_get_view_window_params_reads_all_provided_query_args(helpers_app):
    with helpers_app.test_request_context("/?offset=5&limit=25&sort=name&order=asc"):
        offset, limit, sort, order = helpers.get_view_window_params("offset", "limit", "sort", "order")

    assert (offset, limit, sort, order) == (5, 25, "name", "asc")


def test_get_view_window_params_defaults(helpers_app, monkeypatch):
    import settings

    monkeypatch.setattr(settings, "pagingDefaultLimit", 10, raising=False)

    with helpers_app.test_request_context("/"):
        offset, limit, sort, order = helpers.get_view_window_params("offset", "limit", "sort", "order")

    assert offset == 0
    assert limit == 10
    assert sort is None
    assert order == "desc"


def test_get_view_window_params_non_digit_limit_falls_back_to_default(helpers_app, monkeypatch):
    import settings

    monkeypatch.setattr(settings, "pagingDefaultLimit", 10, raising=False)

    with helpers_app.test_request_context("/?limit=notanumber"):
        (limit,) = helpers.get_view_window_params("limit")

    assert limit == 10


def test_get_view_window_params_rejects_unknown_param_name(helpers_app):
    with helpers_app.test_request_context("/"):
        with pytest.raises(AssertionError, match='Requested parameter "bogus" is not available'):
            helpers.get_view_window_params("bogus")


def test_get_view_window_params_single_param_returns_single_element_list(helpers_app):
    with helpers_app.test_request_context("/?sort=email"):
        result = helpers.get_view_window_params("sort")

    assert result == ["email"]


# ---------------------------------------------------------------------------
# csvify
# ---------------------------------------------------------------------------


def test_csvify_produces_expected_body_and_mimetype(helpers_app):
    @helpers_app.route("/csv")
    def csv_route():
        return helpers.csvify(
            headers=["date", "message"],
            rows=[
                {"date": "2020-01-01", "message": 'hi "there"'},
                {"date": "2020-01-02", "message": None},
            ],
        )

    client = helpers_app.test_client()
    resp = client.get("/csv")

    assert resp.mimetype == "text/csv"
    assert resp.data == b'date ,message\n"2020-01-01","hi ""there"""\n"2020-01-02",""\n'


def test_csvify_as_download_sets_content_disposition(helpers_app):
    @helpers_app.route("/csv")
    def csv_route():
        return helpers.csvify(headers=["a"], rows=[{"a": "1"}], as_download=True, filename="export.csv")

    client = helpers_app.test_client()
    resp = client.get("/csv")

    assert resp.headers.get("Content-Disposition") == "attachment;filename=export.csv"


def test_csvify_without_as_download_has_no_content_disposition(helpers_app):
    @helpers_app.route("/csv")
    def csv_route():
        return helpers.csvify(headers=["a"], rows=[{"a": "1"}])

    client = helpers_app.test_client()
    resp = client.get("/csv")

    assert "Content-Disposition" not in resp.headers


def test_csvify_missing_key_becomes_empty_string(helpers_app):
    @helpers_app.route("/csv")
    def csv_route():
        return helpers.csvify(headers=["a", "b"], rows=[{"a": "1"}])  # "b" missing entirely

    client = helpers_app.test_client()
    resp = client.get("/csv")

    assert resp.data == b'a ,b\n"1",""\n'


def test_csvify_normalizes_unicode_and_drops_non_ascii(helpers_app):
    @helpers_app.route("/csv")
    def csv_route():
        return helpers.csvify(headers=["name"], rows=[{"name": "café"}])

    client = helpers_app.test_client()
    resp = client.get("/csv")

    # unicodedata.normalize("NFKD", ...).encode("ascii", "ignore") drops the
    # combining accent entirely, leaving plain "cafe".
    assert resp.data == b'name\n"cafe"\n'


def test_csvify_requires_at_least_one_header(helpers_app):
    with helpers_app.test_request_context("/"):
        with pytest.raises(AssertionError, match="Cannot write CSV without Headers"):
            helpers.csvify(headers=[], rows=[])
