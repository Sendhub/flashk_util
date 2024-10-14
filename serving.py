# -*- coding: utf-8 -*-

"""Extend werkzeug request handler to suit our needs."""

import time
from werkzeug.serving import WSGIRequestHandler


class ShRequestHandler(WSGIRequestHandler):
    """Extend werkzeug request handler to suit our needs."""
    def __init__(self, *args, **kwargs):
        self.sh_request_started = None
        self.sh_request_processed = None
        super().__init__(*args, **kwargs)

    def handle(self):
        self.sh_request_started = time.time()
        _rv = super().handle()  # pylint: disable=E1111
        return _rv

    def send_response(self, *args, **kw):  # pylint: disable=W0222
        self.sh_request_processed = time.time()
        super().send_response(*args, **kw)

    def log_request(self, code='-', size='-'):
        duration = int(
            (self.sh_request_processed - self.sh_request_started) * 1000)
        self.log('info', '"{0}" {1} {2} [{3}ms]'.format(
            self.requestline.replace('%', '%%'), code, size, duration))
