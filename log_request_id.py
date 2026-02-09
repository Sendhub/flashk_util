"""
Module for log request id filter.
"""

import logging


class RequestIDFilter(logging.Filter):
    """
    Add celery contextual information to a log record, if appropriate.

    https://docs.python.org/2/howto/logging-cookbook.html#using-filters-to-impart-contextual-information
    """

    @staticmethod
    def get_unique_id():
        """
        Get the request id from header.
        """
        # Moved to function level to avoid circular import issues
        from flask import request

        try:
            unique_id = request.headers.get("X-Request-Id", None)
        except RuntimeError:
            unique_id = None
        return unique_id

    def filter(self, record):
        """
        Check for a currently executing celery task and add the name and id to the log record.
        """
        unique_id = self.get_unique_id()

        if unique_id:
            record.__dict__.update(request_id=unique_id)
        else:
            record.__dict__.setdefault("request_id", "")

        return True
