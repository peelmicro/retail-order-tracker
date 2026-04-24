"""PDF parser — thin adapter that implements the OrderParser protocol by
delegating to the multimodal Parser Agent. The agent owns the Claude + Phoenix
integration; this class only handles format detection and delegation."""

from src.application.dtos import OrderDTO
from src.application.ports.parser_agent import ParserAgent


class PdfOrderParser:
    name = "pdf"
    extensions = (".pdf",)

    def __init__(self, agent: ParserAgent) -> None:
        self._agent = agent

    def supports(self, filename: str, mime_type: str | None = None) -> bool:
        if filename.lower().endswith(self.extensions):
            return True
        if mime_type == "application/pdf":
            return True
        return False

    def parse(self, file_bytes: bytes, filename: str) -> OrderDTO:
        return self._agent.parse_pdf(file_bytes)
