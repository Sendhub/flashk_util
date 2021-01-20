# -*- coding: utf-8 -*-

"""Flask app converters."""

from werkzeug.routing import BaseConverter


class RegexConverter(BaseConverter):
    """
    Regex route matcher.

    Example usage:

        app.url_map.converters['regex'] = RegexConverter

    @see http://stackoverflow.com/questions/5870188/does-flask-
    support-regular-expressions-in-its-url-routing
    """

    def __init__(self, url_map, *items):
        """Stores first additional argument as the regular expression."""
        super().__init__(url_map)
        self.regex = items[0]
