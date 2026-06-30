"""Ponte Node ↔ Python.

- `jarvis_client`: cliente HTTP das APIs JÁ EXISTENTES do Jarvis web (dispara
  tarefas, lista agentes). NÃO modifica o app web — apenas o consome.
- `ws_server`: servidor WebSocket que publica os eventos de percepção (aditivo),
  para um futuro Electron/HUD consumir.
- `dispatch`: serviço que transforma comandos de voz em tarefas no Jarvis.
"""
