"""Configuração central (12-factor). Lê variáveis de ambiente e o arquivo `.env`
na raiz de `jarvis-sense/`, com defaults sãos para todos os campos.

Único ponto de verdade de configuração do sistema — nenhum módulo lê
`os.environ` diretamente; todos recebem (injeção de dependência) ou importam
`get_settings()`. Isso mantém os módulos testáveis e desacoplados do ambiente.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Raiz do projeto = jarvis-sense/ (dois níveis acima deste arquivo).
PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOG_DIR = PROJECT_ROOT / "logs"


class Settings(BaseSettings):
    """Configuração tipada do Jarvis Sense.

    Os nomes das variáveis de ambiente seguem o prefixo `JARVIS_` (exceto as
    chaves de provedor, que espelham as do Jarvis web: GROQ_API_KEY etc.).
    """

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Cérebro / LLM ---------------------------------------------------------
    groq_api_key: str | None = Field(default=None, alias="GROQ_API_KEY")
    groq_model: str = Field(default="llama-3.3-70b-versatile", alias="GROQ_MODEL")
    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    # Ollama local (offline, gratuito). Servidor já roda em localhost:11434.
    ollama_base_url: str = Field(default="http://localhost:11434", alias="JARVIS_OLLAMA_BASE_URL")
    ollama_model: str = Field(default="gemma3:4b", alias="JARVIS_OLLAMA_MODEL")
    # "groq" | "anthropic" | "ollama". Vazio = automático (Groq primeiro).
    llm_provider: str | None = Field(default=None, alias="JARVIS_LLM_PROVIDER")

    # --- TTS (voz do Jarvis) ---------------------------------------------------
    tts_engine: str = Field(default="edge", alias="JARVIS_TTS_ENGINE")
    tts_voice: str = Field(default="pt-BR-AntonioNeural", alias="JARVIS_TTS_VOICE")
    tts_rate: str = Field(default="+6%", alias="JARVIS_TTS_RATE")
    # Trecho (case-insensitive) do nome do dispositivo de SAÍDA a usar em vez do
    # padrão do Windows. O MCI/winmm (usado p/ tocar o MP3 do edge-tts) sofre do
    # mesmo problema do PortAudio: não atualiza o "padrão" após trocar p/ um
    # headset Bluetooth sem reiniciar o processo. Vazio = padrão do sistema.
    speaker_device_name: str = Field(default="", alias="JARVIS_SPEAKER_DEVICE_NAME")

    # --- STT (voz do usuário) --------------------------------------------------
    stt_engine: str = Field(default="groq", alias="JARVIS_STT_ENGINE")
    stt_groq_model: str = Field(default="whisper-large-v3-turbo", alias="JARVIS_STT_GROQ_MODEL")
    stt_local_model: str = Field(default="base", alias="JARVIS_STT_LOCAL_MODEL")
    # Pasta onde os pesos do faster-whisper são baixados (mantém fora do C:).
    stt_local_model_dir: str = Field(default="D:/models/whisper", alias="JARVIS_STT_LOCAL_MODEL_DIR")
    stt_language: str = Field(default="pt", alias="JARVIS_STT_LANGUAGE")
    # Trecho (case-insensitive) do nome do dispositivo de entrada a usar em vez
    # do padrão do Windows. Necessário porque o PortAudio (sounddevice) às vezes
    # não atualiza o "dispositivo padrão" depois de trocar o áudio padrão do
    # Windows (ex.: conectar um headset Bluetooth) sem reiniciar o processo.
    # Ex.: "soundcore" | "headset". Vazio = usa o padrão do sistema.
    mic_device_name: str = Field(default="", alias="JARVIS_MIC_DEVICE_NAME")
    # Ganho de software aplicado ao PCM cru do microfone (1.0 = sem alteração).
    # Alguns microfones internos captam muito baixo mesmo com o volume do
    # Windows em 100% — apps de chamada (Zoom/Teams) compensam com AGC próprio;
    # aqui é um ganho fixo simples. Amostras são "clipadas" para não estourar.
    mic_gain: float = Field(default=1.0, alias="JARVIS_MIC_GAIN")
    wake_word: str = Field(default="jarvis", alias="JARVIS_WAKE_WORD")
    # Modo de ativação: "acoustic" (openWakeWord, gatilho antes do STT) ou "text"
    # (transcreve tudo e detecta "jarvis" no texto). Acoustic cai para text se
    # o openWakeWord/modelo não estiver disponível.
    wake_mode: str = Field(default="acoustic", alias="JARVIS_WAKE_MODE")
    # Nome(s) pré-treinado(s) e/ou caminho(s) de modelo customizado (.onnx/.tflite),
    # separados por vírgula. Ex.: "hey_jarvis" ou "models/penelopo.onnx".
    wake_model: str = Field(default="hey_jarvis", alias="JARVIS_WAKE_MODEL")
    wake_threshold: float = Field(default=0.5, alias="JARVIS_WAKE_THRESHOLD")
    # Framework do openWakeWord ("onnx"|"tflite"). Vazio = inferir pelo modelo.
    wake_framework: str = Field(default="", alias="JARVIS_WAKE_FRAMEWORK")

    # --- Tela + OCR ------------------------------------------------------------
    ocr_engine: str = Field(default="rapidocr", alias="JARVIS_OCR_ENGINE")
    tesseract_cmd: str | None = Field(default=None, alias="JARVIS_TESSERACT_CMD")
    screen_interval: float = Field(default=1.5, alias="JARVIS_SCREEN_INTERVAL")

    # --- Visão semântica (LLM) -------------------------------------------------
    vision_engine: str = Field(default="off", alias="JARVIS_VISION_ENGINE")

    # --- Reatividade do cérebro ------------------------------------------------
    # True = cérebro reage ao áudio do sistema (loopback) quando transcrito.
    loopback_react: bool = Field(default=False, alias="JARVIS_LOOPBACK_REACT")
    # True = cérebro comenta proativamente o que vê na tela.
    vision_react: bool = Field(default=False, alias="JARVIS_VISION_REACT")

    # --- Ponte -----------------------------------------------------------------
    ws_host: str = Field(default="127.0.0.1", alias="JARVIS_SENSE_WS_HOST")
    ws_port: int = Field(default=8765, alias="JARVIS_SENSE_WS_PORT")
    web_url: str = Field(default="http://localhost:3000", alias="JARVIS_WEB_URL")

    # --- Logs ------------------------------------------------------------------
    log_level: str = Field(default="INFO", alias="JARVIS_LOG_LEVEL")

    # --- Helpers ---------------------------------------------------------------
    @property
    def has_groq(self) -> bool:
        return bool(self.groq_api_key)

    @property
    def has_anthropic(self) -> bool:
        return bool(self.anthropic_api_key)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Retorna a instância única de configuração (cacheada)."""
    return Settings()
