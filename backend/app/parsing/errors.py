class UnsupportedFileError(ValueError):
    """The file type cannot be analysed (wrong / legacy extension)."""


class ParseError(ValueError):
    """The file is supported but empty, too large, corrupt or unreadable."""
