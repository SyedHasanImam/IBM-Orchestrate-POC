import pytest

from app.core.messages import extract_text
from app.platform.runtime.checkpointer import postgres_checkpointer

__all__ = ["extract_text", "checkpointer"]


@pytest.fixture
def checkpointer():
    with postgres_checkpointer() as cp:
        yield cp
