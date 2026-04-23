from pathlib import Path

import pytest

# tests/parsers/conftest.py → parents[4] = repo root
SAMPLES_DIR = Path(__file__).resolve().parents[4] / "samples" / "orders"


@pytest.fixture
def samples_dir() -> Path:
    return SAMPLES_DIR
