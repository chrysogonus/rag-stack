"""Fixtures for the engine's tests (tests/) and the packs' (packs/*/tests/)."""

import pytest

from rag_stack.config import Settings


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(autouse=True)
def ignore_dotenv(request, monkeypatch):
    """Unit tests use the code defaults, whatever a developer's .env says."""
    if "unit" in request.path.parts:
        monkeypatch.setitem(Settings.model_config, "env_file", None)


@pytest.fixture
def use_pack(monkeypatch):
    """Serve this test a variant of the default pack: `use_pack(sources=..., evals=...)`."""
    from dataclasses import replace

    def use(**changes):
        pack = replace(Settings().pack, **changes)
        monkeypatch.setattr(Settings, "pack", pack)
        return pack

    return use
