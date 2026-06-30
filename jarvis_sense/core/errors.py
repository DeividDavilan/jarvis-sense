"""Tratamento de erros resiliente.

Requisito do prompt: "nenhum módulo poderá derrubar o sistema; todo erro deverá
ser registrado, tratado e permitir recuperação automática".

Este módulo fornece:
- `JarvisSenseError` e subclasses: hierarquia de erros do domínio.
- `@safe` / `@safe_async`: decoradores que capturam exceções, registram no log
  do módulo e retornam um valor padrão em vez de propagar.
- `supervise`: laço supervisor que reinicia uma corrotina de serviço que caia,
  com backoff — a base da "recuperação automática".
"""

from __future__ import annotations

import asyncio
import functools
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from .logging import get_logger

T = TypeVar("T")


class JarvisSenseError(Exception):
    """Erro base do Jarvis Sense."""


class ConfigurationError(JarvisSenseError):
    """Configuração ausente ou inválida (ex.: nenhum provedor de IA)."""


class AudioDeviceError(JarvisSenseError):
    """Falha ao abrir microfone ou dispositivo de loopback."""


class EngineUnavailableError(JarvisSenseError):
    """Motor (TTS/STT/OCR/visão) indisponível ou dependência não instalada."""


def safe(default: Any = None, *, module: str = "Jarvis") -> Callable:
    """Decorador para funções SÍNCRONAS: captura tudo, loga e retorna `default`."""

    def decorator(func: Callable[..., T]) -> Callable[..., T | Any]:
        log = get_logger(module)

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T | Any:
            try:
                return func(*args, **kwargs)
            except JarvisSenseError as exc:
                log.error("%s: %s", func.__name__, exc)
            except Exception:  # noqa: BLE001
                log.exception("Erro inesperado em %s", func.__name__)
            return default

        return wrapper

    return decorator


def safe_async(default: Any = None, *, module: str = "Jarvis") -> Callable:
    """Versão assíncrona de `safe`, para corrotinas."""

    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T | Any]]:
        log = get_logger(module)

        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T | Any:
            try:
                return await func(*args, **kwargs)
            except JarvisSenseError as exc:
                log.error("%s: %s", func.__name__, exc)
            except Exception:  # noqa: BLE001
                log.exception("Erro inesperado em %s", func.__name__)
            return default

        return wrapper

    return decorator


async def supervise(
    factory: Callable[[], Awaitable[None]],
    *,
    name: str,
    module: str = "Jarvis",
    max_backoff: float = 30.0,
) -> None:
    """Executa `factory()` e a reinicia se cair — recuperação automática.

    `factory` deve ser uma corrotina de longa duração (o laço de um serviço).
    Se ela levantar, o erro é registrado e o serviço reinicia após um backoff
    exponencial (até `max_backoff`s). Cancelamento (`CancelledError`) é
    propagado normalmente para permitir shutdown limpo.
    """
    log = get_logger(module)
    backoff = 1.0
    while True:
        try:
            await factory()
            return  # terminou normalmente
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            log.exception("Serviço '%s' caiu; reiniciando em %.0fs", name, backoff)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, max_backoff)
