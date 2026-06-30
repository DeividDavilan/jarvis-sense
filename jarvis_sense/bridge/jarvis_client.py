"""Cliente HTTP das APIs EXISTENTES do Jarvis web.

Consome exatamente os endpoints que o app já publica (sem alterá-los):
- `GET  /api/agents`            → lista de agentes
- `POST /api/tasks`            → cria uma tarefa  {title, agentId, priority}
- `POST /api/tasks/:id/run`    → executa a tarefa pelo orquestrador

`dispatch()` é a conveniência de alto nível: resolve o agente por nome (ou usa o
primeiro disponível), cria a tarefa e a executa — o que faz "um comando de voz
virar uma tarefa no Jarvis" sem nenhuma mudança no sistema web.
"""

from __future__ import annotations

import unicodedata

from ..core.config import Settings, get_settings
from ..core.logging import get_logger

logger = get_logger("Bridge")


def _norm(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", (text or "").lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c)).strip()


class JarvisClient:
    """Cliente assíncrono (httpx) das rotas REST do Jarvis web."""

    def __init__(self, settings: Settings | None = None, http=None) -> None:
        self._settings = settings or get_settings()
        self._base = self._settings.web_url.rstrip("/")
        self._http = http  # injetável para testes (ex.: httpx.AsyncClient mockado)

    def _client(self):
        if self._http is not None:
            return self._http
        import httpx

        return httpx.AsyncClient(base_url=self._base, timeout=15.0)

    async def _request(self, method: str, path: str, **kwargs):
        client = self._client()
        owns = self._http is None
        try:
            resp = await client.request(method, path, **kwargs)
            resp.raise_for_status()
            return resp.json()
        finally:
            if owns:
                await client.aclose()

    async def list_agents(self) -> list[dict]:
        data = await self._request("GET", "/api/agents")
        return data.get("agents", [])

    async def find_agent_id(self, name: str | None) -> str | None:
        """Resolve o id de um agente pelo nome (sem acento/caixa). Sem nome,
        devolve o primeiro agente da frota."""
        agents = await self.list_agents()
        if not agents:
            return None
        if not name:
            return agents[0].get("id")
        target = _norm(name)
        for agent in agents:
            if target in _norm(agent.get("name", "")):
                return agent.get("id")
        return agents[0].get("id")  # fallback: primeiro

    async def create_task(self, title: str, agent_id: str, priority: str = "medium") -> dict:
        data = await self._request(
            "POST", "/api/tasks",
            json={"title": title, "agentId": agent_id, "priority": priority},
        )
        return data.get("task", {})

    async def run_task(self, task_id: str) -> dict:
        return await self._request("POST", f"/api/tasks/{task_id}/run")

    async def dispatch(self, title: str, agent_name: str | None = None) -> dict | None:
        """Cria e executa uma tarefa. Retorna a tarefa criada, ou None se não há
        agentes / o Jarvis web está offline."""
        agent_id = await self.find_agent_id(agent_name)
        if not agent_id:
            logger.error("Nenhum agente disponível no Jarvis web (está rodando?).")
            return None
        task = await self.create_task(title, agent_id)
        task_id = task.get("id")
        if task_id:
            await self.run_task(task_id)
            logger.info("Tarefa despachada ao Jarvis: %r (id=%s)", title, task_id)
        return task
