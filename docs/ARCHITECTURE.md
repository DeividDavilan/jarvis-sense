# Arquitetura — Jarvis Sense

## Princípios

- **Clean Architecture + SOLID** — cada capacidade é um módulo isolado com
  `interfaces` (contratos), `services` (lógica), `models`, `utils`, `config`, `tests`.
- **Orientado a eventos** — módulos nunca se chamam diretamente; publicam e assinam
  eventos num **barramento assíncrono** (`core/events.py`). Trocar/adicionar um
  módulo não afeta os outros.
- **Inversão de dependência** — quem consome fala com **interfaces** (`ITTS`, `ISTT`,
  `IOCR`, `IVision`, `ILLMProvider`, `IAudioSource`...), nunca com a implementação.
- **Resiliência** — nenhum módulo pode derrubar o sistema. Erros são isolados,
  logados e recuperados automaticamente (`core/errors.py` → `@safe`, `supervise`).
- **Gratuito por padrão** — edge-tts, Groq Whisper, RapidOCR, SAPI, faster-whisper.
  Motores pagos (ElevenLabs, Claude Vision) entram como adaptadores opcionais.

## Fluxograma (pipeline de percepção)

```
        ┌───────────────────────── Jarvis Sense (Python · Windows Terminal) ─────────────────────────┐
        │                                                                                            │
 🎙️ Microfone ─► [microphone] VAD/silêncio ─► Utterance ─┐                                            │
                                                          │                                           │
 🎧 Áudio do  ─► [audio] WASAPI loopback ─► resample 16k ─┤─► [speech] ISTT (Groq Whisper│local) ─► texto
    sistema                                               │                         │                 │
                                                          ▼                         ▼                 │
                                              ┌────────── EventBus (pub/sub assíncrono) ──────────┐    │
 🖥️ Tela ─► [screen] captura mss + diff ─► PNG ─► [ocr] RapidOCR│Tesseract ─► [vision] IVision ──►│    │
                                                          │                                       │    │
        OnSpeechDetected · OnAudioCaptured · OnScreenChanged · OnOCRFinished · OnVisionUpdated ··· │    │
                                                          │                                       │    │
                            ┌─────────────────────────────┼───────────────────────────────┐      │    │
                            ▼                              ▼                                ▼      │    │
                    [brain] pensa (Groq│Anthropic)  [bridge] despacho de        [bridge] WS server │    │
                            │                         tarefas → Jarvis web              (8765)      │    │
                            ▼                              │                                ▲       │    │
                    [tts] fala (edge│SAPI) ─► OnJarvisSpeaking ──► silencia o mic (anti-eco)│       │    │
        │                   │                              │                                │       │    │
        └───────────────────┼──────────────────────────────┼────────────────────────────────┼──────┘    │
                            ▼ (voz única do Jarvis)         ▼ HTTP (APIs existentes)          ▼ WS        │
                        🔊 alto-falante              Jarvis web (Node/Next.js)        Electron/HUD futuro │
```

## Módulos

| Módulo | Papel | Interface | Implementações |
| ------ | ----- | --------- | -------------- |
| `core` | config, logging, eventos, erros, ciclo de vida | — | — |
| `tts` | voz do Jarvis | `ITTS` | edge-tts (padrão), SAPI (offline) |
| `microphone` | captura de mic + VAD | `IAudioSource` | sounddevice + webrtcvad |
| `speech` | fala→texto + wake word | `ISTT`, `IWakeWord` | STT: Groq Whisper, faster-whisper · wake: openWakeWord (acústica), textual |
| `audio` | áudio do sistema (loopback) | `ILoopbackSource` | PyAudioWPatch (WASAPI) |
| `screen` | captura de tela + diff | `IScreenCapture` | mss + Pillow |
| `ocr` | leitura de texto da tela | `IOCR` | RapidOCR (padrão), Tesseract |
| `vision` | compreensão da tela | `IVision` | NullVision (padrão), Claude Vision |
| `brain` | raciocínio (decide e fala) | `ILLMProvider` | Groq (padrão), Anthropic |
| `bridge` | ponte com o Jarvis web | — | HTTP client + WebSocket server + despacho |
| `services` | composition root | — | `JarvisSenseApp` |

## Eventos (`core/event_types.py`)

`OnMicrophoneStarted` · `OnSpeechDetected` · `OnAudioCaptured` · `OnScreenChanged` ·
`OnOCRFinished` · `OnVisionUpdated` · `OnJarvisSpeaking`.

Cada evento é uma `dataclass` imutável com `to_payload()` → o frame JSON do
WebSocket de percepção.

## Ciclo de vida (`core/lifecycle.py`)

`ServiceManager` sobe cada serviço sob **supervisão** (`supervise`): se um serviço
cair, é reiniciado com backoff exponencial — recuperação automática. O composition
root (`services/app.py`) registra os serviços; serviços sem dependências instaladas
apenas logam e ficam inativos (degradação graciosa).

## Performance

- **OCR/visão só rodam quando a tela muda** — `screen/diff.py` compara assinaturas
  perceptuais (miniatura 32×32 cinza); abaixo de 2% de mudança, nada é processado.
- **Cache LRU de OCR** por assinatura de tela (`ocr/services.py`) — telas idênticas
  não são reprocessadas.
- **Threads para trabalho pesado** — STT, OCR, TTS e captura rodam em `asyncio.to_thread`,
  mantendo o loop de eventos livre.
- **Reamostragem leve** — loopback convertido para 16 kHz mono com numpy.

## Logs (`core/logging.py`)

Um logger por módulo (Audio, OCR, Speech, Vision, Brain, Bridge, App, Lifecycle…),
com console UTF-8 + arquivo rotativo em `logs/<modulo>.log`. Níveis
DEBUG/INFO/WARNING/ERROR via `JARVIS_LOG_LEVEL`.

## Stack

| Função | Biblioteca (gratuita) |
| ------ | --------------------- |
| Config | pydantic-settings |
| TTS | edge-tts, SAPI (System.Speech) |
| STT | Groq Whisper, faster-whisper |
| VAD | webrtcvad (fallback: VAD por energia em numpy) |
| Wake word | openWakeWord "hey jarvis" (acústica, antes do STT) · textual (fallback) |
| Mic / loopback | sounddevice, PyAudioWPatch |
| Tela / OCR | mss, Pillow, RapidOCR, pytesseract |
| LLM | groq, anthropic |
| Ponte | httpx (HTTP), websockets (WS) |
