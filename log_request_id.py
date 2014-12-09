import logging
from flask import request


class RequestIDFilter(logging.Filter):
    """
    Adds celery contextual information to a log record, if appropriate.

    https://docs.python.org/2/howto/logging-cookbook.html
    #using-filters-to-impart-contextual-information
    """

    def get_unique_id(self):
        try:
            unique_id = request.headers.get('X-Request-Id', None)
        except RuntimeError:
            unique_id = None
        return unique_id

    def filter(self, record):
        """
        Checks for a currently executing celery task and adds the name and
        id to the log record.
        :param record:
        :return:
        """

        unique_id = self.get_unique_id()

        if unique_id:
            record.__dict__.update(request_id=unique_id)
        else:
            record.__dict__.setdefault('request_id', '')

        return True
