cmake_minimum_required(VERSION 3.16)
project(LanguageTutor VERSION 1.0)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED True)

# Find libcurl (pre-installed on macOS)
find_package(CURL REQUIRED)

# Fetch nlohmann/json (header-only, no system install needed)
include(FetchContent)
FetchContent_Declare(
    nlohmann_json
    GIT_REPOSITORY https://github.com/nlohmann/json.git
    GIT_TAG        v3.11.3
    GIT_SHALLOW    TRUE
)
set(JSON_Install OFF CACHE INTERNAL "")
set(JSON_BuildTests OFF CACHE INTERNAL "")
FetchContent_MakeAvailable(nlohmann_json)

add_executable(language_tutor
    src/main.cpp
    src/anthropic_client.cpp
    src/ollama_client.cpp
    src/audio_recorder.cpp
    src/speech_to_text.cpp
    src/language_tutor.cpp
)

target_include_directories(language_tutor PRIVATE src)

target_link_libraries(language_tutor PRIVATE
    CURL::libcurl
    nlohmann_json::nlohmann_json
)
