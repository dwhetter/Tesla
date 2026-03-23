# Language Tutor

A language learning app with two practice modes — phrases and vocabulary — where the user speaks responses that are transcribed and rated by an LLM.

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
│   ├── app.py             Flask backend (phrase + vocab gen, evaluation)
│   ├── generate.py        CLI tool to pre-generate phrases/vocab
│   ├── phrases.json       Cached phrases (language → level → list)
│   ├── vocab.json         Cached vocabulary (language → level → list)
│   ├── requirements.txt
│   └── static/
│       ├── index.html     Phrases practice page
│       ├── vocab.html     Vocabulary practice page
│       ├── style.css      Shared styles
│       ├── app.js         Phrases page logic
│       └── vocab.js       Vocabulary page logic
├── CMakeLists.txt
└── setup.sh               Installs deps + downloads whisper model
```

## Web UI — two practice modes

### Phrases (`index.html`)
1. LLM generates 10 practice phrases for the selected language + level
2. User listens (browser TTS) then records their spoken response
3. Whisper transcribes the audio
4. LLM scores accuracy and gives feedback

### Vocabulary (`vocab.html`)
1. LLM generates 15 vocabulary words for the selected language + level
2. Card shows the target-language word, English translation, pronunciation, and example sentence
3. User records themselves saying the word
4. LLM scores pronunciation and gives feedback

Both modes cache results in JSON files and share the same controls (language, level, name).

## LLM backend selection

Chosen automatically at startup — no code changes needed:

| Env var set          | Backend used             |
|----------------------|--------------------------|
| `ANTHROPIC_API_KEY`  | Claude (`claude-opus-4-6`) |
| neither              | Ollama (`llama3.2`)      |

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
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
brew install ffmpeg                     # needed to convert WebM → WAV
export WHISPER_MODEL=$HOME/.whisper-models/ggml-base.bin
python3 app.py
# open http://localhost:5001
# or on LAN: http://<your-ip>:5001
```

The web UI uses the browser MediaRecorder API for audio, sends WebM to the Flask
server, converts to 16 kHz mono WAV with ffmpeg, and runs whisper-cpp for transcription.
Text-to-speech uses the browser's built-in SpeechSynthesis API.

## Pre-generating content (generate.py)

Run from the `web/` directory (with venv activated) to pre-populate `phrases.json` and `vocab.json`:

```bash
python3 generate.py                              # all languages, all levels, both types
python3 generate.py --language Spanish           # one language
python3 generate.py --language Spanish --level 2 # one language + level
python3 generate.py --type vocab                 # vocabulary only
python3 generate.py --type phrases               # phrases only
python3 generate.py --force                      # ignore cache, regenerate
python3 generate.py --verbose                    # print each phrase/word as generated
```

## Caching behaviour

- `phrases.json` and `vocab.json` store generated content keyed by `language → level`.
- On page load the server always serves from the file if content exists.
- The **↺** button in the UI force-regenerates the current level and overwrites the cache.
- The **⚡ All Levels** button generates any missing levels (skips cached ones).
- `generate.py` follows the same skip-if-cached logic unless `--force` is passed.

## LLM prompt contracts

All responses are plain JSON — no markdown wrappers.

**Phrase generation** returns a JSON array:
```json
[{ "phrase": "...", "translation": "...", "context": "...", "tips": "..." }]
```

**Phrase evaluation** returns:
```json
{ "score": 8, "accuracy": "Good", "went_well": "...", "improvements": "...", "encouragement": "..." }
```

**Vocabulary generation** returns a JSON array:
```json
[{ "word": "<target-language>", "translation": "<english>", "pronunciation": "...", "example": "...", "example_translation": "...", "category": "..." }]
```

**Vocabulary evaluation** returns:
```json
{ "score": 8, "accuracy": "Good", "pronunciation_feedback": "...", "usage_tip": "...", "encouragement": "..." }
```

Scores are 1–10. Accuracy values: `Perfect`, `Good`, `Fair`, `Poor`.
The score bar is green (≥8), amber (≥5), red (<5).
