#include "language_tutor.hpp"
#include <nlohmann/json.hpp>
#include <iostream>
#include <iomanip>
#include <memory>
#include <sstream>
#include <stdexcept>

using json = nlohmann::json;

// ---------------------------------------------------------------------------
// ANSI colour helpers
// ---------------------------------------------------------------------------
namespace Color {
    const std::string RESET   = "\033[0m";
    const std::string BOLD    = "\033[1m";
    const std::string RED     = "\033[31m";
    const std::string GREEN   = "\033[32m";
    const std::string YELLOW  = "\033[33m";
    const std::string BLUE    = "\033[34m";
    const std::string MAGENTA = "\033[35m";
    const std::string CYAN    = "\033[36m";
    const std::string WHITE   = "\033[37m";
}

// ---------------------------------------------------------------------------
// Constructor
// ---------------------------------------------------------------------------
LanguageTutor::LanguageTutor(const Config& config, std::unique_ptr<LLMClient> llm)
    : config_(config)
    , llm_(std::move(llm))
    , recorder_()
    , stt_(config.whisper_binary, config.whisper_model)
{}

// ---------------------------------------------------------------------------
// Extract the first JSON object from a string (Claude sometimes wraps in
// markdown code fences)
// ---------------------------------------------------------------------------
static std::string extract_json(const std::string& text) {
    size_t start = text.find('{');
    size_t end   = text.rfind('}');
    if (start == std::string::npos || end == std::string::npos || end < start)
        throw std::runtime_error("No JSON object found in response:\n" + text);
    return text.substr(start, end - start + 1);
}

// ---------------------------------------------------------------------------
// Generate a practice dialog via Claude
// ---------------------------------------------------------------------------
Dialog LanguageTutor::generate_dialog(int lesson_num) {
    static const char* levels[] = {
        "",                // unused (1-indexed)
        "complete beginner — basic greetings and very short phrases",
        "elementary — simple everyday sentences",
        "intermediate — varied topics with some complex structures",
        "upper-intermediate — idiomatic expressions and nuanced language",
        "advanced — complex discussions and formal registers",
    };

    std::string system =
        "You are a language learning curriculum designer.";

    std::ostringstream prompt;
    prompt << "Create lesson " << lesson_num << " for a "
           << levels[config_.difficulty_level] << " "
           << config_.target_language << " learner.\n\n"
           << "Generate ONE practical phrase or short sentence that:\n"
           << "- Is natural and commonly used\n"
           << "- Fits the difficulty level\n"
           << "- Teaches useful vocabulary or grammar\n\n"
           << "Respond with ONLY valid JSON (no markdown, no extra text):\n"
           << "{\n"
           << "  \"phrase\": \"[phrase in " << config_.target_language << "]\",\n"
           << "  \"translation\": \"[English translation]\",\n"
           << "  \"context\": \"[one sentence: when/where you'd say this]\",\n"
           << "  \"tips\": \"[optional pronunciation or grammar note, or empty string]\"\n"
           << "}";

    std::string response = llm_->chat(system, {{"user", prompt.str()}});

    try {
        auto j = json::parse(extract_json(response));
        return Dialog{
            j["phrase"].get<std::string>(),
            j["translation"].get<std::string>(),
            j["context"].get<std::string>(),
            j.value("tips", "")
        };
    } catch (const json::exception& e) {
        throw std::runtime_error(
            std::string("Failed to parse dialog JSON: ") + e.what() +
            "\nResponse: " + response);
    }
}

// ---------------------------------------------------------------------------
// Evaluate the student's spoken attempt via Claude
// ---------------------------------------------------------------------------
Evaluation LanguageTutor::evaluate_response(const Dialog& dialog,
                                             const std::string& student_response) {
    std::string system =
        "You are a " + config_.target_language + " language tutor. "
        "Evaluate spoken practice. Speech-to-text transcription may have "
        "minor errors — be fair and generous when scoring.";

    std::ostringstream prompt;
    prompt << "Target phrase: \"" << dialog.phrase << "\"\n"
           << "English:       \"" << dialog.translation << "\"\n"
           << "Student said:  \"" << student_response << "\"\n\n"
           << "Rate the student's attempt. Consider STT transcription noise.\n\n"
           << "Respond with ONLY valid JSON (no markdown, no extra text):\n"
           << "{\n"
           << "  \"score\": <integer 1-10>,\n"
           << "  \"accuracy\": \"<Perfect|Good|Fair|Poor>\",\n"
           << "  \"went_well\": \"<what the student got right>\",\n"
           << "  \"improvements\": \"<specific suggestions, or 'None needed'>\",\n"
           << "  \"encouragement\": \"<short motivational message>\"\n"
           << "}";

    std::string response = llm_->chat(system, {{"user", prompt.str()}});

    try {
        auto j = json::parse(extract_json(response));
        return Evaluation{
            j["score"].get<int>(),
            j["accuracy"].get<std::string>(),
            j["went_well"].get<std::string>(),
            j["improvements"].get<std::string>(),
            j["encouragement"].get<std::string>()
        };
    } catch (const json::exception& e) {
        throw std::runtime_error(
            std::string("Failed to parse evaluation JSON: ") + e.what() +
            "\nResponse: " + response);
    }
}

// ---------------------------------------------------------------------------
// Display helpers
// ---------------------------------------------------------------------------
void LanguageTutor::display_dialog(const Dialog& dialog) const {
    const std::string bar(52, '-');
    std::cout << "\n" << Color::CYAN << Color::BOLD << bar << Color::RESET << "\n";
    std::cout << Color::BOLD << "  Practice phrase:\n\n" << Color::RESET;
    std::cout << "  " << Color::YELLOW << Color::BOLD
              << "\"" << dialog.phrase << "\"" << Color::RESET << "\n\n";
    std::cout << "  " << Color::BLUE << dialog.translation << Color::RESET << "\n\n";
    std::cout << "  " << Color::MAGENTA << "Context: " << Color::RESET
              << dialog.context << "\n";
    if (!dialog.tips.empty())
        std::cout << "  " << Color::MAGENTA << "Tip: " << Color::RESET
                  << dialog.tips << "\n";
    std::cout << Color::CYAN << Color::BOLD << bar << Color::RESET << "\n";
}

void LanguageTutor::display_evaluation(const Evaluation& eval) const {
    std::cout << "\n";

    std::string score_color =
        (eval.score >= 9) ? Color::GREEN  :
        (eval.score >= 7) ? Color::YELLOW :
        (eval.score >= 5) ? Color::YELLOW : Color::RED;

    std::string stars =
        (eval.score >= 9) ? "★★★" :
        (eval.score >= 7) ? "★★☆" :
        (eval.score >= 5) ? "★☆☆" : "☆☆☆";

    std::cout << Color::BOLD << "  Score:    "
              << score_color << eval.score << "/10  " << stars
              << Color::RESET << "\n";
    std::cout << "  Accuracy: " << score_color << eval.accuracy
              << Color::RESET << "\n\n";

    std::cout << "  " << Color::GREEN << "✓ " << Color::RESET
              << eval.went_well << "\n";

    if (eval.improvements != "None needed")
        std::cout << "  " << Color::YELLOW << "→ " << Color::RESET
                  << eval.improvements << "\n";

    std::cout << "\n  " << Color::CYAN << eval.encouragement
              << Color::RESET << "\n";
}

// ---------------------------------------------------------------------------
// Record mic + transcribe
// ---------------------------------------------------------------------------
std::string LanguageTutor::record_and_transcribe() {
    const std::string audio_file = "/tmp/lt_recording.wav";

    std::cout << "\n  " << Color::RED << Color::BOLD << "● Recording "
              << Color::RESET << "(" << config_.recording_seconds
              << " s)..." << std::flush;

    if (!recorder_.record(audio_file, config_.recording_seconds))
        throw std::runtime_error("Audio recording failed");

    std::cout << " done\n  Transcribing..." << std::flush;

    std::string text = stt_.transcribe(audio_file, "auto");

    std::cout << " done\n\n";
    std::cout << "  " << Color::BOLD << "You said: " << Color::RESET
              << "\"" << text << "\"\n";

    return text;
}

// ---------------------------------------------------------------------------
// Main interactive loop
// ---------------------------------------------------------------------------
void LanguageTutor::run() {
    if (!AudioRecorder::is_available()) {
        std::cerr << Color::RED
                  << "No audio recorder found. Install sox:  brew install sox\n"
                  << Color::RESET;
        return;
    }

    // Banner
    std::cout << "\n"
              << Color::BOLD << Color::BLUE
              << "  ╔══════════════════════════════════════╗\n"
              << "  ║          LANGUAGE TUTOR              ║\n"
              << "  ╚══════════════════════════════════════╝\n"
              << Color::RESET;
    std::cout << "\n"
              << "  Language : " << Color::BOLD << config_.target_language << Color::RESET << "\n"
              << "  Level    : " << Color::BOLD << config_.difficulty_level << "/5" << Color::RESET << "\n"
              << "\n"
              << "  Listen to each phrase, then try to repeat it.\n"
              << "  Press " << Color::BOLD << Color::GREEN << "ENTER" << Color::RESET
              << " to record, type " << Color::BOLD << "'q'" << Color::RESET
              << " + ENTER to quit.\n";

    int lesson     = 1;
    int total      = 0;
    int completed  = 0;

    while (true) {
        std::cout << "\n\n  " << Color::BOLD << "Lesson " << lesson
                  << Color::RESET << "  — Generating phrase...\n";

        // Generate
        Dialog dialog;
        try {
            dialog = generate_dialog(lesson);
        } catch (const std::exception& e) {
            std::cerr << Color::RED << "  Error: " << e.what() << Color::RESET << "\n";
            std::cout << "  Retry? (ENTER / q): ";
            std::string in; std::getline(std::cin, in);
            if (in == "q" || in == "Q") break;
            continue;
        }

        display_dialog(dialog);

        // Offer to hear pronunciation
        std::cout << "\n  Hear pronunciation? (y/ENTER to skip): ";
        std::string hear; std::getline(std::cin, hear);
        if (hear == "y" || hear == "Y")
            AudioRecorder::speak(dialog.phrase, config_.target_language);

        // Prompt to record
        std::cout << "\n  Press " << Color::BOLD << Color::GREEN << "ENTER"
                  << Color::RESET << " to record your attempt (or 'q' to quit): ";
        std::string go; std::getline(std::cin, go);
        if (go == "q" || go == "Q") break;

        // Record + transcribe
        std::string transcript;
        try {
            transcript = record_and_transcribe();
        } catch (const std::exception& e) {
            std::cerr << Color::RED << "  Error: " << e.what() << Color::RESET << "\n";
            continue;
        }

        if (transcript.empty()) {
            std::cout << "\n  " << Color::YELLOW
                      << "No speech detected — make sure your microphone is working."
                      << Color::RESET << "\n";
            continue;
        }

        // Evaluate
        std::cout << "  Evaluating..." << std::flush;
        Evaluation eval;
        try {
            eval = evaluate_response(dialog, transcript);
        } catch (const std::exception& e) {
            std::cerr << "\n" << Color::RED << "  Error: " << e.what() << Color::RESET << "\n";
            continue;
        }
        std::cout << " done\n";

        display_evaluation(eval);

        total    += eval.score;
        completed++;

        // Next / quit
        std::cout << "\n  Press ENTER for the next lesson, or 'q' to quit: ";
        std::string next; std::getline(std::cin, next);
        if (next == "q" || next == "Q") break;

        lesson++;
    }

    // Session summary
    if (completed > 0) {
        double avg = static_cast<double>(total) / completed;
        std::cout << "\n\n  " << Color::BOLD << Color::BLUE
                  << "Session Summary" << Color::RESET << "\n"
                  << "  Phrases practised : " << Color::BOLD << completed << Color::RESET << "\n"
                  << "  Average score     : " << Color::BOLD
                  << std::fixed << std::setprecision(1) << avg << "/10"
                  << Color::RESET << "\n";
    }

    std::cout << "\n  " << Color::CYAN
              << "Great practice! See you next time." << Color::RESET << "\n\n";
}
