import pytest


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def use_pack(monkeypatch):
    """Serve this test a variant of the default pack: `use_pack(sources=..., evals=...)`."""
    from dataclasses import replace

    from rag_stack.config import Settings

    def use(**changes):
        pack = replace(Settings().pack, **changes)
        monkeypatch.setattr(Settings, "pack", pack)
        return pack

    return use
