#pragma once
#include <string>

class AudioRecorder {
public:
    // Record microphone input to output_file (WAV, 16 kHz mono 16-bit).
    // duration_seconds: how long to record.
    // Returns true on success.
    bool record(const std::string& output_file, int duration_seconds);

    // Pronounce text using macOS text-to-speech (silent no-op on other platforms).
    static void speak(const std::string& text, const std::string& language);

    // Returns true if a suitable recording tool is available.
    static bool is_available();
};
