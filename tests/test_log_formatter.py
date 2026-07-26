"""
Tests for flashk_util.log_formatter.ShLoggingFormatter.
"""

import logging

from flashk_util.log_formatter import ShLoggingFormatter


def _make_record(msg="hello world", **extra):
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=msg,
        args=(),
        exc_info=None,
    )
    for key, value in extra.items():
        setattr(record, key, value)
    return record


def test_no_ids_present_leaves_message_unchanged():
    formatter = ShLoggingFormatter("%(message)s")
    record = _make_record("plain message")

    assert formatter.format(record) == "plain message"


def test_request_id_is_prepended_when_present():
    formatter = ShLoggingFormatter("%(message)s")
    record = _make_record("plain message", request_id="req-123")

    assert formatter.format(record) == "req-123 plain message"


def test_task_id_is_prepended_when_present():
    formatter = ShLoggingFormatter("%(message)s")
    record = _make_record("plain message", task_id="task-456")

    assert formatter.format(record) == "task-456 plain message"


def test_request_id_takes_precedence_over_task_id():
    formatter = ShLoggingFormatter("%(message)s")
    record = _make_record("plain message", request_id="req-123", task_id="task-456")

    assert formatter.format(record) == "req-123 plain message"


def test_empty_string_id_is_treated_as_absent():
    formatter = ShLoggingFormatter("%(message)s")
    record = _make_record("plain message", request_id="")

    assert formatter.format(record) == "plain message"


def test_literal_none_string_id_is_treated_as_absent():
    """`_should_show_attr` explicitly excludes the string 'none' (as would
    result from naively str()-ing a Python None onto a record)."""
    formatter = ShLoggingFormatter("%(message)s")
    record = _make_record("plain message", request_id="none")

    assert formatter.format(record) == "plain message"


def test_should_show_attr_static_method_directly():
    record = _make_record(request_id="abc")
    assert ShLoggingFormatter._should_show_attr(record, "request_id") is True
    assert ShLoggingFormatter._should_show_attr(record, "task_id") is False


def test_only_first_occurrence_of_message_is_prefixed():
    """If the log message text happens to repeat verbatim elsewhere in the
    formatted line, only the first occurrence (the actual message) gets the
    id prefix -- `_s.replace(..., 1)` limits to one substitution."""
    formatter = ShLoggingFormatter("%(message)s | %(message)s")
    record = _make_record("dup", request_id="rid")

    assert formatter.format(record) == "rid dup | dup"


def test_format_with_args_interpolation():
    formatter = ShLoggingFormatter("%(message)s")
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="value is %s",
        args=("42",),
        exc_info=None,
    )
    record.request_id = "rid"

    assert formatter.format(record) == "rid value is 42"
