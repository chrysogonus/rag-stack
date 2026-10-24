import pytest

from rag_stack.config import Settings


@pytest.fixture(autouse=True)
def ignore_dotenv(monkeypatch):
    """Unit tests use the code defaults, whatever a developer's .env says."""
    monkeypatch.setitem(Settings.model_config, "env_file", None)
