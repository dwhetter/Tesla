#include "speech_to_text.hpp"
#include <cstdlib>
#include <ctime>
#include <fstream>
#include <sstream>
#include <stdexcept>
#include <filesystem>
#include <algorithm>
#include <regex>

SpeechToText::SpeechToText(const std::string& whisper_binary,
                             const std::string& model_path)
    : binary_(whisper_binary), model_(model_path) {}

// ---------------------------------------------------------------------------
// Clean up whisper output:
//   - Strip leading/trailing whitespace
//   - Remove [BLANK_AUDIO], [Music], [Applause], and similar markers
// ---------------------------------------------------------------------------
static std::string clean_transcript(const std::string& raw) {
    // Remove bracketed non-speech annotations
    std::string text = std::regex_replace(raw, std::regex("\\[[A-Z_a-z ]+\\]"), "");
    // Trim whitespace
    size_t start = text.find_first_not_of(" \t\n\r");
    size_t end   = text.find_last_not_of(" \t\n\r");
    if (start == std::string::npos) return "";
    return text.substr(start, end - start + 1);
}

std::string SpeechToText::transcribe(const std::string& audio_file,
                                      const std::string& language) {
    // Unique temp output path (avoid collisions in parallel runs)
    std::string out_base = "/tmp/lt_whisper_" + std::to_string(std::time(nullptr));
    std::string out_txt  = out_base + ".txt";

    // whisper-cpp writes plain text to <out_base>.txt when -otxt is given.
    // Diagnostic output is sent to stderr and suppressed with 2>/dev/null.
    std::string cmd = "\"" + binary_ + "\""
        + " -m \""  + model_   + "\""
        + " -l "    + language
        + " --no-timestamps"
        + " -otxt"
        + " -of \"" + out_base + "\""
        + " -f \""  + audio_file + "\""
        + " 2>/dev/null";

    int rc = system(cmd.c_str());

    // Clean up the audio file
    std::filesystem::remove(audio_file);

    if (rc != 0) {
        std::filesystem::remove(out_txt);
        throw std::runtime_error(
            "whisper-cpp failed (exit " + std::to_string(rc) + ").\n"
            "Command: " + cmd + "\n"
            "Check that WHISPER_BIN points to the whisper-cpp binary and\n"
            "WHISPER_MODEL points to a valid ggml model file.");
    }

    std::ifstream file(out_txt);
    if (!file.is_open()) {
        throw std::runtime_error("whisper-cpp produced no output file: " + out_txt);
    }

    std::ostringstream ss;
    ss << file.rdbuf();
    file.close();
    std::filesystem::remove(out_txt);

    return clean_transcript(ss.str());
}
