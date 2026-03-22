#include "anthropic_client.hpp"
#include <curl/curl.h>
#include <nlohmann/json.hpp>
#include <stdexcept>

AnthropicClient::AnthropicClient(const std::string& api_key)
    : api_key_(api_key)
{
    curl_global_init(CURL_GLOBAL_DEFAULT);
}

AnthropicClient::~AnthropicClient() {
    curl_global_cleanup();
}

size_t AnthropicClient::write_callback(void* contents, size_t size,
                                       size_t nmemb, std::string* out) {
    size_t total = size * nmemb;
    out->append(static_cast<char*>(contents), total);
    return total;
}

std::string AnthropicClient::chat(const std::string& system_prompt,
                                   const std::vector<ChatMessage>& messages,
                                   int max_tokens) {
    CURL* curl = curl_easy_init();
    if (!curl)
        throw std::runtime_error("Failed to initialize libcurl");

    // Build request body
    nlohmann::json body;
    body["model"]      = "claude-opus-4-6";
    body["max_tokens"] = max_tokens;

    if (!system_prompt.empty())
        body["system"] = system_prompt;

    nlohmann::json msgs = nlohmann::json::array();
    for (const auto& m : messages)
        msgs.push_back({{"role", m.role}, {"content", m.content}});
    body["messages"] = msgs;

    std::string body_str    = body.dump();
    std::string response_body;

    // Headers
    struct curl_slist* headers = nullptr;
    headers = curl_slist_append(headers, "Content-Type: application/json");
    std::string auth = "x-api-key: " + api_key_;
    headers = curl_slist_append(headers, auth.c_str());
    headers = curl_slist_append(headers, "anthropic-version: 2023-06-01");

    curl_easy_setopt(curl, CURLOPT_URL,           "https://api.anthropic.com/v1/messages");
    curl_easy_setopt(curl, CURLOPT_HTTPHEADER,    headers);
    curl_easy_setopt(curl, CURLOPT_POSTFIELDS,    body_str.c_str());
    curl_easy_setopt(curl, CURLOPT_POSTFIELDSIZE, static_cast<long>(body_str.size()));
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, write_callback);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA,     &response_body);
    curl_easy_setopt(curl, CURLOPT_TIMEOUT,       60L);

    CURLcode res = curl_easy_perform(curl);
    curl_slist_free_all(headers);
    curl_easy_cleanup(curl);

    if (res != CURLE_OK)
        throw std::runtime_error(std::string("CURL error: ") + curl_easy_strerror(res));

    // Parse response
    try {
        auto j = nlohmann::json::parse(response_body);
        if (j.contains("error"))
            throw std::runtime_error("Anthropic API error: " +
                j["error"]["message"].get<std::string>());
        return j["content"][0]["text"].get<std::string>();
    } catch (const nlohmann::json::exception& e) {
        throw std::runtime_error(std::string("JSON parse error: ") + e.what() +
                                 "\nRaw response: " + response_body);
    }
}
