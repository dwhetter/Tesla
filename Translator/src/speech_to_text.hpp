#pragma once
#include <string>

class SpeechToText {
public:
    SpeechToText(const std::string& whisper_binary,
                 const std::string& model_path);

    // Transcribe a WAV file to text.
    // language: ISO 639-1 code or "auto" for auto-detect.
    // Returns the transcribed text, or empty string if nothing detected.
    std::string transcribe(const std::string& audio_file,
                           const std::string& language = "auto");

private:
    std::string binary_;
    std::string model_;
};
