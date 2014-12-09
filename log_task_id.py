import logging
from celery._state import get_current_task


class TaskIDFilter(logging.Filter):
    """
    Adds celery contextual information to a log record, if appropriate.

    https://docs.python.org/2/howto/logging-cookbook.html
    #using-filters-to-impart-contextual-information
    """

    def filter(self, record):
        """
        Checks for a currently executing celery task and adds the name and
        id to the log record.
        :param record:
        :return:
        """

        task = get_current_task()

        if task and hasattr(task, 'request') and task.request:
            record.__dict__.update(task_id=task.request.id,
                                   task_name=task.name)
        else:
            record.__dict__.setdefault('task_name', '')
            record.__dict__.setdefault('task_id', '')

        return True
