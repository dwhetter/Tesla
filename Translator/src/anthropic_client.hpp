#pragma once
#include <string>
#include <vector>

struct ChatMessage {
    std::string role;     // "user" or "assistant"
    std::string content;
};

// Common interface — implemented by AnthropicClient and OllamaClient
class LLMClient {
public:
    virtual std::string chat(const std::string& system_prompt,
                             const std::vector<ChatMessage>& messages,
                             int max_tokens = 512) = 0;
    virtual ~LLMClient() = default;
};

class AnthropicClient : public LLMClient {
public:
    explicit AnthropicClient(const std::string& api_key);
    ~AnthropicClient();

    std::string chat(const std::string& system_prompt,
                     const std::vector<ChatMessage>& messages,
                     int max_tokens = 512) override;

private:
    std::string api_key_;

    static size_t write_callback(void* contents, size_t size, size_t nmemb,
                                 std::string* out);
};
