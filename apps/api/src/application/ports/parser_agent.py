"""Port for the Parser Agent — extracts OrderDTO from a PDF.

The infrastructure layer owns the Claude-backed implementation; the PDF
parser adapter and any use case that needs PDF extraction depend on this
abstraction only.
"""

from typing import Protocol, runtime_checkable

from src.application.dtos import OrderDTO


@runtime_checkable
class ParserAgent(Protocol):
    def parse_pdf(self, pdf_bytes: bytes) -> OrderDTO: ...
