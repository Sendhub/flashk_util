# -*- coding: utf-8 -*-

"""Extend werkzeug request handler to suit our needs."""

import time
from werkzeug.serving import BaseRequestHandler

class ShRequestHandler(BaseRequestHandler):
    """Extend werkzeug request handler to suit our needs."""
    def handle(self):
        self.shRequestStarted = time.time()
        rv = super(ShRequestHandler, self).handle()
        return rv

    def send_response(self, *args, **kw):
        self.shRequestProcessed = time.time()
        super(ShRequestHandler, self).send_response(*args, **kw)

    def log_request(self, code='-', size='-'):
        duration = int((self.shRequestProcessed - self.shRequestStarted) * 1000)
        self.log('info', '"{0}" {1} {2} [{3}ms]'.format(self.requestline, code, size, duration))

