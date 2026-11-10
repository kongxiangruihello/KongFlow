"""Whitespace-insensitive view of a source file, for tests that check that some code is present.

The formatter (ruff, prettier) decides spacing and line breaks, so these checks compare with all
whitespace removed on both sides.
"""

import re


def _squash(text):
    return re.sub(r'\s+', '', text)


class Source(str):
    def __new__(cls, path):
        return super().__new__(cls, _squash(path.read_text(encoding='utf-8')))

    def __contains__(self, needle):
        return super().__contains__(_squash(needle))

    def index(self, needle, *args):
        return super().index(_squash(needle), *args)
