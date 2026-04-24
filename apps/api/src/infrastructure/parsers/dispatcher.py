"""Dispatches a file to the first parser whose supports() returns true."""

from src.application.dtos import OrderDTO
from src.application.ports.order_parser import OrderParser, UnsupportedFormatError
from src.application.ports.parser_agent import ParserAgent
from src.infrastructure.parsers.csv_parser import CsvOrderParser
from src.infrastructure.parsers.edifact_parser import EdifactOrderParser
from src.infrastructure.parsers.json_parser import JsonOrderParser
from src.infrastructure.parsers.pdf_parser import PdfOrderParser
from src.infrastructure.parsers.xml_parser import XmlOrderParser


class OrderParserDispatcher:
    """Composition-based dispatcher. Adding a format = adding a parser to the list."""

    def __init__(self, parsers: list[OrderParser]):
        self._parsers = parsers

    def find_parser(
        self,
        filename: str,
        mime_type: str | None = None,
    ) -> OrderParser:
        """Return the first parser whose supports() returns true."""
        for parser in self._parsers:
            if parser.supports(filename, mime_type):
                return parser
        raise UnsupportedFormatError(filename, mime_type)

    def dispatch(
        self,
        file_bytes: bytes,
        filename: str,
        mime_type: str | None = None,
    ) -> OrderDTO:
        return self.find_parser(filename, mime_type).parse(file_bytes, filename)


def default_dispatcher(
    parser_agent: ParserAgent | None = None,
) -> OrderParserDispatcher:
    """Factory wiring the deterministic parsers in registration order.

    Pass a ParserAgent to also include the PdfOrderParser. Leaving it None
    yields the 4 deterministic parsers only — useful for code paths that
    never need AI (e.g. unit tests, environments without an API key).
    """
    parsers: list[OrderParser] = [
        JsonOrderParser(),
        XmlOrderParser(),
        CsvOrderParser(),
        EdifactOrderParser(),
    ]
    if parser_agent is not None:
        parsers.append(PdfOrderParser(parser_agent))
    return OrderParserDispatcher(parsers)
