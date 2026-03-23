#!/usr/bin/env python3
"""
generate.py — Pre-generate phrases and/or vocabulary words from the command line.

Usage:
  python3 generate.py                              # all languages, all levels, both types
  python3 generate.py --language Spanish           # one language, all levels, both types
  python3 generate.py --language Spanish --level 2 # one language+level
  python3 generate.py --type phrases               # phrases only
  python3 generate.py --type vocab                 # vocabulary only
  python3 generate.py --force                      # regenerate even if already cached
"""

import argparse
import json
import os
import sys
from threading import Lock

import requests

# ── Config ────────────────────────────────────────────────────────────────────

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
OLLAMA_URL        = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL      = os.getenv("OLLAMA_MODEL", "llama3.2")

DIR          = os.path.dirname(__file__)
PHRASES_FILE = os.path.join(DIR, "phrases.json")
VOCAB_FILE   = os.path.join(DIR, "vocab.json")

LEVELS = {
    1: "complete beginner (basic greetings, simple phrases)",
    2: "elementary (basic conversations, common situations)",
    3: "intermediate (varied topics, some complex structures)",
    4: "upper-intermediate (idiomatic expressions, nuanced language)",
    5: "advanced (complex discussions, formal language)",
}

ALL_LANGUAGES = [
    "Spanish", "French", "German", "Italian",
    "Japanese", "Mandarin", "Portuguese",
]

_lock = Lock()

# ── LLM ──────────────────────────────────────────────────────────────────────

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

# ── Phrases ───────────────────────────────────────────────────────────────────

def _load_json(path):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}

def _save_json(path, db):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)

def phrases_get(language, level):
    return _load_json(PHRASES_FILE).get(language, {}).get(str(level))

def phrases_set(language, level, data):
    with _lock:
        db = _load_json(PHRASES_FILE)
        db.setdefault(language, {})[str(level)] = data
        _save_json(PHRASES_FILE, db)

def vocab_get(language, level):
    return _load_json(VOCAB_FILE).get(language, {}).get(str(level))

def vocab_set(language, level, data):
    with _lock:
        db = _load_json(VOCAB_FILE)
        db.setdefault(language, {})[str(level)] = data
        _save_json(VOCAB_FILE, db)

def _parse_array(raw, verbose=False):
    # Strip markdown code fences
    text = raw.strip()
    if text.startswith("```"):
        text = "\n".join(text.split("\n")[1:])
    if text.endswith("```"):
        text = "\n".join(text.split("\n")[:-1])
    start, end = text.find("["), text.rfind("]") + 1
    if start == -1 or end == 0:
        if verbose:
            print(f"    [raw response]\n{raw}\n")
        raise ValueError(f"No JSON array found in response: {raw[:200]}")
    try:
        return json.loads(text[start:end])
    except json.JSONDecodeError as e:
        if verbose:
            print(f"    [raw response]\n{raw}\n")
        raise ValueError(f"JSON parse error: {e}")

def gen_phrases(language, level, verbose=False):
    level_desc = LEVELS[level]
    system = "You are a language learning curriculum designer."
    prompt = (
        f"Create exactly 10 distinct practice phrases in {language} "
        f"for a {level_desc} learner. Cover a variety of everyday topics.\n"
        "Respond with ONLY a valid JSON array, no markdown:\n"
        '[{"phrase":"...","translation":"...","context":"...","tips":"..."}, ...]'
    )
    items = _parse_array(llm_chat(system, prompt), verbose)
    return [
        {k: p.get(k, "") for k in ("phrase", "translation", "context", "tips")}
        for p in items if isinstance(p, dict) and {"phrase", "translation"}.issubset(p)
    ]

def gen_vocab(language, level, verbose=False):
    level_desc = LEVELS[level]
    system = "You are a language learning vocabulary curriculum designer."
    prompt = (
        f"Create exactly 15 vocabulary words in {language} "
        f"for a {level_desc} learner. "
        "Cover a variety of everyday categories (food, travel, family, emotions, etc.).\n"
        f"'word' must be the {language} word. 'translation' must be the English meaning.\n"
        "Respond with ONLY a valid JSON array, no markdown:\n"
        '[{"word":"hola","translation":"hello","pronunciation":"OH-lah",'
        '"example":"Hola, ¿cómo estás?","example_translation":"Hello, how are you?","category":"greetings"}, ...]'
    )
    items = _parse_array(llm_chat(system, prompt), verbose)
    return [
        {k: w.get(k, "") for k in ("word", "translation", "pronunciation", "example", "example_translation", "category")}
        for w in items if isinstance(w, dict) and {"word", "translation"}.issubset(w)
    ]

# ── CLI ───────────────────────────────────────────────────────────────────────

def print_phrases(data):
    for i, p in enumerate(data, 1):
        print(f"    {i:2}. {p['phrase']}")
        print(f"        → {p['translation']}")
        if p.get('context'):
            print(f"        context: {p['context']}")
        if p.get('tips'):
            print(f"        tips:    {p['tips']}")

def print_vocab(data):
    for i, w in enumerate(data, 1):
        pron = f"  /{w['pronunciation']}/" if w.get('pronunciation') else ""
        print(f"    {i:2}. {w['word']}{pron}  →  {w['translation']}"
              + (f"  [{w['category']}]" if w.get('category') else ""))
        if w.get('example'):
            print(f"        \"{w['example']}\"  —  {w.get('example_translation', '')}")

def run(language, level, do_phrases, do_vocab, force, verbose):
    errors = 0
    if do_phrases:
        if not force and phrases_get(language, level):
            print(f"  [skip]  {language} L{level} phrases (cached)")
        else:
            try:
                data = gen_phrases(language, level, verbose)
                phrases_set(language, level, data)
                print(f"  [ok]    {language} L{level} phrases ({len(data)} items)")
                if verbose:
                    print_phrases(data)
            except Exception as e:
                print(f"  [error] {language} L{level} phrases: {e}", file=sys.stderr)
                errors += 1
    if do_vocab:
        if not force and vocab_get(language, level):
            print(f"  [skip]  {language} L{level} vocab (cached)")
        else:
            try:
                data = gen_vocab(language, level, verbose)
                vocab_set(language, level, data)
                print(f"  [ok]    {language} L{level} vocab ({len(data)} items)")
                if verbose:
                    print_vocab(data)
            except Exception as e:
                print(f"  [error] {language} L{level} vocab: {e}", file=sys.stderr)
                errors += 1
    return errors

def main():
    parser = argparse.ArgumentParser(description="Pre-generate phrase and vocabulary data.")
    parser.add_argument("--language", "-l", choices=ALL_LANGUAGES,
                        help="Language to generate (default: all)")
    parser.add_argument("--level", "-n", type=int, choices=range(1, 6),
                        help="Level 1–5 to generate (default: all)")
    parser.add_argument("--type", "-t", choices=["phrases", "vocab", "both"],
                        default="both", help="What to generate (default: both)")
    parser.add_argument("--force", "-f", action="store_true",
                        help="Regenerate even if already cached")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Print each generated phrase/word after generation")
    args = parser.parse_args()

    languages  = [args.language] if args.language else ALL_LANGUAGES
    levels     = [args.level]    if args.level    else list(LEVELS.keys())
    do_phrases = args.type in ("phrases", "both")
    do_vocab   = args.type in ("vocab",   "both")

    backend = "Anthropic (Claude)" if ANTHROPIC_API_KEY else f"Ollama ({OLLAMA_MODEL})"
    total   = len(languages) * len(levels) * (do_phrases + do_vocab)
    print(f"Backend: {backend}")
    print(f"Generating up to {total} item(s): languages={languages} levels={levels} type={args.type} force={args.force}\n")

    errors = sum(run(lang, lvl, do_phrases, do_vocab, args.force, args.verbose)
                 for lang in languages for lvl in levels)

    print(f"\nDone. {errors} error(s).")
    sys.exit(1 if errors else 0)

if __name__ == "__main__":
    main()
