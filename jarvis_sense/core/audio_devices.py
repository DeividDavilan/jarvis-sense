"""Resolução de dispositivo de áudio por nome, preferindo a API MME.

O Windows expõe o mesmo dispositivo físico várias vezes através de APIs de
áudio diferentes (MME, DirectSound, WASAPI, WDM-KS) — cada uma com seu próprio
índice no `sounddevice`/PortAudio. Nem todas funcionam igual: WDM-KS é acesso
de baixo nível e, neste projeto, falha consistentemente ao abrir com os
parâmetros genéricos que usamos (16 kHz mono) — inclusive para "fantasmas" de
dispositivos Bluetooth pareados mas não conectados no momento. Por isso ela é
excluída da busca; MME é a preferida entre as que restam.
"""

from __future__ import annotations

# Ordem de preferência das host APIs do PortAudio no Windows. WDM-KS de fora:
# abre com sucesso mas falha ao iniciar (ou nem abre) neste projeto/hardware.
_HOSTAPI_PREFERENCE = ("MME", "Windows WASAPI", "Windows DirectSound")


def resolve_device_by_name(sd, name_hint: str, *, kind: str) -> int | None:
    """Procura um dispositivo cujo nome contenha `name_hint` (case-insensitive).

    `kind` é `"input"` ou `"output"`. Entre múltiplos matches (o mesmo hardware
    aparece em várias host APIs), prefere a API mais compatível. Retorna
    `None` (padrão do sistema) se nenhum match aparecer numa API compatível —
    ex.: um headset Bluetooth pareado mas desconectado só deixa um "fantasma"
    na WDM-KS, que não conta como match válido.
    """
    name_hint = name_hint.strip().lower()
    if not name_hint:
        return None

    hostapis = sd.query_hostapis()
    channel_key = "max_input_channels" if kind == "input" else "max_output_channels"
    devices = sd.query_devices()

    def _api_rank(d) -> int | None:
        api_name = hostapis[d["hostapi"]]["name"]
        try:
            return _HOSTAPI_PREFERENCE.index(api_name)
        except ValueError:
            return None  # API não suportada (ex.: WDM-KS) — descarta o candidato

    candidates = [
        (i, d, rank)
        for i, d in enumerate(devices)
        if d[channel_key] > 0
        and name_hint in d["name"].lower()
        and (rank := _api_rank(d)) is not None
    ]
    if not candidates:
        return None

    candidates.sort(key=lambda item: item[2])
    return candidates[0][0]
