"""
Tests for flashk_util.log_task_id.TaskIDFilter.
"""

import logging
from types import SimpleNamespace
from unittest import mock

from flashk_util.log_task_id import TaskIDFilter


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


def test_no_current_task_sets_defaults_blank():
    record = _make_record()

    with mock.patch("celery._state.get_current_task", return_value=None):
        result = TaskIDFilter().filter(record)

    assert result is True
    assert record.task_id == ""
    assert record.task_name == ""


def test_current_task_populates_id_and_name():
    record = _make_record()
    fake_request = SimpleNamespace(id="task-abc-123")
    fake_task = SimpleNamespace(request=fake_request, name="myapp.tasks.do_thing")

    with mock.patch("celery._state.get_current_task", return_value=fake_task):
        result = TaskIDFilter().filter(record)

    assert result is True
    assert record.task_id == "task-abc-123"
    assert record.task_name == "myapp.tasks.do_thing"


def test_task_without_request_attribute_falls_back_to_defaults():
    record = _make_record()
    fake_task = SimpleNamespace(name="myapp.tasks.do_thing")  # no `.request`

    with mock.patch("celery._state.get_current_task", return_value=fake_task):
        result = TaskIDFilter().filter(record)

    assert result is True
    assert record.task_id == ""
    assert record.task_name == ""


def test_task_with_falsy_request_falls_back_to_defaults():
    record = _make_record()
    fake_task = SimpleNamespace(request=None, name="myapp.tasks.do_thing")

    with mock.patch("celery._state.get_current_task", return_value=fake_task):
        result = TaskIDFilter().filter(record)

    assert result is True
    assert record.task_id == ""
    assert record.task_name == ""


def test_filter_does_not_overwrite_preexisting_attrs_via_setdefault():
    """When there's no current task, setdefault only fills in the attrs if
    they're not already present on the record."""
    record = _make_record()
    record.task_name = "pre-existing"

    with mock.patch("celery._state.get_current_task", return_value=None):
        TaskIDFilter().filter(record)

    assert record.task_name == "pre-existing"
    assert record.task_id == ""
