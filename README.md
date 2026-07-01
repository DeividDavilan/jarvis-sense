# J.A.R.V.I.S. Sense

Camada de **percepção nativa** do [J.A.R.V.I.S. Command Center](https://github.com/DeividDavilan/jarvis-command-center) — roda no **Windows Terminal** em Python e dá ao Jarvis olhos, ouvidos e voz.

> Projeto irmão do `jarvis-command-center`. **Nenhum arquivo do app web é modificado.**

---

## O que o Jarvis Sense faz

| Capacidade | O que acontece |
|---|---|
| 🎙️ **Microfone + STT** | Ouve o que você diz, transcreve com Groq Whisper (ou faster-whisper offline) |
| 🔊 **TTS — voz do Jarvis** | Responde em voz sintetizada (edge-tts neural / SAPI offline) |
| 🎧 **Loopback de áudio** | Captura o áudio do sistema via WASAPI (YouTube, Spotify, chamadas…) |
| 👁️ **Visão de tela** | Captura e lê a tela com OCR (RapidOCR / Tesseract); opcionalmente descreve com LLM |
| 🧠 **Cérebro LLM** | Processa comandos com Groq (Llama 3.3 70B, gratuito) ou Anthropic |
| 🔗 **Ponte WS + HTTP** | Envia comandos para o Jarvis web pelas APIs que ele já publica |
| 🖥️ **HUD de percepção** | Transmite eventos ao vivo para o painel do Command Center via WebSocket |

---

## Arquitetura

```
┌─────────────────────── Jarvis Sense (Python · Windows) ────────────────────────┐
│                                                                                  │
│  🎙️ mic ──► [microphone] VAD ──► [speech] STT ──────────────────┐               │
│  🎧 loopback ──► [audio] resample 16k ──────────────────────────┤               │
│  🖥️ tela ──► [screen] diff ──► [ocr] ──► [vision] LLM opcional ─┤               │
│                                                                   ▼               │
│                              ┌──────── EventBus (pub/sub async) ──────────┐      │
│                              │  OnSpeechDetected · OnAudioCaptured         │      │
│                              │  OnVisionUpdated · OnMicState · ControlCmd  │      │
│                              └─────────────────┬───────────────────────────┘      │
│                                                ▼                                  │
│  [brain] LLM ◄──────────────────────── história + contexto de tela               │
│       │                                                                           │
│       ▼                                                                           │
│  [tts] fala ── [bridge] WS server :8765 ──► jarvis-command-center (HUD)          │
│                        │                                                          │
│                        └──► HTTP /api/tasks (cria/executa tarefas no web)        │
└──────────────────────────────────────────────────────────────────────────────────┘
```

**Princípios:** Clean Architecture + SOLID — cada módulo tem `interfaces`, `services`, `models`, `config` e `tests`. Módulos nunca se chamam diretamente: publicam e assinam eventos no `EventBus`. Erros são isolados e recuperados automaticamente (`@safe`, `supervise`).

---

## Instalação

**Pré-requisitos:** Python 3.11+ · Windows 10/11

> O venv e os pesos de modelos (Whisper, etc.) ficam no **D:**, não no C: (pouco
> espaço livre no disco do sistema).

```bash
cd jarvis-sense
python -m venv D:\venvs\jarvis-sense
D:\venvs\jarvis-sense\Scripts\activate
pip install -r requirements.txt
copy .env.example .env   # cole sua GROQ_API_KEY
```

Capacidades opcionais — instale conforme precisar:

```bash
# Wake word acústica "hey jarvis"
pip install openwakeword

# OCR + visão de tela
pip install mss Pillow rapidocr-onnxruntime

# Loopback de áudio do sistema
pip install PyAudioWPatch

# STT offline (sem internet)
pip install faster-whisper
```

> TTS e STT já funcionam sem instalar nada extra: `edge-tts` vem no `requirements.txt` e o fallback offline é o **SAPI do Windows** (zero dependências extra). O STT padrão é o **Groq Whisper** — usa a mesma chave do Jarvis web.

---

## Como usar

### Subir todos os serviços

```bash
python run.py
```

Inicializa cérebro, voz, visão, loopback e ponte WebSocket. Módulos sem libs instaladas se desativam com um aviso — nada quebra. Encerre com `Ctrl+C`.

### Demos isoladas

```bash
python -m jarvis_sense.tts.demo "Olá, senhor."   # voz do Jarvis fala
python -m jarvis_sense.brain.demo                 # chat por texto (sem mic)
python -m jarvis_sense.vision.demo                # lê a tela uma vez
python -m jarvis_sense.speech.wake_demo           # testa wake word acústica
```

### Exemplos de comando de voz

- *"Jarvis, que horas são?"* → cérebro responde em voz
- *"Jarvis, criar tarefa revisar a proposta"* → cria a tarefa no Jarvis web e confirma falando

---

## HUD de percepção (painel ao vivo)

Com o `jarvis-command-center` rodando em `localhost:3000`, o Sense transmite eventos em tempo real pelo WebSocket em `ws://127.0.0.1:8765`. O painel **Percepção · Jarvis Sense** exibe:

- **Barra de wake word** — cinza (aguardando) → dourado pulsando (wake word detectada) → ciano pulsando (escutando comando)
- **Botão Power** em cada sensor (mic, loopback, OCR, visão) — liga/desliga sem reiniciar
- **Reatividade do Cérebro** — botões LOOP e VIS habilitam respostas proativas a áudio e visão
- **Feed ao vivo** — todos os eventos de percepção em ordem cronológica

O HUD também envia comandos de volta ao Python (WebSocket bidirecional): clicar em um botão publica um `ControlCommand` no `EventBus` e o módulo responde.

---

## Testes

```bash
pytest          # 77 testes (lógica pura + serviços com fakes)
pytest -v       # verbose
```

Os testes não exigem hardware (microfone, alto-falante, tela) — usam dublês. Validação real é feita pelas **demos** e pelo `run.py`.

---

## Configuração (`.env`)

| Variável | Default | Para quê |
|---|---|---|
| `GROQ_API_KEY` | — | cérebro + STT Whisper (gratuito) |
| `ANTHROPIC_API_KEY` | — | visão LLM (opcional, gera custo) |
| `JARVIS_TTS_ENGINE` | `edge` | voz: `edge` (neural) ou `sapi` (offline) |
| `JARVIS_STT_ENGINE` | `groq` | STT: `groq` ou `local` (faster-whisper) |
| `JARVIS_WAKE_MODE` | `acoustic` | wake word: `acoustic` (openWakeWord) ou `text` |
| `JARVIS_OCR_ENGINE` | `rapidocr` | OCR: `rapidocr` ou `tesseract` |
| `JARVIS_VISION_ENGINE` | `off` | visão LLM: `off` ou `anthropic` |
| `JARVIS_LOOPBACK_REACT` | `false` | cérebro reage ao áudio do sistema |
| `JARVIS_VISION_REACT` | `false` | cérebro comenta o que vê na tela |
| `JARVIS_WEB_URL` | `http://localhost:3000` | URL do Jarvis web |
| `JARVIS_SENSE_WS_PORT` | `8765` | porta do WebSocket de percepção |

Lista completa em [`.env.example`](.env.example).

---

## Estrutura de módulos

```
jarvis_sense/
├── core/          # EventBus, config, erros, logging, ciclo de vida
├── speech/        # wake word, VAD, STT, VoiceInputService
├── tts/           # síntese de voz (edge-tts, SAPI)
├── microphone/    # captura de áudio do mic
├── audio/         # loopback WASAPI (áudio do sistema)
├── screen/        # captura de tela + diff
├── ocr/           # RapidOCR / Tesseract
├── vision/        # VisionService (OCR + LLM opcional)
├── brain/         # BrainService — histórico + contexto de tela + LLM
├── bridge/        # WebSocket server + despacho de tarefas HTTP
└── services/      # App — monta e inicia todos os serviços
```

---

## Documentação

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — arquitetura detalhada, eventos, performance
- [`docs/NODE_PYTHON_BRIDGE.md`](docs/NODE_PYTHON_BRIDGE.md) — contrato de comunicação Node ↔ Python
- [`docs/HOW_TO_ADD_MODULE.md`](docs/HOW_TO_ADD_MODULE.md) — como adicionar motores e módulos novos
- [`docs/WAKE_WORD.md`](docs/WAKE_WORD.md) — personalizar wake word (pré-treinada, customizada, calibração)

---

## Status

| Fase | Capacidade | Estado |
|---|---|---|
| 0 | Fundação (core, eventos, logs, erros) | ✅ |
| 1 | TTS — voz do Jarvis (edge-tts + SAPI) | ✅ validado |
| 2 | Microfone + STT + wake word acústica | ✅ validado |
| 3 | Cérebro (ouvir → pensar → falar) | ✅ validado |
| 4 | Tela + OCR + visão LLM opcional | ✅ validado |
| 5 | Loopback de áudio do sistema (WASAPI) | ✅ validado |
| 6 | Ponte Node↔Python (WS + HTTP) | ✅ validado |
| 7 | HUD ao vivo + WS bidirecional + 4 features | ✅ validado |

**77 testes pytest passando.**

---

## Projeto irmão

[**J.A.R.V.I.S. Command Center**](https://github.com/DeividDavilan/jarvis-command-center) — o HUD web (Next.js) que o Sense alimenta com eventos de percepção em tempo real.
