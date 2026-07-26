"""
Tests for flashk_util.serving.ShRequestHandler.

`ShRequestHandler` subclasses `socketserver.BaseRequestHandler` (via
werkzeug's `WSGIRequestHandler`), whose `__init__` normally performs real
socket I/O (`setup()`/`handle()`/`finish()` are invoked automatically from
`__init__` against a live connection). To unit test the handler's own
timing/logging logic in isolation, instances are constructed via
`object.__new__` (bypassing `__init__` entirely) and the werkzeug parent
class's `handle`/`send_response`/`log` methods are patched out.
"""

import time
from unittest import mock

import serving


def _make_handler():
    handler = object.__new__(serving.ShRequestHandler)
    handler.sh_request_started = None
    handler.sh_request_processed = None
    handler.requestline = "GET /foo HTTP/1.1"
    return handler


def test_init_sets_timestamps_to_none():
    handler = object.__new__(serving.ShRequestHandler)
    with mock.patch.object(serving.WSGIRequestHandler, "__init__", return_value=None):
        handler.__init__()
    assert handler.sh_request_started is None
    assert handler.sh_request_processed is None


def test_handle_records_start_time_and_delegates_to_parent():
    handler = _make_handler()

    with mock.patch.object(serving.WSGIRequestHandler, "handle", return_value="parent-handle-result") as parent_handle:
        before = time.time()
        result = handler.handle()
        after = time.time()

    assert parent_handle.called
    assert result == "parent-handle-result"
    assert before <= handler.sh_request_started <= after


def test_send_response_records_processed_time_and_delegates_to_parent():
    handler = _make_handler()

    with mock.patch.object(serving.WSGIRequestHandler, "send_response") as parent_send:
        before = time.time()
        handler.send_response(200, "OK")
        after = time.time()

    parent_send.assert_called_once_with(200, "OK")
    assert before <= handler.sh_request_processed <= after


def test_log_request_computes_duration_and_delegates_to_log():
    handler = _make_handler()
    handler.sh_request_started = 1000.0
    handler.sh_request_processed = 1000.25  # 250 ms later

    logged = []

    def fake_log(self_ignored, level, message):
        logged.append((level, message))

    with mock.patch.object(serving.WSGIRequestHandler, "log", new=fake_log):
        handler.log_request(code=200, size=1234)

    assert len(logged) == 1
    level, message = logged[0]
    assert level == "info"
    assert '"GET /foo HTTP/1.1" 200 1234 [250ms]' == message


def test_log_request_defaults_code_and_size_to_dash():
    handler = _make_handler()
    handler.sh_request_started = 0.0
    handler.sh_request_processed = 0.001  # 1 ms

    logged = []

    def fake_log(self_ignored, level, message):
        logged.append((level, message))

    with mock.patch.object(serving.WSGIRequestHandler, "log", new=fake_log):
        handler.log_request()

    level, message = logged[0]
    assert message == '"GET /foo HTTP/1.1" - - [1ms]'


def test_log_request_escapes_percent_signs_in_requestline():
    """A literal '%' in the request line is doubled to '%%' before being
    handed to the parent's log() -- defensive escaping against printf-style
    '%'-substitution that BaseHTTPRequestHandler-derived loggers may apply."""
    handler = _make_handler()
    handler.requestline = "GET /foo%20bar HTTP/1.1"
    handler.sh_request_started = 0.0
    handler.sh_request_processed = 0.0

    logged = []

    def fake_log(self_ignored, level, message):
        logged.append((level, message))

    with mock.patch.object(serving.WSGIRequestHandler, "log", new=fake_log):
        handler.log_request(code=200, size=10)

    _, message = logged[0]
    assert message == '"GET /foo%%20bar HTTP/1.1" 200 10 [0ms]'
