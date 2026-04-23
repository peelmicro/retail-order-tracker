"""Pluggable document parsers — one adapter per format."""

from src.infrastructure.parsers.csv_parser import CsvOrderParser
from src.infrastructure.parsers.dispatcher import OrderParserDispatcher, default_dispatcher
from src.infrastructure.parsers.edifact_parser import EdifactOrderParser
from src.infrastructure.parsers.json_parser import JsonOrderParser
from src.infrastructure.parsers.xml_parser import XmlOrderParser

__all__ = [
    "CsvOrderParser",
    "EdifactOrderParser",
    "JsonOrderParser",
    "OrderParserDispatcher",
    "XmlOrderParser",
    "default_dispatcher",
]
