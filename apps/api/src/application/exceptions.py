"""Domain-level exceptions raised by use cases.

Kept FastAPI-free — the API layer translates these to HTTP responses.
"""


class UnknownCurrencyError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(f"Currency code {code!r} is not registered in the database")


class UnknownFormatError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(f"Format code {code!r} is not registered in the database")
