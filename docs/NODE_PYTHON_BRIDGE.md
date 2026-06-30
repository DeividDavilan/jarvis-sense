# Ponte Node ↔ Python

O Jarvis Sense (Python) e o Jarvis web (Node/Next.js) conversam por **dois canais
desacoplados e aditivos**. Nenhum endpoint existente do app web é modificado.

```
   Jarvis Sense (Python)                         Jarvis web (Node/Next.js)
   ─────────────────────                         ─────────────────────────
   bridge/jarvis_client.py  ──── HTTP ────►  APIs JÁ EXISTENTES (/api/agents, /api/tasks…)
   bridge/ws_server.py      ◄─── WS ─────   (futuro) Electron/HUD consumindo percepção
```

---

## 1. Canal HTTP — Python consome as APIs existentes

`bridge/jarvis_client.py` (`JarvisClient`) chama exatamente os endpoints que o
Jarvis web já publica:

| Método | Rota | Uso |
| ------ | ---- | --- |
| `GET`  | `/api/agents` | listar/resolver agentes |
| `POST` | `/api/tasks` | criar tarefa `{title, agentId, priority}` → `201 {task}` |
| `POST` | `/api/tasks/:id/run` | executar a tarefa pelo orquestrador |

**Fluxo de despacho** (`JarvisClient.dispatch(title, agent_name?)`):
1. resolve o `agentId` por nome (ou usa o primeiro agente);
2. `POST /api/tasks` cria a tarefa;
3. `POST /api/tasks/:id/run` a executa.

Disparado por voz via `bridge/dispatch.py` (`TaskDispatchService`), que reconhece
comandos como *"criar tarefa …"*, *"nova tarefa: …"*, *"anota uma tarefa de …"*.

> Como o Python é **cliente** das rotas existentes, o app web permanece intocado.

---

## 2. Canal WebSocket — Python publica eventos de percepção

`bridge/ws_server.py` (`PerceptionWebSocketServer`) sobe um servidor em
`ws://127.0.0.1:8765` (configurável). Ele assina **todos** os eventos do barramento
e transmite cada um como **um frame JSON** para os clientes conectados.

É o espelho do canal SSE do Jarvis web (`/api/stream`), mas no sentido
**Python → consumidores** (um futuro Electron/HUD nativo, por exemplo).

### Formato do frame

Cada frame é o `to_payload()` do evento:

```json
{ "type": "OnOCRFinished", "ts": 1719600000.12, "text": "…", "region": "full", "engine": "rapidocr" }
{ "type": "OnSpeechDetected", "ts": 1719600001.34, "text": "abrir o painel", "is_final": true, "wake": true }
{ "type": "OnAudioCaptured", "ts": 1719600002.00, "text": "…", "source": "loopback" }
{ "type": "OnScreenChanged", "ts": 1719600002.50, "region": "full", "diff_ratio": 0.18 }
{ "type": "OnVisionUpdated", "ts": 1719600003.10, "summary": "…", "text": "…" }
{ "type": "OnJarvisSpeaking", "ts": 1719600003.80, "text": "…", "speaking": true }
```

### Exemplo de cliente (JS)

```js
const ws = new WebSocket("ws://127.0.0.1:8765");
ws.onmessage = (e) => {
  const ev = JSON.parse(e.data);
  if (ev.type === "OnOCRFinished") console.log("Tela diz:", ev.text);
};
```

---

## Por que WebSocket (e não gRPC)?

- Alinha com o padrão que a própria `docs/ARCHITECTURE.md` do Jarvis web define
  (SSE/WebSocket), reduzindo atrito conceitual.
- Sem etapa de build de `.proto`; texto/JSON é fácil de inspecionar e depurar.
- Latência baixa o suficiente para eventos de percepção.

Se um dia for preciso streaming binário de alto volume (ex.: vídeo), um segundo
canal gRPC pode ser adicionado **ao lado** deste, sem remover o WebSocket.

---

## Configuração

| Variável | Default | Descrição |
| -------- | ------- | --------- |
| `JARVIS_WEB_URL` | `http://localhost:3000` | base das APIs do Jarvis web (HTTP) |
| `JARVIS_SENSE_WS_HOST` | `127.0.0.1` | host do servidor WS de percepção |
| `JARVIS_SENSE_WS_PORT` | `8765` | porta do servidor WS de percepção |
