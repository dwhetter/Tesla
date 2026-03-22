# Language Tutor

A language learning app that presents spoken dialog for the user to repeat, then rates their response and gives feedback using an LLM.

## Project structure

```
Translator/
├── src/                   C++ CLI application
│   ├── main.cpp
│   ├── config.hpp         All env-var config in one place
│   ├── anthropic_client.cpp/.hpp   Claude API via libcurl
│   ├── ollama_client.cpp/.hpp      Ollama API via libcurl
│   ├── language_tutor.cpp/.hpp     Core tutor loop + LLM prompts
│   ├── audio_recorder.cpp/.hpp     Records mic audio via sox/ffmpeg
│   └── speech_to_text.cpp/.hpp     Transcribes via whisper-cpp CLI
├── web/                   Python + HTML web UI
│   ├── app.py             Flask backend (phrase gen + evaluation)
│   └── static/
│       ├── index.html
│       ├── style.css
│       └── app.js         MediaRecorder + fetch + history list
├── CMakeLists.txt
└── setup.sh               Installs deps + downloads whisper model
```

## Two frontends, one backend logic

Both the C++ CLI and the Python web server do the same thing:
1. Call an LLM (Anthropic or Ollama) to generate a practice phrase as JSON
2. Record the user's spoken response
3. Transcribe with `whisper-cpp`
4. Call the LLM again to rate accuracy and give feedback

## LLM backend selection

The LLM backend is chosen automatically at startup — no code changes needed:

| Env var set          | Backend used           |
|----------------------|------------------------|
| `ANTHROPIC_API_KEY`  | Claude (claude-opus-4-6) |
| neither              | Ollama (`llama3.2`)    |

Ollama env vars: `OLLAMA_URL` (default `http://localhost:11434`), `OLLAMA_MODEL` (default `llama3.2`).

## Required env vars

```bash
WHISPER_MODEL   # path to ggml model file, e.g. ~/.whisper-models/ggml-base.bin
WHISPER_BIN     # path to whisper-cpp binary (default: whisper-cpp)
```

Optional:
```bash
ANTHROPIC_API_KEY     # use Claude instead of Ollama
OLLAMA_MODEL          # default: llama3.2
TARGET_LANGUAGE       # CLI only, default: Spanish
DIFFICULTY            # CLI only, 1–5, default: 1
RECORDING_SECONDS     # CLI only, default: 8
```

## Build & run (C++ CLI)

```bash
./setup.sh                              # one-time: install deps, download model
mkdir build && cd build && cmake .. && make
export WHISPER_MODEL=$HOME/.whisper-models/ggml-base.bin
./language_tutor Spanish 2              # language + difficulty level
```

Dependencies: `brew install cmake sox whisper-cpp` + libcurl (pre-installed on macOS).
nlohmann/json is fetched automatically by CMake via FetchContent.

## Run (web UI)

```bash
cd web
pip install -r requirements.txt
brew install ffmpeg                     # needed to convert WebM → WAV
export WHISPER_MODEL=$HOME/.whisper-models/ggml-base.bin
python app.py
# open http://localhost:5000
```

The web UI uses the browser MediaRecorder API for audio, sends WebM to the Flask
server, converts to 16 kHz mono WAV with ffmpeg, and runs whisper-cpp for transcription.
Text-to-speech uses the browser's built-in SpeechSynthesis API.

## LLM prompt contracts

Both frontends expect JSON back from the LLM — no markdown wrappers.

**Phrase generation** returns:
```json
{ "phrase": "...", "translation": "...", "context": "...", "tips": "..." }
```

**Evaluation** returns:
```json
{ "score": 8, "accuracy": "Good", "went_well": "...", "improvements": "...", "encouragement": "..." }
```

Scores are 1–10. Accuracy values: `Perfect`, `Good`, `Fair`, `Poor`.
The web UI colours the score bar green (≥8), amber (≥5), red (<5).
