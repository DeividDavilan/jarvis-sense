"""Testes do tratamento de erros resiliente: `@safe`, `@safe_async` e o
supervisor `supervise` (recuperação automática)."""

import asyncio

import pytest

from jarvis_sense.core.errors import safe, safe_async, supervise


def test_safe_swallows_and_returns_default() -> None:
    @safe(default=-1, module="Test")
    def explode() -> int:
        raise ValueError("nope")

    assert explode() == -1


def test_safe_passes_through_on_success() -> None:
    @safe(default=-1, module="Test")
    def ok() -> int:
        return 42

    assert ok() == 42


async def test_safe_async() -> None:
    @safe_async(default="fallback", module="Test")
    async def explode() -> str:
        raise RuntimeError("nope")

    assert await explode() == "fallback"


async def test_supervise_restarts_then_succeeds() -> None:
    attempts = {"n": 0}

    async def flaky() -> None:
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise RuntimeError("ainda não")
        return  # sucesso na 3ª

    # Backoff curto para o teste rodar rápido.
    await asyncio.wait_for(supervise(flaky, name="flaky", max_backoff=0.01), timeout=2)
    assert attempts["n"] == 3


async def test_supervise_propagates_cancel() -> None:
    async def forever() -> None:
        await asyncio.Event().wait()

    task = asyncio.create_task(supervise(forever, name="forever"))
    await asyncio.sleep(0.01)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
