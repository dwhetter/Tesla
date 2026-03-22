/* ── State ───────────────────────────────────────────────── */
let currentWord   = null;
let mediaRecorder = null;
let audioChunks   = [];
let isRecording   = false;
// vocabBank[level] = [{ word, translation, pronunciation, example, example_translation, category, score|null }, ...]
const vocabBank  = {};
const vocabIndex = {};

/* ── DOM refs ────────────────────────────────────────────── */
const nameInput       = document.getElementById("name-input");
const languageEl      = document.getElementById("language");
const levelEl         = document.getElementById("level");
const wordLoading     = document.getElementById("word-loading");
const wordContent     = document.getElementById("word-content");
const wordText        = document.getElementById("word-text");
const wordCategory    = document.getElementById("word-category");
const revealBtn       = document.getElementById("reveal-btn");
const wordTranslation = document.getElementById("word-translation");
const wordPronunciation = document.getElementById("word-pronunciation");
const wordExample     = document.getElementById("word-example");
const recordBtn       = document.getElementById("record-btn");
const recordStatus    = document.getElementById("record-status");
const resultsSection  = document.getElementById("results");
const scoreNumber     = document.getElementById("score-number");
const scoreBar        = document.getElementById("score-bar");
const accuracyBadge   = document.getElementById("accuracy-badge");
const transcriptionEl = document.getElementById("transcription");
const pronunciationFeedbackEl = document.getElementById("pronunciation-feedback");
const usageTipEl      = document.getElementById("usage-tip");
const encouragementEl = document.getElementById("encouragement");
const nextBtn         = document.getElementById("next-btn");
const refreshBtn      = document.getElementById("refresh-btn");
const errorBanner     = document.getElementById("error-banner");
const bankSection     = document.getElementById("bank-section");
const bankList        = document.getElementById("bank-list");
const bankLabel       = document.getElementById("bank-label");

/* ── Load vocab for current level ───────────────────────── */
async function loadLevel() {
  hideError();
  showLoading(true);
  resultsSection.classList.add("hidden");
  recordBtn.disabled = true;

  const language = languageEl.value;
  const level    = levelEl.value;

  if (vocabBank[level]?.length) {
    showWord(level);
    renderBank();
    return;
  }

  try {
    const name = nameInput.value.trim();
    const nameParam = name ? `&name=${encodeURIComponent(name)}` : "";
    const resp = await fetch(
      `/api/vocab/batch?language=${encodeURIComponent(language)}&level=${level}${nameParam}`
    );
    const data = await resp.json();
    if (data.error) throw new Error(data.error);
    if (!Array.isArray(data) || data.length === 0) throw new Error("No words returned");

    vocabBank[level]  = data.map(w => ({ ...w, score: null }));
    vocabIndex[level] = 0;

    renderBank();
    showWord(level);
  } catch (err) {
    showLoading(false);
    showError(`Failed to load vocabulary: ${err.message}`);
  }
}

/* ── Display current word ───────────────────────────────── */
function showWord(level) {
  const idx   = vocabIndex[level] ?? 0;
  const entry = vocabBank[level]?.[idx];
  if (!entry) return;

  currentWord = { ...entry, language: languageEl.value, _bankIndex: idx };

  wordText.textContent         = entry.word;
  wordCategory.textContent     = entry.category || "";
  wordTranslation.textContent  = entry.translation;
  wordPronunciation.textContent = entry.pronunciation
    ? `/${entry.pronunciation}/`
    : "";
  wordPronunciation.classList.toggle("hidden", !entry.pronunciation);
  wordExample.textContent = entry.example
    ? `"${entry.example}" — ${entry.example_translation || ""}`
    : "";
  // Reset example to hidden; show reveal button only if there's an example
  wordExample.classList.add("hidden");
  revealBtn.classList.toggle("hidden", !entry.example);

  showLoading(false);
  recordBtn.disabled = false;
  scoreBar.style.width = "0%";
}

/* ── Reveal toggle (example sentence) ──────────────────── */
revealBtn.addEventListener("click", () => {
  wordExample.classList.remove("hidden");
  revealBtn.classList.add("hidden");
});

/* ── Next word ──────────────────────────────────────────── */
nextBtn.addEventListener("click", () => {
  const level   = levelEl.value;
  const words   = vocabBank[level];
  if (!words) return;
  const next = ((vocabIndex[level] ?? 0) + 1) % words.length;
  vocabIndex[level] = next;
  resultsSection.classList.add("hidden");
  renderBank();
  showWord(level);
});

/* ── Recording ──────────────────────────────────────────── */
recordBtn.addEventListener("click", () => {
  isRecording ? stopRecording() : startRecording();
});

async function startRecording() {
  hideError();
  try {
    const stream  = await navigator.mediaDevices.getUserMedia({ audio: true });
    audioChunks   = [];
    mediaRecorder = new MediaRecorder(stream);
    mediaRecorder.ondataavailable = e => { if (e.data.size > 0) audioChunks.push(e.data); };
    mediaRecorder.onstop = () => { stream.getTracks().forEach(t => t.stop()); submitAudio(); };
    mediaRecorder.start();
    isRecording = true;
    recordBtn.classList.add("recording");
    recordBtn.querySelector(".btn-icon").textContent  = "⏹";
    recordBtn.querySelector(".btn-label").textContent = "Stop";
    recordStatus.textContent = "Recording… press stop when done";
  } catch {
    showError("Microphone access denied.");
  }
}

function stopRecording() {
  if (mediaRecorder && mediaRecorder.state !== "inactive") mediaRecorder.stop();
  isRecording = false;
  recordBtn.classList.remove("recording");
  recordBtn.querySelector(".btn-icon").textContent  = "🎤";
  recordBtn.querySelector(".btn-label").textContent = "Record";
  recordStatus.textContent = "Processing…";
  recordBtn.disabled = true;
}

/* ── Submit audio ───────────────────────────────────────── */
async function submitAudio() {
  if (!currentWord) return;
  const audioBlob = new Blob(audioChunks, { type: audioChunks[0]?.type || "audio/webm" });
  const formData  = new FormData();
  formData.append("audio",       audioBlob, "recording.webm");
  formData.append("word",        currentWord.word);
  formData.append("translation", currentWord.translation);
  formData.append("language",    currentWord.language);
  formData.append("name",        nameInput.value.trim());

  try {
    const resp = await fetch("/api/vocab/evaluate", { method: "POST", body: formData });
    const data = await resp.json();
    if (!resp.ok || data.error) throw new Error(data.error || "Evaluation failed");
    showResults(data);
    recordStatus.textContent = "";
  } catch (err) {
    showError(`Evaluation error: ${err.message}`);
    recordStatus.textContent = "";
  } finally {
    recordBtn.disabled = false;
  }
}

/* ── Display results ────────────────────────────────────── */
function showResults(data) {
  const score    = data.score ?? 0;
  const accuracy = (data.accuracy ?? "").toLowerCase();

  scoreNumber.textContent   = score;
  scoreBar.style.background = score >= 8 ? "#22c55e" : score >= 6 ? "#f59e0b" : "#e84040";
  setTimeout(() => { scoreBar.style.width = (score * 10) + "%"; }, 50);

  accuracyBadge.textContent = data.accuracy || "";
  accuracyBadge.className   = "badge " + accuracy;
  transcriptionEl.textContent = `"${data.transcription}"`;

  pronunciationFeedbackEl.textContent = data.pronunciation_feedback || "";
  pronunciationFeedbackEl.classList.toggle("hidden", !data.pronunciation_feedback);
  usageTipEl.textContent = data.usage_tip || "";
  usageTipEl.classList.toggle("hidden", !data.usage_tip);
  encouragementEl.textContent = data.encouragement || "";

  const level = levelEl.value;
  if (vocabBank[level]?.[currentWord._bankIndex] !== undefined)
    vocabBank[level][currentWord._bankIndex].score = score;
  renderBank();

  resultsSection.classList.remove("hidden");
  resultsSection.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

/* ── Word bank ──────────────────────────────────────────── */
function renderBank() {
  const level   = levelEl.value;
  const entries = vocabBank[level] || [];
  const active  = vocabIndex[level] ?? 0;

  bankLabel.textContent = level;
  bankList.innerHTML    = "";

  if (entries.length === 0) { bankSection.classList.add("hidden"); return; }
  bankSection.classList.remove("hidden");

  entries.forEach(({ word, translation, score }, i) => {
    const tier  = score === null ? "none" : score >= 8 ? "high" : score >= 5 ? "mid" : "low";
    const label = score === null ? "–" : `${score}/10`;
    const li    = document.createElement("li");
    li.className = "vocab-bank-item" + (i === active ? " active" : "");
    li.innerHTML = `
      <div class="vb-text">
        <div class="vb-word">${word}</div>
        <div class="vb-translation">${translation}</div>
      </div>
      <span class="lp-score ${tier}">${label}</span>`;
    li.addEventListener("click", () => {
      vocabIndex[level] = i;
      resultsSection.classList.add("hidden");
      renderBank();
      showWord(level);
      window.scrollTo({ top: 0, behavior: "smooth" });
    });
    bankList.appendChild(li);
  });
}

/* ── Refresh ─────────────────────────────────────────────── */
refreshBtn.addEventListener("click", async () => {
  const language = languageEl.value;
  const level    = levelEl.value;
  const name     = nameInput.value.trim();
  refreshBtn.disabled = true;
  refreshBtn.textContent = "Regenerating…";

  try {
    const resp = await fetch("/api/vocab/refresh", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ language, level: parseInt(level), name }),
    });
    const data = await resp.json();
    if (data.error) throw new Error(data.error);
    vocabBank[level]  = data.map(w => ({ ...w, score: null }));
    vocabIndex[level] = 0;
    resultsSection.classList.add("hidden");
    renderBank();
    showWord(level);
  } catch (err) {
    showError(`Refresh failed: ${err.message}`);
  } finally {
    refreshBtn.disabled = false;
    refreshBtn.textContent = "↺ New Words";
  }
});

/* ── Controls ────────────────────────────────────────────── */
languageEl.addEventListener("change", () => {
  Object.keys(vocabBank).forEach(k => { delete vocabBank[k]; delete vocabIndex[k]; });
  loadLevel();
});
levelEl.addEventListener("change", () => { renderBank(); loadLevel(); });

/* ── Helpers ─────────────────────────────────────────────── */
function showLoading(on) {
  wordLoading.classList.toggle("hidden", !on);
  wordContent.classList.toggle("hidden", on);
}
function showError(msg) {
  errorBanner.textContent = msg;
  errorBanner.classList.remove("hidden");
}
function hideError() { errorBanner.classList.add("hidden"); }

/* ── Name persistence ────────────────────────────────────── */
nameInput.value = localStorage.getItem("tutor_name") || "";
nameInput.addEventListener("change", () => {
  localStorage.setItem("tutor_name", nameInput.value.trim());
});

/* ── Init ────────────────────────────────────────────────── */
loadLevel();
