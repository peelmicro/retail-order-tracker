"""Dispatches a file to the first parser whose supports() returns true."""

from src.application.dtos import OrderDTO
from src.application.ports.order_parser import OrderParser, UnsupportedFormatError
from src.infrastructure.parsers.csv_parser import CsvOrderParser
from src.infrastructure.parsers.edifact_parser import EdifactOrderParser
from src.infrastructure.parsers.json_parser import JsonOrderParser
from src.infrastructure.parsers.xml_parser import XmlOrderParser


class OrderParserDispatcher:
    """Composition-based dispatcher. Adding a format = adding a parser to the list."""

    def __init__(self, parsers: list[OrderParser]):
        self._parsers = parsers

    def dispatch(
        self,
        file_bytes: bytes,
        filename: str,
        mime_type: str | None = None,
    ) -> OrderDTO:
        for parser in self._parsers:
            if parser.supports(filename, mime_type):
                return parser.parse(file_bytes, filename)
        raise UnsupportedFormatError(filename, mime_type)


def default_dispatcher() -> OrderParserDispatcher:
    """Factory wiring the 4 deterministic parsers in registration order."""
    return OrderParserDispatcher(
        [
            JsonOrderParser(),
            XmlOrderParser(),
            CsvOrderParser(),
            EdifactOrderParser(),
        ]
    )
