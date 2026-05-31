/*
 * JuiceLab Coach for PwnzzAI — injected client sidebar.
 *
 * Loaded by the coach reverse proxy into every HTML page. It:
 *   - detects the current lab from the URL (reframe: lab-agnostic),
 *   - monkey-patches fetch / XHR to capture the student <-> vulnerable-LLM
 *     transcript in the browser (reframe 3),
 *   - offers adaptive hints (reframe 4) and an LLM-as-judge verdict
 *     (reframe 1) by calling the coach backend,
 *   - reports session_start / hint_revealed / challenge_solved /
 *     journal_filled events to the teacher dashboard via the backend.
 *
 * Pure vanilla JS, no framework. PwnzzAI source is never modified.
 */
(function () {
  "use strict";

  if (window.__COACH_LOADED__) return;
  window.__COACH_LOADED__ = true;

  var BASE = window.__COACH_BASE__ || "/__coach";
  var STORE_KEY = "pwnzzai_coach_v1";
  var QUEUE_KEY = "pwnzzai_coach_queue_v1";

  // Request/response field names that typically carry the attack / reply.
  var USER_FIELDS = ["message", "query", "prompt", "input", "question",
    "text", "user_message", "msg", "content", "doc", "document"];
  var BOT_FIELDS = ["response", "answer", "reply", "result", "output",
    "message", "content", "text", "completion", "data"];

  // ---- i18n ---------------------------------------------------------------
  var I18N = {
    fr: {
      title: "Coach JuiceLab",
      no_lab: "Aucun lab detecte sur cette page.",
      goal: "Objectif",
      captured: "Conversation capturee",
      turns: "echange(s)",
      hint: "Indice",
      judge: "Verifier ma reussite",
      journal: "Journal",
      view: "Voir la conversation",
      hide: "Masquer la conversation",
      judging: "Evaluation en cours...",
      hinting: "Generation de l'indice...",
      solved: "Reussi",
      partial: "Partiel",
      notyet: "Pas encore reussi",
      score: "Score",
      hint_level: "Niveau",
      journal_q: "Comment as-tu exploite cette faille ? Explique ta demarche.",
      save: "Enregistrer",
      journal_saved: "Journal enregistre",
      empty: "Discute d'abord avec l'assistant du lab.",
      dashboard_off: "Dashboard prof non configure (mode local).",
      sent: "Envoye au dashboard",
      queued: "Hors-ligne : sera renvoye",
      unavailable: "Service coach indisponible (Ollama ?).",
      you: "Toi",
      bot: "Assistant",
      cohort: "Cohorte",
      reset: "Effacer la conversation"
    },
    en: {
      title: "JuiceLab Coach",
      no_lab: "No lab detected on this page.",
      goal: "Goal",
      captured: "Captured conversation",
      turns: "turn(s)",
      hint: "Hint",
      judge: "Check my success",
      journal: "Journal",
      view: "View conversation",
      hide: "Hide conversation",
      judging: "Grading...",
      hinting: "Generating hint...",
      solved: "Solved",
      partial: "Partial",
      notyet: "Not solved yet",
      score: "Score",
      hint_level: "Level",
      journal_q: "How did you exploit this flaw? Explain your approach.",
      save: "Save",
      journal_saved: "Journal saved",
      empty: "Talk to the lab assistant first.",
      dashboard_off: "Teacher dashboard not configured (local mode).",
      sent: "Sent to dashboard",
      queued: "Offline: will retry",
      unavailable: "Coach service unavailable (Ollama?).",
      you: "You",
      bot: "Assistant",
      cohort: "Cohort",
      reset: "Clear conversation"
    }
  };

  // ---- state --------------------------------------------------------------
  var state = loadState();
  var config = null;
  var currentLab = null;
  var ui = {};

  function loadState() {
    try {
      var raw = localStorage.getItem(STORE_KEY);
      if (raw) return JSON.parse(raw);
    } catch (e) { /* ignore */ }
    return { token: uuid(), lang: "fr", transcripts: {}, hintLevel: {}, solved: {} };
  }
  function saveState() {
    try { localStorage.setItem(STORE_KEY, JSON.stringify(state)); } catch (e) { /* ignore */ }
  }
  function t(key) { return (I18N[state.lang] || I18N.fr)[key] || key; }
  function uuid() {
    if (window.crypto && crypto.randomUUID) return crypto.randomUUID();
    return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, function (c) {
      var r = (Math.random() * 16) | 0, v = c === "x" ? r : (r & 0x3) | 0x8;
      return v.toString(16);
    });
  }

  // ---- transcript capture (fetch + XHR) -----------------------------------
  function transcriptFor(key) {
    if (!state.transcripts[key]) state.transcripts[key] = [];
    return state.transcripts[key];
  }
  function pushTurn(role, content) {
    if (!currentLab || !content) return;
    var tr = transcriptFor(currentLab.key);
    var text = String(content).trim();
    if (!text) return;
    tr.push({ role: role, content: text.slice(0, 8000), ts: Date.now() });
    if (tr.length > 200) tr.splice(0, tr.length - 200);
    saveState();
    renderBody();
  }
  function pick(obj, fields) {
    if (!obj || typeof obj !== "object") return null;
    for (var i = 0; i < fields.length; i++) {
      var v = obj[fields[i]];
      if (typeof v === "string" && v.trim()) return v;
    }
    return null;
  }
  function captureRequest(bodyStr) {
    if (!bodyStr) return;
    try {
      var obj = JSON.parse(bodyStr);
      var msg = pick(obj, USER_FIELDS);
      if (msg) pushTurn("user", msg);
    } catch (e) { /* not json, skip */ }
  }
  function captureResponse(text) {
    if (!text) return;
    try {
      var obj = JSON.parse(text);
      var reply = pick(obj, BOT_FIELDS);
      if (reply) { pushTurn("assistant", reply); return; }
    } catch (e) { /* not json */ }
  }
  function isOwn(url) {
    return typeof url === "string" && url.indexOf(BASE + "/") !== -1;
  }

  var origFetch = window.fetch;
  if (origFetch) {
    window.fetch = function (input, init) {
      var url = (typeof input === "string") ? input : (input && input.url) || "";
      var method = ((init && init.method) ||
        (input && input.method) || "GET").toUpperCase();
      if (method === "POST" && currentLab && !isOwn(url) && init && init.body &&
        typeof init.body === "string") {
        captureRequest(init.body);
      }
      return origFetch.apply(this, arguments).then(function (resp) {
        if (method === "POST" && currentLab && !isOwn(url)) {
          try {
            resp.clone().text().then(captureResponse).catch(function () {});
          } catch (e) { /* ignore */ }
        }
        return resp;
      });
    };
  }

  var XHR = window.XMLHttpRequest;
  if (XHR) {
    var origOpen = XHR.prototype.open;
    var origSend = XHR.prototype.send;
    XHR.prototype.open = function (method, url) {
      this.__coach = { method: (method || "GET").toUpperCase(), url: url || "" };
      return origOpen.apply(this, arguments);
    };
    XHR.prototype.send = function (body) {
      var meta = this.__coach;
      if (meta && meta.method === "POST" && currentLab && !isOwn(meta.url) &&
        typeof body === "string") {
        captureRequest(body);
      }
      if (meta) {
        var self = this;
        this.addEventListener("load", function () {
          if (meta.method === "POST" && currentLab && !isOwn(meta.url)) {
            try { captureResponse(self.responseText); } catch (e) { /* ignore */ }
          }
        });
      }
      return origSend.apply(this, arguments);
    };
  }

  // ---- backend calls ------------------------------------------------------
  function api(path, payload) {
    return origFetch(BASE + path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    }).then(function (r) { return r.json().then(function (j) { return { ok: r.ok, body: j }; }); });
  }

  function sendEvent(type, challengeKey, data) {
    var ev = {
      event_type: type, challenge_key: challengeKey, data: data || {},
      student_token: state.token, client_timestamp: new Date().toISOString()
    };
    return api("/event", ev).then(function (res) {
      if (!res.body || !res.body.ok) enqueue(ev);
      return res.body;
    }).catch(function () { enqueue(ev); return { ok: false, queued: true }; });
  }
  function enqueue(ev) {
    var q = loadQueue(); q.push(ev); saveQueue(q.slice(-300));
  }
  function loadQueue() {
    try { return JSON.parse(localStorage.getItem(QUEUE_KEY) || "[]"); } catch (e) { return []; }
  }
  function saveQueue(q) {
    try { localStorage.setItem(QUEUE_KEY, JSON.stringify(q)); } catch (e) { /* ignore */ }
  }
  function flushQueue() {
    var q = loadQueue();
    if (!q.length) return;
    saveQueue([]);
    q.forEach(function (ev) {
      api("/event", ev).then(function (res) {
        if (!res.body || !res.body.ok) enqueue(ev);
      }).catch(function () { enqueue(ev); });
    });
  }

  // ---- lab detection ------------------------------------------------------
  function detectLab() {
    if (!config || !config.labs) return null;
    var path = window.location.pathname;
    for (var i = 0; i < config.labs.length; i++) {
      if (path.indexOf(config.labs[i].match) === 0) return config.labs[i];
    }
    return null;
  }

  // ---- UI -----------------------------------------------------------------
  function el(tag, cls, txt) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (txt != null) e.textContent = txt;
    return e;
  }

  function buildUI() {
    var launcher = el("button", "coach-launcher");
    launcher.setAttribute("aria-label", t("title"));
    launcher.textContent = "JL";
    launcher.addEventListener("click", togglePanel);

    var panel = el("aside", "coach-panel coach-hidden");

    var header = el("div", "coach-header");
    var titleWrap = el("div", "coach-title-wrap");
    ui.title = el("span", "coach-title", t("title"));
    ui.sub = el("span", "coach-sub", "");
    titleWrap.appendChild(ui.title); titleWrap.appendChild(ui.sub);
    var langBtn = el("button", "coach-lang", state.lang.toUpperCase());
    langBtn.addEventListener("click", toggleLang);
    var closeBtn = el("button", "coach-close", "×");
    closeBtn.addEventListener("click", togglePanel);
    header.appendChild(titleWrap); header.appendChild(langBtn); header.appendChild(closeBtn);

    ui.content = el("div", "coach-content");

    panel.appendChild(header);
    panel.appendChild(ui.content);

    document.body.appendChild(launcher);
    document.body.appendChild(panel);
    ui.launcher = launcher; ui.panel = panel; ui.langBtn = langBtn;
    renderBody();
    // Deep-link: a URL ending in #coach opens the panel on load, so a
    // teacher can share a link that lands the student straight on the coach.
    if ((window.location.hash || "").toLowerCase().indexOf("coach") !== -1) {
      panel.classList.remove("coach-hidden");
    }
  }

  function togglePanel() { ui.panel.classList.toggle("coach-hidden"); }
  function toggleLang() {
    state.lang = state.lang === "fr" ? "en" : "fr"; saveState();
    ui.langBtn.textContent = state.lang.toUpperCase();
    ui.title.textContent = t("title");
    renderBody();
  }

  function renderBody() {
    if (!ui.content) return;
    var c = ui.content; c.innerHTML = "";

    if (!currentLab) {
      ui.sub.textContent = "";
      c.appendChild(el("p", "coach-muted", t("no_lab")));
      appendCohortLine(c);
      return;
    }
    ui.sub.textContent = currentLab.owasp || "";

    var name = state.lang === "fr" ? currentLab.name_fr : currentLab.name_en;
    c.appendChild(el("h3", "coach-lab-name", name));

    var goalWrap = el("div", "coach-goal");
    goalWrap.appendChild(el("span", "coach-label", t("goal")));
    goalWrap.appendChild(el("p", null,
      state.lang === "fr" ? currentLab.goal_fr : currentLab.goal_en));
    c.appendChild(goalWrap);

    // verdict banner if previously solved
    if (state.solved[currentLab.key]) {
      var banner = el("div", "coach-verdict coach-ok",
        t("solved") + " ✓");
      c.appendChild(banner);
    }

    // transcript summary
    var tr = transcriptFor(currentLab.key);
    var sum = el("div", "coach-summary");
    sum.appendChild(el("span", "coach-label", t("captured")));
    sum.appendChild(el("span", "coach-count", tr.length + " " + t("turns")));
    c.appendChild(sum);

    // actions
    var actions = el("div", "coach-actions");
    var hintBtn = el("button", "coach-btn", t("hint"));
    hintBtn.addEventListener("click", onHint);
    var judgeBtn = el("button", "coach-btn coach-btn-primary", t("judge"));
    judgeBtn.addEventListener("click", onJudge);
    var viewBtn = el("button", "coach-btn coach-btn-ghost", t("view"));
    viewBtn.addEventListener("click", toggleTranscript);
    actions.appendChild(hintBtn); actions.appendChild(judgeBtn); actions.appendChild(viewBtn);
    c.appendChild(actions);

    ui.status = el("div", "coach-status");
    c.appendChild(ui.status);

    ui.transcriptBox = el("div", "coach-transcript coach-hidden");
    renderTranscript();
    c.appendChild(ui.transcriptBox);

    // journal
    var jWrap = el("div", "coach-journal");
    jWrap.appendChild(el("span", "coach-label", t("journal")));
    var ta = el("textarea", "coach-textarea");
    ta.placeholder = t("journal_q");
    ta.value = (state.journal && state.journal[currentLab.key]) || "";
    var saveBtn = el("button", "coach-btn", t("save"));
    saveBtn.addEventListener("click", function () { onJournal(ta.value); });
    jWrap.appendChild(ta); jWrap.appendChild(saveBtn);
    c.appendChild(jWrap);

    appendCohortLine(c);
  }

  function appendCohortLine(c) {
    var line = el("div", "coach-cohort");
    if (config && config.dashboard_configured) {
      line.textContent = t("cohort") + ": " + (config.cohort_id || "-");
    } else {
      line.textContent = t("dashboard_off");
    }
    c.appendChild(line);
  }

  function renderTranscript() {
    if (!ui.transcriptBox) return;
    ui.transcriptBox.innerHTML = "";
    var tr = transcriptFor(currentLab.key);
    if (!tr.length) {
      ui.transcriptBox.appendChild(el("p", "coach-muted", t("empty")));
      return;
    }
    tr.forEach(function (turn) {
      var row = el("div", "coach-turn coach-turn-" + turn.role);
      row.appendChild(el("span", "coach-turn-role",
        turn.role === "user" ? t("you") : t("bot")));
      row.appendChild(el("p", "coach-turn-text", turn.content));
      ui.transcriptBox.appendChild(row);
    });
    var resetBtn = el("button", "coach-btn coach-btn-ghost", t("reset"));
    resetBtn.addEventListener("click", function () {
      state.transcripts[currentLab.key] = []; saveState(); renderBody();
    });
    ui.transcriptBox.appendChild(resetBtn);
  }
  function toggleTranscript() {
    if (ui.transcriptBox) ui.transcriptBox.classList.toggle("coach-hidden");
  }

  function setStatus(msg, kind) {
    if (!ui.status) return;
    ui.status.textContent = msg || "";
    ui.status.className = "coach-status" + (kind ? " coach-" + kind : "");
  }

  // ---- actions ------------------------------------------------------------
  function onHint() {
    var lvl = (state.hintLevel[currentLab.key] || 0) + 1;
    if (lvl > 3) lvl = 3;
    state.hintLevel[currentLab.key] = lvl; saveState();
    setStatus(t("hinting"), "muted");
    api("/hint", {
      lab_key: currentLab.key, level: lvl, lang: state.lang,
      transcript: transcriptFor(currentLab.key)
    }).then(function (res) {
      if (!res.ok || !res.body || res.body.error) { setStatus(t("unavailable"), "warn"); return; }
      setStatus("");
      showHint(lvl, res.body.hint);
      sendEvent("hint_revealed", currentLab.key, {
        hint_level: lvl, student_email: studentName()
      });
    }).catch(function () { setStatus(t("unavailable"), "warn"); });
  }
  function showHint(lvl, text) {
    var box = el("div", "coach-hint");
    box.appendChild(el("span", "coach-hint-lvl", t("hint_level") + " " + lvl + "/3"));
    box.appendChild(el("p", null, text));
    ui.status.parentNode.insertBefore(box, ui.status.nextSibling);
  }

  function onJudge() {
    var tr = transcriptFor(currentLab.key);
    if (!tr.length) { setStatus(t("empty"), "warn"); return; }
    setStatus(t("judging"), "muted");
    api("/judge", { lab_key: currentLab.key, transcript: tr })
      .then(function (res) {
        if (!res.ok || !res.body || res.body.error) {
          setStatus((res.body && res.body.reason) || t("unavailable"), "warn"); return;
        }
        setStatus("");
        showVerdict(res.body);
        if (res.body.success) {
          state.solved[currentLab.key] = true; saveState();
          sendEvent("challenge_solved", currentLab.key, {
            score: res.body.score, verdict: res.body.verdict,
            rationale: res.body.reason, judged_by: "llm",
            student_email: studentName()
          });
        }
      }).catch(function () { setStatus(t("unavailable"), "warn"); });
  }
  function showVerdict(v) {
    var old = ui.content.querySelector(".coach-verdict-live");
    if (old) old.remove();
    var kind = v.success ? "ok" : (v.partial ? "warn" : "bad");
    var label = v.success ? t("solved") : (v.partial ? t("partial") : t("notyet"));
    var box = el("div", "coach-verdict coach-verdict-live coach-" + kind);
    box.appendChild(el("strong", null, label + "  —  " + t("score") + " " + v.score + "/100"));
    if (v.reason) box.appendChild(el("p", "coach-verdict-reason", v.reason));
    ui.status.parentNode.insertBefore(box, ui.status.nextSibling);
  }

  function onJournal(text) {
    if (!state.journal) state.journal = {};
    state.journal[currentLab.key] = text; saveState();
    setStatus(t("journal_saved"), "ok");
    sendEvent("journal_filled", currentLab.key, {
      length: text.length, after: text.slice(0, 4000),
      student_email: studentName()
    });
  }

  // Best-effort student display name from the PwnzzAI navbar (alice/bob).
  function studentName() {
    try {
      var nav = document.querySelector(".navbar, nav");
      if (!nav) return "";
      var m = nav.textContent.match(/(alice|bob)/i);
      return m ? m[1].toLowerCase() : "";
    } catch (e) { return ""; }
  }

  // ---- boot ---------------------------------------------------------------
  function boot() {
    origFetch(BASE + "/config").then(function (r) { return r.json(); })
      .then(function (cfg) {
        config = cfg;
        // server gives no default language; honour a ?lang or keep stored
        currentLab = detectLab();
        buildUI();
        flushQueue();
        sendEvent("session_start", currentLab ? currentLab.key : null, {
          path: window.location.pathname, student_email: studentName()
        });
      })
      .catch(function () {
        // even without config, render an empty panel so the student sees it
        config = { labs: [], dashboard_configured: false };
        buildUI();
      });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
