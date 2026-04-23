"""Port for document parsers. Infrastructure adapters implement this."""

from typing import Protocol, runtime_checkable

from src.application.dtos import OrderDTO


class UnsupportedFormatError(Exception):
    """Raised when no registered parser can handle the given file."""

    def __init__(self, filename: str, mime_type: str | None = None):
        self.filename = filename
        self.mime_type = mime_type
        super().__init__(
            f"No parser supports file {filename!r} (mime: {mime_type})"
        )


@runtime_checkable
class OrderParser(Protocol):
    """Parses bytes of one document format into a normalised OrderDTO."""

    def supports(self, filename: str, mime_type: str | None = None) -> bool: ...

    def parse(self, file_bytes: bytes, filename: str) -> OrderDTO: ...
