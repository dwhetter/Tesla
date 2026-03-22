/* ── State ──────────────────────────────────────────────────── */
let currentPhrase  = null;
let mediaRecorder  = null;
let audioChunks    = [];
let isRecording    = false;
// levelPhrases[level] = [{ phrase, translation, context, tips, score|null }, ...]
const levelPhrases = {};
// current index within levelPhrases[level]
const levelIndex   = {};

/* ── DOM refs ───────────────────────────────────────────────── */
const nameInput       = document.getElementById("name-input");
const languageEl      = document.getElementById("language");
const levelEl         = document.getElementById("level");
const phraseLoading   = document.getElementById("phrase-loading");
const phraseContent   = document.getElementById("phrase-content");
const phraseText      = document.getElementById("phrase-text");
const translationText = document.getElementById("translation-text");
const contextText     = document.getElementById("context-text");
const tipsText        = document.getElementById("tips-text");
const recordBtn       = document.getElementById("record-btn");
const recordStatus    = document.getElementById("record-status");
const resultsSection  = document.getElementById("results");
const scoreNumber     = document.getElementById("score-number");
const scoreBar        = document.getElementById("score-bar");
const accuracyBadge   = document.getElementById("accuracy-badge");
const transcriptionEl = document.getElementById("transcription");
const wentWellEl      = document.getElementById("went-well").querySelector("span:not(.icon)");
const improvementsEl  = document.getElementById("improvements").querySelector("span:not(.icon)");
const encouragementEl = document.getElementById("encouragement");
const nextBtn         = document.getElementById("next-btn");
const listenBtn       = document.getElementById("listen-btn");
const genAllBtn       = document.getElementById("gen-all-btn");
const refreshBtn      = document.getElementById("refresh-btn");
const errorBanner     = document.getElementById("error-banner");
const historySection      = document.getElementById("history-section");
const historyList         = document.getElementById("history-list");
const levelPhrasesSection = document.getElementById("level-phrases-section");
const levelPhrasesList    = document.getElementById("level-phrases-list");
const levelPhrasesLabel   = document.getElementById("level-phrases-label");

const LANG_CODES = {
  Spanish: "es-ES", French: "fr-FR", German: "de-DE",
  Italian: "it-IT", Japanese: "ja-JP", Mandarin: "zh-CN", Portuguese: "pt-BR",
};

/* ── Load batch of 10 phrases for a level ───────────────────── */
async function loadLevel() {
  hideError();
  showLoading(true);
  resultsSection.classList.add("hidden");
  recordBtn.disabled = true;

  const language = languageEl.value;
  const level    = levelEl.value;

  // Use cached phrases if already loaded for this level
  if (levelPhrases[level]?.length) {
    showPhrase(level);
    renderLevelPhrases();
    return;
  }

  try {
    const name = nameInput.value.trim();
    const nameParam = name ? `&name=${encodeURIComponent(name)}` : "";
    const resp = await fetch(
      `/api/phrases/batch?language=${encodeURIComponent(language)}&level=${level}&count=10${nameParam}`
    );
    const data = await resp.json();
    if (data.error) throw new Error(data.error);
    if (!Array.isArray(data) || data.length === 0) throw new Error("No phrases returned");

    levelPhrases[level] = data.map(p => ({ ...p, score: null }));
    levelIndex[level]   = 0;

    renderLevelPhrases();
    showPhrase(level);
  } catch (err) {
    showLoading(false);
    showError(`Failed to load phrases: ${err.message}`);
  }
}

/* ── Display the current phrase for a level ─────────────────── */
function showPhrase(level) {
  const idx    = levelIndex[level] ?? 0;
  const entry  = levelPhrases[level]?.[idx];
  if (!entry) return;

  currentPhrase = { ...entry, language: languageEl.value, _bankIndex: idx };

  phraseText.textContent      = entry.phrase;
  translationText.textContent = entry.translation;
  contextText.textContent     = entry.context || "";
  tipsText.textContent        = entry.tips || "";
  tipsText.classList.toggle("hidden", !entry.tips);

  showLoading(false);
  recordBtn.disabled = false;
  scoreBar.style.width = "0%";
}

/* ── Next phrase (cycle through bank) ───────────────────────── */
nextBtn.addEventListener("click", () => {
  const level   = levelEl.value;
  const phrases = levelPhrases[level];
  if (!phrases) return;

  // Advance to next unscored phrase, or just the next one if all scored
  const current = levelIndex[level] ?? 0;
  const next    = (current + 1) % phrases.length;
  levelIndex[level] = next;

  resultsSection.classList.add("hidden");
  renderLevelPhrases();
  showPhrase(level);
});

/* ── Recording ──────────────────────────────────────────────── */
recordBtn.addEventListener("click", () => {
  isRecording ? stopRecording() : startRecording();
});

async function startRecording() {
  hideError();
  try {
    const stream  = await navigator.mediaDevices.getUserMedia({ audio: true });
    audioChunks   = [];
    mediaRecorder = new MediaRecorder(stream);

    mediaRecorder.ondataavailable = (e) => {
      if (e.data.size > 0) audioChunks.push(e.data);
    };
    mediaRecorder.onstop = () => {
      stream.getTracks().forEach(t => t.stop());
      submitAudio();
    };

    mediaRecorder.start();
    isRecording = true;
    recordBtn.classList.add("recording");
    recordBtn.querySelector(".btn-icon").textContent  = "⏹";
    recordBtn.querySelector(".btn-label").textContent = "Stop";
    recordStatus.textContent = "Recording… press stop when done";
  } catch {
    showError("Microphone access denied. Please allow microphone permissions.");
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

/* ── Submit audio ───────────────────────────────────────────── */
async function submitAudio() {
  if (!currentPhrase) return;

  const audioBlob = new Blob(audioChunks, { type: audioChunks[0]?.type || "audio/webm" });
  const formData  = new FormData();
  formData.append("audio",       audioBlob, "recording.webm");
  formData.append("phrase",      currentPhrase.phrase);
  formData.append("translation", currentPhrase.translation);
  formData.append("language",    currentPhrase.language);
  formData.append("name",        nameInput.value.trim());

  try {
    const resp = await fetch("/api/evaluate", { method: "POST", body: formData });
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

/* ── Display results ────────────────────────────────────────── */
function showResults(data) {
  const score    = data.score ?? 0;
  const accuracy = (data.accuracy ?? "").toLowerCase();

  scoreNumber.textContent   = score;
  scoreBar.style.background = score >= 8 ? "#22c55e" : score >= 6 ? "#f59e0b" : "#e84040";
  setTimeout(() => { scoreBar.style.width = (score * 10) + "%"; }, 50);

  accuracyBadge.textContent = data.accuracy || "";
  accuracyBadge.className   = "badge " + accuracy;
  transcriptionEl.textContent = `"${data.transcription}"`;
  wentWellEl.textContent      = data.went_well     || "";
  improvementsEl.textContent  = data.improvements  || "";
  encouragementEl.textContent = data.encouragement || "";

  document.getElementById("improvements").classList.toggle("hidden",
    !data.improvements || data.improvements.toLowerCase() === "none needed");

  // Persist score into bank
  const level = levelEl.value;
  if (levelPhrases[level]?.[currentPhrase._bankIndex] !== undefined)
    levelPhrases[level][currentPhrase._bankIndex].score = score;
  renderLevelPhrases();

  resultsSection.classList.remove("hidden");
  resultsSection.scrollIntoView({ behavior: "smooth", block: "nearest" });
  addHistoryEntry(currentPhrase.phrase, currentPhrase.translation, score);
}

/* ── Level phrase bank ──────────────────────────────────────── */
function renderLevelPhrases() {
  const level   = levelEl.value;
  const entries = levelPhrases[level] || [];
  const active  = levelIndex[level]  ?? 0;

  levelPhrasesLabel.textContent = level;
  levelPhrasesList.innerHTML    = "";

  if (entries.length === 0) {
    levelPhrasesSection.classList.add("hidden");
    return;
  }

  levelPhrasesSection.classList.remove("hidden");
  entries.forEach(({ phrase, translation, score }, i) => {
    const tier       = score === null ? "none" : score >= 8 ? "high" : score >= 5 ? "mid" : "low";
    const scoreLabel = score === null ? "–" : `${score}/10`;
    const li         = document.createElement("li");
    li.className     = "level-phrase-item" + (i === active ? " active" : "");
    li.innerHTML = `
      <div class="lp-text">
        <div class="lp-phrase">${phrase}</div>
        <div class="lp-translation">${translation}</div>
      </div>
      <span class="lp-score ${tier}">${scoreLabel}</span>`;

    // Click to jump to that phrase
    li.addEventListener("click", () => {
      levelIndex[level] = i;
      resultsSection.classList.add("hidden");
      renderLevelPhrases();
      showPhrase(level);
      window.scrollTo({ top: 0, behavior: "smooth" });
    });

    levelPhrasesList.appendChild(li);
  });
}

/* ── History ────────────────────────────────────────────────── */
function addHistoryEntry(phrase, translation, score) {
  historySection.classList.remove("hidden");
  const tier = score >= 8 ? "high" : score >= 5 ? "mid" : "low";
  const li   = document.createElement("li");
  li.className = "history-item";
  li.innerHTML = `
    <div class="history-score ${tier}">${score}</div>
    <div class="history-text">
      <div class="history-phrase">${phrase}</div>
      <div class="history-translation">${translation}</div>
    </div>`;
  historyList.prepend(li);
}

/* ── Listen ─────────────────────────────────────────────────── */
listenBtn.addEventListener("click", () => {
  if (!currentPhrase) return;
  speechSynthesis.cancel();
  const utterance   = new SpeechSynthesisUtterance(currentPhrase.phrase);
  utterance.lang    = LANG_CODES[currentPhrase.language] ?? "en-US";
  utterance.rate    = 0.85;
  utterance.onstart = () => listenBtn.classList.add("speaking");
  utterance.onend   = () => listenBtn.classList.remove("speaking");
  speechSynthesis.speak(utterance);
});

/* ── Controls ───────────────────────────────────────────────── */
languageEl.addEventListener("change", () => {
  Object.keys(levelPhrases).forEach(k => { delete levelPhrases[k]; delete levelIndex[k]; });
  loadLevel();
});

levelEl.addEventListener("change", () => {
  renderLevelPhrases();
  loadLevel();
});

/* Regenerate current level */
refreshBtn.addEventListener("click", async () => {
  const language = languageEl.value;
  const level    = levelEl.value;
  setHeaderBusy(true, "Regenerating…");

  try {
    const name = nameInput.value.trim();
    const resp = await fetch("/api/phrases/refresh", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ language, level: parseInt(level), name }),
    });
    const data = await resp.json();
    if (data.error) throw new Error(data.error);
    levelPhrases[level] = data.map(p => ({ ...p, score: null }));
    levelIndex[level]   = 0;
    resultsSection.classList.add("hidden");
    renderLevelPhrases();
    showPhrase(level);
  } catch (err) {
    showError(`Refresh failed: ${err.message}`);
  } finally {
    setHeaderBusy(false);
  }
});

/* Generate all 5 levels for current language */
genAllBtn.addEventListener("click", async () => {
  const language = languageEl.value;
  if (!confirm(`Generate phrases for all 5 levels of ${language}? This may take a minute.`)) return;
  setHeaderBusy(true, "Generating all levels…");

  try {
    const name = nameInput.value.trim();
    const resp = await fetch("/api/phrases/generate-all", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ language, name }),
    });
    const data = await resp.json();

    // Load generated phrases into local cache
    Object.entries(data.results ?? data).forEach(([lvl, phrases]) => {
      levelPhrases[lvl] = phrases.map(p => ({ ...p, score: null }));
      levelIndex[lvl]   = 0;
    });

    renderLevelPhrases();
    showPhrase(levelEl.value);
    if (data.errors && Object.keys(data.errors).length)
      showError(`Some levels failed: ${JSON.stringify(data.errors)}`);
  } catch (err) {
    showError(`Generate all failed: ${err.message}`);
  } finally {
    setHeaderBusy(false);
  }
});

function setHeaderBusy(busy, label = "") {
  genAllBtn.disabled = busy;
  refreshBtn.disabled = busy;
  genAllBtn.textContent = busy && label ? label : "⚡ All Levels";
}

/* ── Error helpers ──────────────────────────────────────────── */
function showError(msg) {
  errorBanner.textContent = msg;
  errorBanner.classList.remove("hidden");
}
function hideError() {
  errorBanner.classList.add("hidden");
}

function showLoading(on) {
  phraseLoading.classList.toggle("hidden", !on);
  phraseContent.classList.toggle("hidden", on);
}

/* ── Name persistence ───────────────────────────────────────── */
nameInput.value = localStorage.getItem("tutor_name") || "";
nameInput.addEventListener("change", () => {
  localStorage.setItem("tutor_name", nameInput.value.trim());
});

/* ── Init ───────────────────────────────────────────────────── */
loadLevel();
