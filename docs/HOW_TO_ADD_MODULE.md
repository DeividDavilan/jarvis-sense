# Como adicionar módulos e motores

A arquitetura foi desenhada para crescer **sem reescrita**. Há dois cenários comuns.

---

## A) Adicionar um novo MOTOR a um módulo existente

Ex.: trocar/adicionar um motor de TTS (ElevenLabs), STT (Whisper.cpp), OCR
(PaddleOCR), visão (Gemini) ou LLM (modelo local).

1. **Implemente a interface** do módulo num novo adaptador. Ex.: `tts/adapters/elevenlabs.py`:
   ```python
   class ElevenLabsTTS:
       name = "elevenlabs"
       async def is_available(self) -> bool: ...
       async def speak(self, text: str) -> None: ...
   ```
   A interface está em `<modulo>/interfaces.py` (`ITTS`, `ISTT`, `IOCR`, `IVision`,
   `ILLMProvider`). Use `is_available()` para checar credenciais/dependências.

2. **Registre na fábrica** do módulo (`<modulo>/services.py` ou `<modulo>/config.py`):
   ```python
   registry = {
       "edge": lambda: EdgeTTS(voice),
       "sapi": lambda: SapiTTS(voice),
       "elevenlabs": lambda: ElevenLabsTTS(voice),   # ← novo
   }
   ```

3. **Selecione via `.env`** (ex.: `JARVIS_TTS_ENGINE=elevenlabs`). Adicione a chave
   nova em `core/config.py` se precisar de credencial.

4. **Teste com um dublê** (sem hardware/rede) em `<modulo>/tests/`.

> Nenhum outro arquivo muda. Quem chama `TTSService.speak()` não sabe (nem precisa
> saber) qual motor está ativo — é o Princípio Aberto/Fechado na prática.

### Motores já previstos como adaptadores futuros
- **TTS**: ElevenLabs, OpenAI, Piper.
- **STT**: Whisper.cpp, Vosk.
- **Visão**: Claude (já incluso), GPT-4o, Gemini, YOLO/OpenCV.
- **LLM**: OpenAI, modelos locais (Ollama/llama.cpp).
- **Wake word acústica**: openWakeWord/Porcupine (hoje a detecção é textual).

---

## B) Adicionar um MÓDULO de capacidade novo

Ex.: `automation` (controlar o mouse/teclado), `notifications`, etc.

1. **Crie a pasta** `jarvis_sense/<modulo>/` com o layout padrão:
   ```
   <modulo>/
   ├── __init__.py
   ├── interfaces.py   # contratos (Protocol)
   ├── models.py       # dataclasses do domínio
   ├── services.py     # lógica + um Service (laço) se for de longa duração
   ├── config.py       # fábrica + leitura de Settings
   ├── utils.py
   └── tests/
   ```

2. **Comunique-se só por eventos.** Publique/assine em `core/events.py`; se precisar
   de um evento novo, adicione-o em `core/event_types.py` (dataclass `frozen` com
   `name: ClassVar[EventName]`). Nunca importe outro módulo de capacidade
   diretamente — o ponto de ligação é o composition root.

3. **Implemente o `Service`** (se for um laço): uma classe com `name: str` e
   `async def run(self)`, respeitando cancelamento. Use `@safe_async` nos handlers
   para isolamento de erros.

4. **Registre no composition root** (`services/app.py` → `assemble()`):
   ```python
   from ..automation.services import AutomationService
   self.manager.register(AutomationService(self.settings, self.bus))
   ```
   O `ServiceManager` cuida de subir sob supervisão e derrubar com limpeza.

5. **Degrade com elegância:** se o módulo depende de uma lib nativa, cheque a
   disponibilidade no início do `run()` e, se faltar, **logue e retorne** (não
   levante) — o resto do sistema continua de pé.

6. **Adicione testes** em `<modulo>/tests/` usando dublês (sem hardware).

---

## Convenções

- **Interfaces** = `Protocol` com `@runtime_checkable`.
- **Modelos** = `@dataclass(frozen=True, slots=True)`.
- **Config** lida apenas em `core/config.py` (pydantic); módulos recebem `Settings`.
- **Logs** via `get_logger("NomeDoModulo")` — nunca `print`.
- **Erros** isolados com `@safe`/`@safe_async`; serviços longos sob `supervise`.
- **pt-BR** nas mensagens de UX/voz; **código e identificadores em inglês**.
