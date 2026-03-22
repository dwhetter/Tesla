#pragma once
#include <string>
#include <stdexcept>
#include <cstdlib>

enum class LLMBackend { Anthropic, Ollama };

struct Config {
    // LLM backend selection
    LLMBackend  llm_backend;

    // Anthropic (set ANTHROPIC_API_KEY)
    std::string anthropic_api_key;

    // Ollama (no key needed — just run  ollama serve)
    std::string ollama_url;        // default: http://localhost:11434
    std::string ollama_model;      // default: llama3.2

    // Speech-to-text
    std::string whisper_binary;    // path to whisper-cpp binary
    std::string whisper_model;     // path to ggml model file

    // Lesson settings
    std::string target_language;   // language being learned
    int         difficulty_level;  // 1 (beginner) – 5 (advanced)
    int         recording_seconds; // mic recording duration

    static Config from_env() {
        Config cfg;

        const char* key = std::getenv("ANTHROPIC_API_KEY");

        if (key && std::string(key).length() > 0) {
            // Anthropic mode
            cfg.llm_backend        = LLMBackend::Anthropic;
            cfg.anthropic_api_key  = key;
        } else {
            // Ollama mode — no API key required
            cfg.llm_backend  = LLMBackend::Ollama;
            const char* url  = std::getenv("OLLAMA_URL");
            cfg.ollama_url   = url ? url : "http://localhost:11434";
            const char* mdl  = std::getenv("OLLAMA_MODEL");
            cfg.ollama_model = mdl ? mdl : "llama3.2";
        }

        const char* wmodel = std::getenv("WHISPER_MODEL");
        if (!wmodel || std::string(wmodel).empty())
            throw std::runtime_error(
                "WHISPER_MODEL environment variable is not set\n"
                "Set it to the path of a downloaded ggml model file, e.g.:\n"
                "  export WHISPER_MODEL=$HOME/.whisper-models/ggml-base.bin\n"
                "Run ./setup.sh to download the model automatically.");
        cfg.whisper_model = wmodel;

        const char* bin = std::getenv("WHISPER_BIN");
        cfg.whisper_binary = bin ? bin : "whisper-cpp";

        const char* lang = std::getenv("TARGET_LANGUAGE");
        cfg.target_language = lang ? lang : "Spanish";

        const char* level = std::getenv("DIFFICULTY");
        cfg.difficulty_level = level ? std::stoi(level) : 1;
        if (cfg.difficulty_level < 1 || cfg.difficulty_level > 5)
            throw std::runtime_error("DIFFICULTY must be 1–5");

        const char* secs = std::getenv("RECORDING_SECONDS");
        cfg.recording_seconds = secs ? std::stoi(secs) : 8;

        return cfg;
    }
};
