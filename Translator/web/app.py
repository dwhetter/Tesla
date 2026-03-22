import os
import json
import tempfile
import subprocess
from threading import Lock, Thread
from flask import Flask, request, jsonify, send_from_directory
import requests

app = Flask(__name__, static_folder="static", static_url_path="")

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
OLLAMA_URL        = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL      = os.getenv("OLLAMA_MODEL", "llama3.2")
WHISPER_BIN       = os.getenv("WHISPER_BIN", "whisper-cpp")
WHISPER_MODEL     = os.getenv("WHISPER_MODEL", "")

PHRASES_FILE = os.path.join(os.path.dirname(__file__), "phrases.json")
VOCAB_FILE = os.path.join(os.path.dirname(__file__), "vocab.json")
LEVELS = {
    1: "complete beginner (basic greetings, simple phrases)",
    2: "elementary (basic conversations, common situations)",
    3: "intermediate (varied topics, some complex structures)",
    4: "upper-intermediate (idiomatic expressions, nuanced language)",
    5: "advanced (complex discussions, formal language)",
}

_db_lock = Lock()


# ── Phrase file helpers ───────────────────────────────────────────────────────

def load_db() -> dict:
    if os.path.exists(PHRASES_FILE):
        with open(PHRASES_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_db(db: dict):
    with open(PHRASES_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)


def db_get(language: str, level: str):
    db = load_db()
    return db.get(language, {}).get(level)


def db_set(language: str, level: str, phrases: list):
    with _db_lock:
        db = load_db()
        db.setdefault(language, {})[level] = phrases
        save_db(db)


# ── LLM helper ───────────────────────────────────────────────────────────────

def llm_chat(system: str, user_message: str) -> str:
    if ANTHROPIC_API_KEY:
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-opus-4-6",
                "max_tokens": 2048,
                "system": system,
                "messages": [{"role": "user", "content": user_message}],
            },
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json()["content"][0]["text"]
    else:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": user_message})
        resp = requests.post(
            f"{OLLAMA_URL}/api/chat",
            json={"model": OLLAMA_MODEL, "messages": messages, "stream": False},
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json()["message"]["content"]


def extract_json(text: str) -> dict:
    start = text.find("{")
    end   = text.rfind("}") + 1
    if start == -1 or end == 0:
        raise ValueError(f"No JSON object in LLM response: {text}")
    return json.loads(text[start:end])


def generate_phrases_for_level(language: str, level: int, name: str = "") -> list:
    """Call LLM and return 10 phrases. Does NOT touch the file."""
    level_desc = LEVELS.get(level, LEVELS[1])
    name_hint  = f" The learner's name is {name}; naturally include their name in 1-2 phrases (e.g. introductions)." if name else ""
    system = "You are a language learning curriculum designer."
    prompt = (
        f"Create exactly 10 distinct practice phrases in {language} "
        f"for a {level_desc} learner. Cover a variety of everyday topics.{name_hint}\n"
        "Respond with ONLY a valid JSON array, no markdown:\n"
        '[{"phrase":"...","translation":"...","context":"...","tips":"..."}, ...]'
    )
    raw   = llm_chat(system, prompt)
    start = raw.find("[")
    end   = raw.rfind("]") + 1
    if start == -1 or end == 0:
        raise ValueError(f"No JSON array in LLM response: {raw}")
    return json.loads(raw[start:end])


# ── Audio helpers ─────────────────────────────────────────────────────────────

def convert_to_wav(input_path: str, output_path: str):
    subprocess.run(
        ["ffmpeg", "-i", input_path, "-ar", "16000", "-ac", "1",
         "-acodec", "pcm_s16le", output_path, "-y"],
        check=True, capture_output=True,
    )


def transcribe(wav_path: str) -> str:
    if not WHISPER_MODEL:
        raise RuntimeError("WHISPER_MODEL env var not set")
    output_base = wav_path.replace(".wav", "_out")
    subprocess.run(
        [WHISPER_BIN, "-m", WHISPER_MODEL, "-l", "auto",
         "--no-timestamps", "-otxt", "-of", output_base, "-f", wav_path],
        check=True, capture_output=True,
    )
    txt_path = output_base + ".txt"
    with open(txt_path) as f:
        text = f.read().strip()
    os.remove(txt_path)
    text = " ".join(w for w in text.split() if not (w.startswith("[") and w.endswith("]")))
    return text.strip()


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/api/phrases/batch")
def phrases_batch():
    """Return phrases for language+level. Always serves from file if present."""
    language = request.args.get("language", "Spanish")
    level    = request.args.get("level", "1")

    cached = db_get(language, level)
    if cached:
        return jsonify(cached)

    name = request.args.get("name", "").strip()
    try:
        phrases = _validate_phrases(generate_phrases_for_level(language, int(level), name))
        db_set(language, level, phrases)
        return jsonify(phrases)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/phrases/generate-all", methods=["POST"])
def generate_all():
    """Generate phrases for any missing levels of a language and save to file."""
    language = request.json.get("language", "Spanish")
    name     = request.json.get("name", "").strip()
    errors   = {}
    results  = {}

    for level in range(1, 6):
        cached = db_get(language, str(level))
        if cached:
            results[str(level)] = cached
            continue
        try:
            phrases = _validate_phrases(generate_phrases_for_level(language, level, name))
            db_set(language, str(level), phrases)
            results[str(level)] = phrases
        except Exception as e:
            errors[str(level)] = str(e)

    if errors:
        return jsonify({"results": results, "errors": errors}), 207
    return jsonify(results)


@app.route("/api/phrases/refresh", methods=["POST"])
def refresh_level():
    """Force-regenerate phrases for a specific language+level, overwriting the file."""
    language = request.json.get("language", "Spanish")
    level    = str(request.json.get("level", "1"))
    name     = request.json.get("name", "").strip()

    try:
        phrases = _validate_phrases(generate_phrases_for_level(language, int(level), name))
        db_set(language, level, phrases)
        return jsonify(phrases)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/evaluate", methods=["POST"])
def evaluate():
    phrase      = request.form.get("phrase", "")
    translation = request.form.get("translation", "")
    language    = request.form.get("language", "Spanish")
    name        = request.form.get("name", "").strip()
    audio_file  = request.files.get("audio")

    if not audio_file:
        return jsonify({"error": "No audio file uploaded"}), 400

    with tempfile.TemporaryDirectory() as tmp:
        raw_path = os.path.join(tmp, "recording.webm")
        wav_path = os.path.join(tmp, "recording.wav")
        audio_file.save(raw_path)

        try:
            convert_to_wav(raw_path, wav_path)
        except subprocess.CalledProcessError:
            return jsonify({"error": "ffmpeg not found — install with: brew install ffmpeg"}), 500

        try:
            transcription = transcribe(wav_path)
        except Exception as e:
            return jsonify({"error": f"Transcription failed: {e}"}), 500

    if not transcription:
        return jsonify({"error": "No speech detected — try again"}), 422

    student    = name if name else "the student"
    system = f"You are a {language} language tutor evaluating spoken practice."
    prompt = (
        f'Target phrase: "{phrase}"\n'
        f'English meaning: "{translation}"\n'
        f'Student said: "{transcription}"\n\n'
        f"Evaluate {student}'s attempt. Minor transcription errors are expected."
        + (f" Address them by name ({name}) in your feedback." if name else "") + "\n"
        "Respond with ONLY valid JSON, no markdown:\n"
        '{"score":8,"accuracy":"Good","went_well":"...","improvements":"...","encouragement":"..."}'
    )

    try:
        raw    = llm_chat(system, prompt)
        result = extract_json(raw)
        result["transcription"] = transcription
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/config")
def config_info():
    backend = "Anthropic (Claude)" if ANTHROPIC_API_KEY else f"Ollama ({OLLAMA_MODEL})"
    db      = load_db()
    return jsonify({
        "backend": backend,
        "whisper_model": bool(WHISPER_MODEL),
        "stored_languages": list(db.keys()),
        "phrases_file": PHRASES_FILE,
    })


SEED_LANGUAGES = [
    "Spanish", "French", "German", "Italian",
    "Japanese", "Mandarin", "Portuguese",
]

REQUIRED_PHRASE_KEYS = {"phrase", "translation", "context", "tips"}


def _validate_phrases(phrases: list) -> list:
    """Keep only entries that have all required keys; fill missing optional fields with empty string."""
    out = []
    for p in phrases:
        if not isinstance(p, dict):
            continue
        if not {"phrase", "translation"}.issubset(p.keys()):
            continue  # skip unusable entries
        out.append({k: p.get(k, "") for k in ("phrase", "translation", "context", "tips")})
    return out


def _validate_vocab(words: list) -> list:
    out = []
    for w in words:
        if not isinstance(w, dict):
            continue
        if not {"word", "translation"}.issubset(w.keys()):
            continue
        out.append({k: w.get(k, "") for k in
                    ("word", "translation", "pronunciation", "example", "example_translation", "category")})
    return out


def vocab_db_get(language: str, level: str):
    if not os.path.exists(VOCAB_FILE):
        return None
    with open(VOCAB_FILE, encoding="utf-8") as f:
        db = json.load(f)
    return db.get(language, {}).get(level)


def vocab_db_set(language: str, level: str, words: list):
    with _db_lock:
        db = {}
        if os.path.exists(VOCAB_FILE):
            with open(VOCAB_FILE, encoding="utf-8") as f:
                db = json.load(f)
        db.setdefault(language, {})[level] = words
        with open(VOCAB_FILE, "w", encoding="utf-8") as f:
            json.dump(db, f, ensure_ascii=False, indent=2)


def generate_vocab_for_level(language: str, level: int, name: str = "") -> list:
    level_desc = LEVELS.get(level, LEVELS[1])
    name_hint  = f" The learner's name is {name}." if name else ""
    system = "You are a language learning vocabulary curriculum designer."
    prompt = (
        f"Create exactly 15 vocabulary words in {language} "
        f"for a {level_desc} learner.{name_hint} "
        "Cover a variety of everyday categories (food, travel, family, emotions, etc.).\n"
        f"'word' must be the {language} word. 'translation' must be the English meaning.\n"
        "Respond with ONLY a valid JSON array, no markdown:\n"
        '[{"word":"hola","translation":"hello","pronunciation":"OH-lah",'
        '"example":"Hola, ¿cómo estás?","example_translation":"Hello, how are you?","category":"greetings"}, ...]'
    )
    raw   = llm_chat(system, prompt)
    start = raw.find("[")
    end   = raw.rfind("]") + 1
    if start == -1 or end == 0:
        raise ValueError(f"No JSON array in LLM response: {raw}")
    return json.loads(raw[start:end])


@app.route("/api/vocab/batch")
def vocab_batch():
    language = request.args.get("language", "Spanish")
    level    = request.args.get("level", "1")

    cached = vocab_db_get(language, level)
    if cached:
        return jsonify(cached)

    name = request.args.get("name", "").strip()
    try:
        words = _validate_vocab(generate_vocab_for_level(language, int(level), name))
        vocab_db_set(language, level, words)
        return jsonify(words)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/vocab/refresh", methods=["POST"])
def vocab_refresh():
    language = request.json.get("language", "Spanish")
    level    = str(request.json.get("level", "1"))
    name     = request.json.get("name", "").strip()

    try:
        words = _validate_vocab(generate_vocab_for_level(language, int(level), name))
        vocab_db_set(language, level, words)
        return jsonify(words)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/vocab/evaluate", methods=["POST"])
def vocab_evaluate():
    word        = request.form.get("word", "")
    translation = request.form.get("translation", "")
    language    = request.form.get("language", "Spanish")
    name        = request.form.get("name", "").strip()
    audio_file  = request.files.get("audio")

    if not audio_file:
        return jsonify({"error": "No audio file uploaded"}), 400

    with tempfile.TemporaryDirectory() as tmp:
        raw_path = os.path.join(tmp, "recording.webm")
        wav_path = os.path.join(tmp, "recording.wav")
        audio_file.save(raw_path)

        try:
            convert_to_wav(raw_path, wav_path)
        except subprocess.CalledProcessError:
            return jsonify({"error": "ffmpeg not found — install with: brew install ffmpeg"}), 500

        try:
            transcription = transcribe(wav_path)
        except Exception as e:
            return jsonify({"error": f"Transcription failed: {e}"}), 500

    if not transcription:
        return jsonify({"error": "No speech detected — try again"}), 422

    student = name if name else "the student"
    system  = f"You are a {language} language tutor evaluating vocabulary pronunciation."
    prompt  = (
        f'Vocabulary word: "{word}" → {language}: "{translation}"\n'
        f'{student.capitalize()} said: "{transcription}"\n\n'
        f"Evaluate how accurately {student} pronounced the {language} word."
        + (f" Address them by name ({name}) in encouragement." if name else "") + "\n"
        "Respond with ONLY valid JSON, no markdown:\n"
        '{"score":8,"accuracy":"Good","pronunciation_feedback":"...","usage_tip":"...","encouragement":"..."}'
    )

    try:
        raw    = llm_chat(system, prompt)
        result = extract_json(raw)
        result["transcription"] = transcription
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def _seed_phrases():
    """Generate any missing language+level combinations and add them to the existing file."""
    db = load_db()
    missing = [
        (lang, level)
        for lang in SEED_LANGUAGES
        for level in range(1, 6)
        if not db.get(lang, {}).get(str(level))
    ]
    if not missing:
        return
    print(f"Seeding {len(missing)} missing language/level combinations…")
    for language, level in missing:
        try:
            phrases = _validate_phrases(generate_phrases_for_level(language, level))
            db_set(language, str(level), phrases)
            print(f"  {language} level {level}: {len(phrases)} phrases")
        except Exception as e:
            print(f"  {language} level {level} failed: {e}")
    print("Seed complete.")


if __name__ == "__main__":
    print(f"Backend:       {'Anthropic' if ANTHROPIC_API_KEY else 'Ollama'}")
    print(f"Whisper model: {WHISPER_MODEL or '(not set)'}")
    print(f"Phrases file:  {PHRASES_FILE}")
    Thread(target=_seed_phrases, daemon=True).start()
    app.run(host="0.0.0.0", debug=True, port=5001)
