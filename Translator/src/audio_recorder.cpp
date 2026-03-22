#include "audio_recorder.hpp"
#include <cstdlib>
#include <stdexcept>
#include <string>

// ---------------------------------------------------------------------------
// Internal helper: check if a command is on PATH
// ---------------------------------------------------------------------------
static bool command_exists(const std::string& cmd) {
    return system(("which " + cmd + " > /dev/null 2>&1").c_str()) == 0;
}

// ---------------------------------------------------------------------------
// AudioRecorder::is_available
// ---------------------------------------------------------------------------
bool AudioRecorder::is_available() {
    return command_exists("rec") || command_exists("sox") ||
           command_exists("ffmpeg");
}

// ---------------------------------------------------------------------------
// AudioRecorder::record
//
// Records RECORDING_SECONDS of audio to output_file as 16 kHz / mono / 16-bit
// signed PCM WAV — the format whisper.cpp expects.
//
// Tool priority: rec (from sox) → sox -d → ffmpeg avfoundation
// ---------------------------------------------------------------------------
bool AudioRecorder::record(const std::string& output_file, int duration_seconds) {
    std::string cmd;

    if (command_exists("rec")) {
        // 'rec' is the sox recording front-end; most portable
        cmd = "rec -q -r 16000 -c 1 -b 16 -e signed-integer \""
            + output_file + "\" trim 0 "
            + std::to_string(duration_seconds)
            + " 2>/dev/null";
    } else if (command_exists("sox")) {
        // sox with '-d' selects the default input device
        cmd = "sox -q -d -r 16000 -c 1 -b 16 -e signed-integer \""
            + output_file + "\" trim 0 "
            + std::to_string(duration_seconds)
            + " 2>/dev/null";
    } else if (command_exists("ffmpeg")) {
        // ffmpeg via AVFoundation (macOS built-in audio subsystem)
        cmd = "ffmpeg -loglevel quiet -f avfoundation -i \":0\" -t "
            + std::to_string(duration_seconds)
            + " -ar 16000 -ac 1 -acodec pcm_s16le \""
            + output_file + "\" -y 2>/dev/null";
    } else {
        throw std::runtime_error(
            "No audio recorder found.\n"
            "Install one with:  brew install sox");
    }

    return system(cmd.c_str()) == 0;
}

// ---------------------------------------------------------------------------
// AudioRecorder::speak
//
// Uses macOS 'say' to pronounce the phrase so the learner can hear it.
// Chooses a voice appropriate for the target language where possible.
// ---------------------------------------------------------------------------
void AudioRecorder::speak(const std::string& text, const std::string& language) {
    if (!command_exists("say")) return;  // non-macOS: silently skip

    // Map common language names to macOS TTS voices
    std::string voice;
    if      (language == "Spanish")    voice = "Paulina";
    else if (language == "French")     voice = "Thomas";
    else if (language == "German")     voice = "Anna";
    else if (language == "Italian")    voice = "Alice";
    else if (language == "Portuguese") voice = "Luciana";
    else if (language == "Japanese")   voice = "Kyoko";
    else if (language == "Mandarin" || language == "Chinese") voice = "Tingting";
    else if (language == "Korean")     voice = "Yuna";
    // Default: system voice

    std::string cmd;
    if (!voice.empty())
        cmd = "say -v \"" + voice + "\" \"" + text + "\"";
    else
        cmd = "say \"" + text + "\"";

    system(cmd.c_str());
}
