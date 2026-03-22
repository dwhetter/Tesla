#pragma once
#include "anthropic_client.hpp"  // for LLMClient + ChatMessage
#include <string>

// Calls a local Ollama server (http://localhost:11434 by default).
// No API key required — just run:  ollama serve  and  ollama pull <model>
class OllamaClient : public LLMClient {
public:
    // base_url: e.g. "http://localhost:11434"
    // model:    e.g. "llama3.2", "mistral", "gemma3"
    OllamaClient(const std::string& base_url, const std::string& model);

    std::string chat(const std::string& system_prompt,
                     const std::vector<ChatMessage>& messages,
                     int max_tokens = 512) override;

private:
    std::string base_url_;
    std::string model_;

    static size_t write_callback(void* contents, size_t size, size_t nmemb,
                                 std::string* out);
};
