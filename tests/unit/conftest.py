import os

import pytest

from rag_stack.config import Settings

# The engine's tests use the reference pack as their domain, whatever the default or .env selects.
os.environ["RAG_PACK"] = "cybersecurity"


@pytest.fixture(autouse=True)
def ignore_dotenv(monkeypatch):
    """Unit tests use the code defaults, whatever a developer's .env says."""
    monkeypatch.setitem(Settings.model_config, "env_file", None)
