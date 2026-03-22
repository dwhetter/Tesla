#include "ollama_client.hpp"
#include <curl/curl.h>
#include <nlohmann/json.hpp>
#include <stdexcept>

OllamaClient::OllamaClient(const std::string& base_url, const std::string& model)
    : base_url_(base_url), model_(model) {}

size_t OllamaClient::write_callback(void* contents, size_t size,
                                     size_t nmemb, std::string* out) {
    size_t total = size * nmemb;
    out->append(static_cast<char*>(contents), total);
    return total;
}

std::string OllamaClient::chat(const std::string& system_prompt,
                                 const std::vector<ChatMessage>& messages,
                                 int /*max_tokens*/) {
    CURL* curl = curl_easy_init();
    if (!curl)
        throw std::runtime_error("Failed to initialize libcurl");

    // Ollama /api/chat format
    nlohmann::json body;
    body["model"]  = model_;
    body["stream"] = false;

    nlohmann::json msgs = nlohmann::json::array();
    if (!system_prompt.empty())
        msgs.push_back({{"role", "system"}, {"content", system_prompt}});
    for (const auto& m : messages)
        msgs.push_back({{"role", m.role}, {"content", m.content}});
    body["messages"] = msgs;

    std::string body_str    = body.dump();
    std::string response_body;

    std::string url = base_url_ + "/api/chat";

    struct curl_slist* headers = nullptr;
    headers = curl_slist_append(headers, "Content-Type: application/json");

    curl_easy_setopt(curl, CURLOPT_URL,           url.c_str());
    curl_easy_setopt(curl, CURLOPT_HTTPHEADER,    headers);
    curl_easy_setopt(curl, CURLOPT_POSTFIELDS,    body_str.c_str());
    curl_easy_setopt(curl, CURLOPT_POSTFIELDSIZE, static_cast<long>(body_str.size()));
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, write_callback);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA,     &response_body);
    curl_easy_setopt(curl, CURLOPT_TIMEOUT,       120L);  // local models can be slow

    CURLcode res = curl_easy_perform(curl);
    curl_slist_free_all(headers);
    curl_easy_cleanup(curl);

    if (res != CURLE_OK) {
        throw std::runtime_error(
            std::string("Ollama connection failed: ") + curl_easy_strerror(res) +
            "\nMake sure Ollama is running:  ollama serve");
    }

    try {
        auto j = nlohmann::json::parse(response_body);
        if (j.contains("error"))
            throw std::runtime_error("Ollama error: " +
                j["error"].get<std::string>());
        return j["message"]["content"].get<std::string>();
    } catch (const nlohmann::json::exception& e) {
        throw std::runtime_error(
            std::string("Ollama JSON parse error: ") + e.what() +
            "\nRaw response: " + response_body);
    }
}
