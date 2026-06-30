"""Testes do JarvisClient contra as rotas reais do Jarvis web, usando o
httpx.MockTransport (sem servidor de verdade). Garante que o contrato HTTP bate
com os endpoints existentes: GET /api/agents, POST /api/tasks, POST /api/tasks/:id/run."""

import httpx
import pytest

from jarvis_sense.bridge.jarvis_client import JarvisClient
from jarvis_sense.core.config import get_settings


def _client(handler) -> JarvisClient:
    transport = httpx.MockTransport(handler)
    http = httpx.AsyncClient(transport=transport, base_url="http://test")
    return JarvisClient(get_settings(), http=http)


async def test_find_agent_id_by_name() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/api/agents"
        return httpx.Response(200, json={"agents": [
            {"id": "a1", "name": "Sr. Penelopo"},
            {"id": "a2", "name": "Mega Tron"},
        ]})

    client = _client(handler)
    assert await client.find_agent_id("mega tron") == "a2"
    assert await client.find_agent_id(None) == "a1"   # primeiro
    assert await client.find_agent_id("inexistente") == "a1"  # fallback


async def test_dispatch_creates_and_runs_task() -> None:
    calls: list[str] = []

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append(f"{req.method} {req.url.path}")
        if req.url.path == "/api/agents":
            return httpx.Response(200, json={"agents": [{"id": "a1", "name": "Penelopo"}]})
        if req.url.path == "/api/tasks" and req.method == "POST":
            body = req.read().decode()
            assert "title" in body and "agentId" in body
            return httpx.Response(201, json={"task": {"id": "t9", "title": "x"}})
        if req.url.path == "/api/tasks/t9/run":
            return httpx.Response(200, json={"ok": True})
        return httpx.Response(404)

    client = _client(handler)
    task = await client.dispatch("revisar contrato")

    assert task == {"id": "t9", "title": "x"}
    assert "POST /api/tasks" in calls
    assert "POST /api/tasks/t9/run" in calls


async def test_dispatch_without_agents_returns_none() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"agents": []})

    client = _client(handler)
    assert await client.dispatch("qualquer") is None
