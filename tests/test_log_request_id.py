"""
Tests for flashk_util.log_request_id.RequestIDFilter.
"""

import logging

from flashk_util.log_request_id import RequestIDFilter


def _make_record():
    return logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello",
        args=(),
        exc_info=None,
    )


def test_get_unique_id_outside_request_context_returns_none():
    """No active Flask request context -> accessing `flask.request` raises
    RuntimeError, which get_unique_id() catches and turns into None."""
    assert RequestIDFilter.get_unique_id() is None


def test_get_unique_id_returns_header_value_within_request_context(app):
    with app.test_request_context("/", headers={"X-Request-Id": "req-xyz"}):
        assert RequestIDFilter.get_unique_id() == "req-xyz"


def test_get_unique_id_returns_none_when_header_absent(app):
    with app.test_request_context("/"):
        assert RequestIDFilter.get_unique_id() is None


def test_filter_sets_request_id_from_header(app):
    with app.test_request_context("/", headers={"X-Request-Id": "req-xyz"}):
        record = _make_record()
        result = RequestIDFilter().filter(record)

    assert result is True
    assert record.request_id == "req-xyz"


def test_filter_defaults_to_blank_outside_request_context():
    record = _make_record()
    result = RequestIDFilter().filter(record)

    assert result is True
    assert record.request_id == ""


def test_filter_defaults_to_blank_when_header_absent(app):
    with app.test_request_context("/"):
        record = _make_record()
        RequestIDFilter().filter(record)

    assert record.request_id == ""
