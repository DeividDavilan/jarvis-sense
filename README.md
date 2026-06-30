# Jarvis Sense 🧠👁️🎙️

Camada de **percepção** (voz, áudio e visão) do **J.A.R.V.I.S.**, feita para rodar
no **Windows Terminal**. Dá ao Jarvis a capacidade de:

- 🎙️ **ouvir o microfone** (fala → texto, com wake word "Jarvis", VAD e anti-eco);
- 🔊 **falar com voz única** (a do Jarvis — a sua nunca é sintetizada);
- 🎧 **capturar o áudio do sistema** (loopback WASAPI: YouTube, Spotify, chamadas…);
- 👁️ **enxergar e ler a tela** (captura inteligente + OCR gratuito);
- 🧩 **comandar o Jarvis web existente** — pelas APIs que ele já publica, **sem alterá-lo**.

É um subsistema **Python independente**, que conversa com o **Jarvis web (Node/Next.js)**
de forma desacoplada (WebSocket + HTTP). Construído com **Clean Architecture + SOLID**:
cada capacidade é um módulo isolado que só se comunica por um **barramento de eventos**.

> Projeto irmão do `jarvis-command-center/`. **Nenhum arquivo do app web é modificado.**

---

## Por que Python + Node?

| Camada | Responsabilidade |
| ------ | ---------------- |
| **Python** (`jarvis-sense`) | OCR, captura de tela, visão, áudio, microfone, STT, TTS, automações Windows |
| **Node** (`jarvis-command-center`) | backend, API, frontend, WebSocket, orquestração de agentes |

As capacidades de SO (microfone, loopback de áudio, captura de tela, OCR) **não
existem no navegador** — por isso vivem em Python. O Node continua sendo o cérebro
da aplicação web; o Python é a percepção que roda na máquina.

---

## Instalação

Pré-requisitos: **Python 3.11+** e **Windows 10/11**.

```bash
cd jarvis-sense
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env      # edite e cole sua GROQ_API_KEY (a mesma do Jarvis web)
```

O `requirements.txt` instala o **núcleo + voz + cérebro + ponte**. As dependências
mais pesadas (microfone, OCR, loopback) estão **comentadas por fase** no arquivo —
descomente conforme for ativando cada capacidade:

```bash
# Microfone (Fase 2):     pip install sounddevice            (webrtcvad é OPCIONAL;
#                          sem ele, o VAD por energia em numpy já funciona)
# Wake word acústica:     pip install openwakeword           ("hey jarvis" antes do
#                          STT; sem ela, a ativação cai para o modo textual)
# Tela + OCR (Fase 4):    pip install mss Pillow rapidocr-onnxruntime
# Áudio do sistema (Fase 5): pip install PyAudioWPatch
# STT local offline:      pip install faster-whisper          (fallback do Groq Whisper)
```

> **TTS e STT funcionam sem instalar nada extra de pesado:** o edge-tts (voz neural
> grátis) já vem no requirements, e há fallback offline via **SAPI do Windows** (zero
> dependências). O STT padrão é o **Groq Whisper** (usa sua chave Groq).

---

## Como usar

### Subir tudo (no Windows Terminal)
```bash
python run.py
```
Sobe todos os serviços ativos (cérebro, voz, visão, loopback, ponte). Cada um que
não tiver suas libs instaladas **apenas se desativa com um aviso** — nada quebra.
Encerre com `Ctrl+C`.

### Demos isoladas (validar cada parte)
```bash
python -m jarvis_sense.tts.demo "Olá, senhor."     # a voz do Jarvis fala
python -m jarvis_sense.brain.demo                    # converse por TEXTO (sem mic)
python -m jarvis_sense.vision.demo                   # lê a tela uma vez por OCR
```

### Exemplos de comando de voz
- *"Jarvis, que horas são?"* → o cérebro responde falando.
- *"Jarvis, criar tarefa revisar a proposta"* → cria a tarefa no **Jarvis web** e confirma.

---

## Testes

```bash
pytest          # 77 testes de unidade (lógica pura + serviços com fakes)
```

Os testes **não exigem hardware** (microfone, alto-falante, tela): usam dublês.
A validação com hardware real é feita pelas **demos** e pelo `run.py`.

---

## Configuração (`.env`)

Tudo é opcional (há defaults). Destaques:

| Variável | Default | Para quê |
| -------- | ------- | -------- |
| `GROQ_API_KEY` | — | cérebro + STT (gratuito) |
| `JARVIS_TTS_ENGINE` | `edge` | voz: `edge` (neural) ou `sapi` (offline) |
| `JARVIS_STT_ENGINE` | `groq` | STT: `groq` ou `local` (faster-whisper) |
| `JARVIS_OCR_ENGINE` | `rapidocr` | OCR: `rapidocr` ou `tesseract` |
| `JARVIS_VISION_ENGINE` | `off` | visão LLM: `off` ou `anthropic` (gera custo) |
| `JARVIS_WEB_URL` | `http://localhost:3000` | onde está o Jarvis web |
| `JARVIS_SENSE_WS_PORT` | `8765` | porta do WebSocket de percepção |

Lista completa em `.env.example`.

---

## Documentação

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — arquitetura, fluxograma, eventos, performance.
- [`docs/NODE_PYTHON_BRIDGE.md`](docs/NODE_PYTHON_BRIDGE.md) — contrato de comunicação Node ↔ Python.
- [`docs/HOW_TO_ADD_MODULE.md`](docs/HOW_TO_ADD_MODULE.md) — como adicionar motores e módulos novos.
- [`docs/WAKE_WORD.md`](docs/WAKE_WORD.md) — personalizar a wake word (pré-treinada, customizada "Penelopo", calibração).

---

## Status das fases

| Fase | Capacidade | Estado |
| ---- | ---------- | ------ |
| 0 | Fundação (core, eventos, logs, erros) | ✅ |
| 1 | Voz do Jarvis (TTS: edge + SAPI) | ✅ validado |
| 2 | Microfone + STT híbrido (Groq + local) + wake word acústica "hey jarvis" | ✅ validado |
| 3 | Cérebro — fatia vertical (ouvir→pensar→falar) | ✅ validado |
| 4 | Tela + OCR + visão | ✅ validado |
| 5 | Áudio do sistema (loopback WASAPI) | ✅ validado |
| 6 | Ponte Node↔Python (WS + despacho de tarefas) | ✅ validado |
| 7 | Documentação | ✅ |
