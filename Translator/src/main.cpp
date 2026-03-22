#include "config.hpp"
#include "anthropic_client.hpp"
#include "ollama_client.hpp"
#include "language_tutor.hpp"
#include <iostream>
#include <memory>
#include <stdexcept>

static void print_usage(const char* argv0) {
    std::cerr
        << "Usage: " << argv0 << " [language] [difficulty 1-5]\n\n"
        << "Examples:\n"
        << "  " << argv0 << "\n"
        << "  " << argv0 << " French\n"
        << "  " << argv0 << " Japanese 3\n\n"
        << "LLM backend (pick one):\n"
        << "  ANTHROPIC_API_KEY   Set this to use Claude (cloud)\n"
        << "  -- or --\n"
        << "  (unset)             Falls back to Ollama (local, no key needed)\n"
        << "  OLLAMA_URL          Ollama server URL (default: http://localhost:11434)\n"
        << "  OLLAMA_MODEL        Model to use     (default: llama3.2)\n\n"
        << "Required:\n"
        << "  WHISPER_MODEL       Path to a whisper.cpp ggml model file\n\n"
        << "Optional:\n"
        << "  WHISPER_BIN         Path to whisper-cpp binary (default: whisper-cpp)\n"
        << "  TARGET_LANGUAGE     Language to learn (default: Spanish)\n"
        << "  DIFFICULTY          Level 1-5 (default: 1)\n"
        << "  RECORDING_SECONDS   Recording duration in seconds (default: 8)\n";
}

int main(int argc, char* argv[]) {
    try {
        Config config = Config::from_env();

        // Command-line args override environment variables
        if (argc > 1) config.target_language  = argv[1];
        if (argc > 2) config.difficulty_level = std::stoi(argv[2]);

        // Select LLM backend
        std::unique_ptr<LLMClient> llm;
        if (config.llm_backend == LLMBackend::Anthropic) {
            std::cout << "Backend: Anthropic Claude\n";
            llm = std::make_unique<AnthropicClient>(config.anthropic_api_key);
        } else {
            std::cout << "Backend: Ollama (" << config.ollama_url
                      << "  model: " << config.ollama_model << ")\n"
                      << "Make sure Ollama is running:  ollama serve\n";
            llm = std::make_unique<OllamaClient>(config.ollama_url, config.ollama_model);
        }

        LanguageTutor tutor(config, std::move(llm));
        tutor.run();

    } catch (const std::invalid_argument& e) {
        std::cerr << "Invalid argument: " << e.what() << "\n";
        print_usage(argv[0]);
        return 1;
    } catch (const std::exception& e) {
        std::cerr << "\nError: " << e.what() << "\n\n";
        print_usage(argv[0]);
        return 1;
    }

    return 0;
}
