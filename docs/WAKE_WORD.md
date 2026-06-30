# Wake word — personalização

O gatilho de ativação é configurável e tem **dois modos** (`JARVIS_WAKE_MODE`):

| Modo | Como funciona | Personalização |
| ---- | ------------- | -------------- |
| `acoustic` (padrão) | openWakeWord ouve o áudio cru e dispara **antes** do STT | nome pré-treinado **ou** modelo `.onnx` próprio |
| `text` | transcreve tudo e procura a palavra no texto | `JARVIS_WAKE_WORD` = qualquer palavra |

---

## Modo textual — qualquer palavra, sem treino

O mais simples. Funciona com qualquer STT, sem modelo:

```ini
JARVIS_WAKE_MODE=text
JARVIS_WAKE_WORD=penelopo      # ou "sexta-feira", "computador"…
```

A detecção é por texto (normaliza acentos/caixa). Custo: transcreve toda fala.

---

## Modo acústico — gatilho dedicado, eficiente

### 1) Usar um modelo pré-treinado

Liste os disponíveis:

```bash
python -m jarvis_sense.speech.wake_demo --list
# alexa · hey_jarvis · hey_mycroft · hey_rhasspy · …
```

Configure um (ou vários, separados por vírgula):

```ini
JARVIS_WAKE_MODE=acoustic
JARVIS_WAKE_MODEL=hey_jarvis
# vários gatilhos ao mesmo tempo:
# JARVIS_WAKE_MODEL=hey_jarvis, alexa
```

### 2) Usar um modelo CUSTOMIZADO (ex.: "Penelopo")

openWakeWord não traz "penelopo" pronto — você **treina** um modelo (gratuito) e
aponta o arquivo `.onnx` aqui.

**Treinar (sem GPU local, ~1h, gratuito):**
1. Abra o notebook oficial de treino do openWakeWord no Google Colab
   (procure por *"openWakeWord automatic model training"* no repositório
   `dscripka/openWakeWord`).
2. Informe a frase (ex.: `penelopo`). O notebook **sintetiza** milhares de
   amostras com TTS e treina o modelo.
3. Baixe o `penelopo.onnx` gerado.

**Instalar no Jarvis Sense:**
```bash
# coloque o arquivo em jarvis-sense/models/
mkdir models   # se não existir
# copie penelopo.onnx para models/
```
```ini
JARVIS_WAKE_MODEL=models/penelopo.onnx
# combinar com um pré-treinado, se quiser:
# JARVIS_WAKE_MODEL=hey_jarvis, models/penelopo.onnx
```
Caminhos relativos são resolvidos a partir da raiz `jarvis-sense/`. Modelos
`.onnx` usam o onnxruntime que já temos; `.tflite` exigem `tflite-runtime`
(ajuste `JARVIS_WAKE_FRAMEWORK=tflite`).

### 3) Calibrar a sensibilidade

```bash
python -m jarvis_sense.speech.wake_demo
```
Abre o microfone e mostra a **pontuação ao vivo** do gatilho. Fale a palavra e
veja o score subir; ajuste o limiar:

```ini
JARVIS_WAKE_THRESHOLD=0.5   # menor = mais sensível (mais falsos positivos)
```

---

## Resumo das variáveis (`.env`)

| Variável | Default | Descrição |
| -------- | ------- | --------- |
| `JARVIS_WAKE_MODE` | `acoustic` | `acoustic` ou `text` |
| `JARVIS_WAKE_MODEL` | `hey_jarvis` | nome(s) e/ou caminho(s) `.onnx`, por vírgula |
| `JARVIS_WAKE_THRESHOLD` | `0.5` | limiar de disparo (0–1) |
| `JARVIS_WAKE_FRAMEWORK` | _(infere)_ | `onnx` ou `tflite` |
| `JARVIS_WAKE_WORD` | `jarvis` | palavra do modo textual |

> Robustez: se o modo `acoustic` não conseguir carregar (lib/modelo ausente), o
> sistema **cai automaticamente para o modo textual** e avisa no log — nunca quebra.
