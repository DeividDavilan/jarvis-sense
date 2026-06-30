"""Jarvis Sense — camada de percepção (voz, áudio, visão) do Jarvis.

Subsistema Python independente que roda no Windows Terminal. Ouve o microfone,
captura o áudio do sistema (loopback), enxerga/lê a tela (OCR) e fala com a voz
única do Jarvis — comandando o Jarvis web existente pelas APIs já publicadas,
sem alterá-lo.

Arquitetura: Clean Architecture + SOLID. Cada capacidade é um módulo isolado
que se comunica exclusivamente pelo barramento de eventos (`core.events`).
"""

__version__ = "0.1.0"
