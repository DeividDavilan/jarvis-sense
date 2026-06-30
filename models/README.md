# Modelos de wake word customizados

Coloque aqui os modelos `.onnx` (ou `.tflite`) que você treinar no openWakeWord
— por exemplo `penelopo.onnx`.

Depois aponte no `.env`:

```ini
JARVIS_WAKE_MODEL=models/penelopo.onnx
```

Passo a passo de como treinar e calibrar: **`../docs/WAKE_WORD.md`**.
