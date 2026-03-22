#pragma once
#include "config.hpp"
#include "anthropic_client.hpp"   // LLMClient + ChatMessage
#include "audio_recorder.hpp"
#include "speech_to_text.hpp"
#include <memory>
#include <string>

// A practice phrase returned by the LLM
struct Dialog {
    std::string phrase;       // in target language
    std::string translation;  // English
    std::string context;      // brief situational description
    std::string tips;         // optional pronunciation / grammar note
};

// The LLM's assessment of the student's attempt
struct Evaluation {
    int         score;         // 1–10
    std::string accuracy;      // "Perfect" | "Good" | "Fair" | "Poor"
    std::string went_well;
    std::string improvements;
    std::string encouragement;
};

class LanguageTutor {
public:
    // Takes ownership of the LLM client pointer.
    LanguageTutor(const Config& config, std::unique_ptr<LLMClient> llm);

    void run();

private:
    Dialog     generate_dialog(int lesson_num);
    Evaluation evaluate_response(const Dialog& dialog,
                                  const std::string& student_response);

    void display_dialog(const Dialog& dialog) const;
    void display_evaluation(const Evaluation& eval) const;
    std::string record_and_transcribe();

    Config                   config_;
    std::unique_ptr<LLMClient> llm_;
    AudioRecorder            recorder_;
    SpeechToText             stt_;
};
