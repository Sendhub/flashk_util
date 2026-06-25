"""
Log formatter module.
"""

import logging


class ShLoggingFormatter(logging.Formatter):
    """
    Custom log formatting class for SendHub Flask apps which looks for the presence of either a request_id or task_id attribute and prepends it to the log line being formatted.

    Request_id is an attribute set by flashk_util.log_request_id.RequestIDFilter which pulls a header from all HTTP requests, X_REQUEST_ID, if it exists.

    Task_id is an attribute set by flashk_util.log_task_id.TaskIDFilter which checks for the existence of a running celery task and pulls the unique task id, if it exists.

    If both request_id and task_id are present (which should never occur), request_id takes precedence and is shown.
    """

    def __init__(self, fmt=None):
        logging.Formatter.__init__(self, fmt)

    @staticmethod
    def _should_show_attr(record, attr):
        """
        Determine if the requested attribute should be included in the log output.
        """
        return hasattr(record, attr) and getattr(record, attr) and getattr(record, attr) != "none"

    def format(self, record):
        """
        Format the specified record as text. Prepends a unique identifier from either the current request or the celery task being run, if one exists.
        """
        show_request_id = self._should_show_attr(record, "request_id")
        show_task_id = self._should_show_attr(record, "task_id")

        unique_id = ""
        if show_request_id:
            unique_id = record.request_id
        elif show_task_id:
            unique_id = record.task_id

        # Let the parent class build the base string
        _s = logging.Formatter.format(self, record)

        if unique_id:
            # Replace only the first occurrence of the original message
            _s = _s.replace(record.getMessage(), f"{unique_id} {record.getMessage()}", 1)

        return _s
