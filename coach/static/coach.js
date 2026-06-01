/*
 * JuiceLab Coach for PwnzzAI — UI orchestrator (tabbed sidebar).
 * Depends on: coach-i18n.js, coach-state.js, coach-api.js (loaded first).
 *
 * Tabs: Briefing | Hints (5 graded levels) | Journal (before/after) |
 *       Quiz (3 MCQ) | Progress (score, badges, dashboard).
 * Pure vanilla JS. PwnzzAI source is never modified.
 */
(function () {
  "use strict";
  if (window.__COACH_LOADED__) return;
  window.__COACH_LOADED__ = true;

  var I18n = window.CoachI18n, St = window.CoachState, Api = window.CoachApi;
  var config = null, currentLab = null, costByLevel = { 1: 5, 2: 10, 3: 20, 4: 35, 5: 50 };
  var activeTab = "briefing";
  var ui = {};

  function t(k) { return I18n.t(St.lang(), k); }
  function el(tag, cls, txt) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (txt != null) e.textContent = txt;
    return e;
  }

  // ---- lab detection ----
  function detectLab() {
    if (!config || !config.labs) return null;
    var path = window.location.pathname;
    for (var i = 0; i < config.labs.length; i++) {
      if (path.indexOf(config.labs[i].match) === 0) return config.labs[i];
    }
    return null;
  }
  function labName(lab) { return St.lang() === "fr" ? lab.name_fr : lab.name_en; }

  // ---- shell ----
  function buildShell() {
    var launcher = el("button", "coach-launcher", "JL");
    launcher.setAttribute("aria-label", t("title"));
    launcher.addEventListener("click", togglePanel);

    var panel = el("aside", "coach-panel coach-hidden");
    var header = el("div", "coach-header");
    var tw = el("div", "coach-title-wrap");
    ui.title = el("span", "coach-title", t("title"));
    ui.sub = el("span", "coach-sub", "");
    tw.appendChild(ui.title); tw.appendChild(ui.sub);
    ui.langBtn = el("button", "coach-lang", St.lang().toUpperCase());
    ui.langBtn.addEventListener("click", toggleLang);
    var closeBtn = el("button", "coach-close", "×");
    closeBtn.addEventListener("click", togglePanel);
    header.appendChild(tw); header.appendChild(ui.langBtn); header.appendChild(closeBtn);

    ui.tabs = el("div", "coach-tabs");
    ui.body = el("div", "coach-content");

    panel.appendChild(header); panel.appendChild(ui.tabs); panel.appendChild(ui.body);
    document.body.appendChild(launcher);
    document.body.appendChild(panel);
    ui.launcher = launcher; ui.panel = panel;

    renderTabs();
    render();
    if ((window.location.hash || "").toLowerCase().indexOf("coach") !== -1) {
      panel.classList.remove("coach-hidden");
    }
  }
  function togglePanel() { ui.panel.classList.toggle("coach-hidden"); }
  function toggleLang() {
    St.setLang(St.lang() === "fr" ? "en" : "fr");
    ui.langBtn.textContent = St.lang().toUpperCase();
    ui.title.textContent = t("title");
    renderTabs(); render();
  }

  var TABS = ["briefing", "hints", "journal", "quiz", "progress"];
  function renderTabs() {
    if (!ui.tabs) return;
    ui.tabs.innerHTML = "";
    if (!currentLab) return;
    TABS.forEach(function (id) {
      var b = el("button", "coach-tab" + (id === activeTab ? " coach-tab-active" : ""),
        t("tab_" + id));
      b.addEventListener("click", function () { activeTab = id; renderTabs(); render(); });
      ui.tabs.appendChild(b);
    });
  }

  function render() {
    if (!ui.body) return;
    var c = ui.body; c.innerHTML = "";
    if (!currentLab) {
      c.appendChild(el("p", "coach-muted", t("no_lab")));
      renderProgress(c);   // still show global progress + dashboard line
      return;
    }
    ui.sub.textContent = currentLab.owasp || "";
    if (activeTab === "briefing") renderBriefing(c);
    else if (activeTab === "hints") renderHints(c);
    else if (activeTab === "journal") renderJournal(c);
    else if (activeTab === "quiz") renderQuiz(c);
    else renderProgress(c);
  }

  // ---- briefing tab ----
  function renderBriefing(c) {
    c.appendChild(el("h3", "coach-lab-name", labName(currentLab)));
    var g = el("div", "coach-block");
    g.appendChild(el("span", "coach-label", t("mission")));
    g.appendChild(el("p", null, St.lang() === "fr" ? currentLab.goal_fr : currentLab.goal_en));
    c.appendChild(g);
    var concepts = currentLab.concepts || [];
    if (concepts.length) {
      c.appendChild(el("span", "coach-label", t("concepts")));
      concepts.forEach(function (cp) {
        var card = el("div", "coach-concept");
        card.appendChild(el("strong", null, St.lang() === "fr" ? cp.title_fr : cp.title_en));
        card.appendChild(el("p", null, St.lang() === "fr" ? cp.body_fr : cp.body_en));
        c.appendChild(card);
      });
    }
  }

  // ---- hints tab ----
  function renderHints(c) {
    var ch = St.challenge(currentLab.key);
    var head = el("div", "coach-summary");
    head.appendChild(el("span", "coach-label", t("score_lab")));
    head.appendChild(el("span", "coach-count", St.scoreFor(currentLab.key, costByLevel) + " / 100"));
    c.appendChild(head);

    for (var lvl = 1; lvl <= 5; lvl++) {
      (function (level) {
        var revealed = ch.hints.indexOf(level) !== -1;
        var row = el("div", "coach-hint-row" + (revealed ? " coach-hint-done" : ""));
        var top = el("div", "coach-hint-top");
        top.appendChild(el("span", "coach-hint-lvl", t("hint_level") + " " + level + "/5"));
        top.appendChild(el("span", "coach-hint-cost", "-" + costByLevel[level] + "%"));
        row.appendChild(top);
        if (revealed && ch["hint_text_" + level]) {
          row.appendChild(el("p", "coach-hint-text", ch["hint_text_" + level]));
        } else if (!revealed) {
          var next = St.nextHintLevel(currentLab.key);
          var btn = el("button", "coach-btn", t("hint_reveal"));
          if (level !== next) { btn.disabled = true; btn.title = t("hint_locked"); }
          btn.addEventListener("click", function () { revealHint(level); });
          row.appendChild(btn);
        }
        c.appendChild(row);
      })(lvl);
    }
    ui.hintStatus = el("div", "coach-status");
    c.appendChild(ui.hintStatus);
  }

  function revealHint(level) {
    if (ui.hintStatus) { ui.hintStatus.textContent = t("hinting"); ui.hintStatus.className = "coach-status coach-muted"; }
    Api.hint(currentLab.key, level, St.lang(), Api.transcript(currentLab.key))
      .then(function (res) {
        if (!res.ok || !res.body || res.body.error) {
          if (ui.hintStatus) { ui.hintStatus.textContent = t("unavailable"); ui.hintStatus.className = "coach-status coach-warn"; }
          return;
        }
        St.revealHint(currentLab.key, level);
        St.challenge(currentLab.key)["hint_text_" + level] = res.body.hint;
        Api.sendEvent("hint_revealed", currentLab.key, {
          level: "N" + level, cost_pct: res.body.cost_pct,
          score_after: St.scoreFor(currentLab.key, costByLevel),
          student_email: identity()
        });
        render();
      })
      .catch(function () {
        if (ui.hintStatus) { ui.hintStatus.textContent = t("unavailable"); ui.hintStatus.className = "coach-status coach-warn"; }
      });
  }

  // ---- journal tab ----
  function renderJournal(c) {
    var ch = St.challenge(currentLab.key);
    [["before", "journal_before", "journal_before_ph"],
     ["after", "journal_after", "journal_after_ph"]].forEach(function (spec) {
      var phase = spec[0];
      var wrap = el("div", "coach-block");
      wrap.appendChild(el("span", "coach-label", t(spec[1])));
      var ta = el("textarea", "coach-textarea");
      ta.placeholder = t(spec[2]);
      ta.value = ch.journal[phase] || "";
      var meta = el("div", "coach-journal-meta");
      var wc = el("span", "coach-muted", wordCount(ta.value) + " " + t("words"));
      ta.addEventListener("input", function () { wc.textContent = wordCount(ta.value) + " " + t("words"); });
      var btn = el("button", "coach-btn", t("save"));
      var done = el("span", "coach-ok", "");
      btn.addEventListener("click", function () {
        St.setJournal(currentLab.key, phase, ta.value);
        done.textContent = " " + t("saved");
        if (phase === "after") {
          Api.sendEvent("journal_filled", currentLab.key, {
            length: ta.value.length, after: ta.value.slice(0, 4000),
            student_email: identity()
          });
          maybeAwardBadges();
        }
      });
      meta.appendChild(wc); meta.appendChild(btn); meta.appendChild(done);
      wrap.appendChild(ta); wrap.appendChild(meta);
      c.appendChild(wrap);
    });
  }
  function wordCount(s) { return (s || "").trim().split(/\s+/).filter(Boolean).length; }

  // ---- quiz tab ----
  function renderQuiz(c) {
    if ((currentLab.quiz_count || 0) === 0) { c.appendChild(el("p", "coach-muted", "—")); return; }
    if (!ui.quizCache || ui.quizCache.key !== currentLab.key) {
      c.appendChild(el("p", "coach-muted", "..."));
      Api.quizQuestions(currentLab.key).then(function (res) {
        if (res.ok && res.body && res.body.questions) {
          ui.quizCache = { key: currentLab.key, questions: res.body.questions, answers: [] };
          if (activeTab === "quiz") render();
        }
      });
      return;
    }
    ui.quizCache.questions.forEach(function (q, qi) {
      var block = el("div", "coach-quiz-q");
      block.appendChild(el("p", "coach-quiz-question",
        (qi + 1) + ". " + (St.lang() === "fr" ? q.question_fr : q.question_en)));
      var opts = St.lang() === "fr" ? q.options_fr : q.options_en;
      opts.forEach(function (opt, oi) {
        var lab = el("label", "coach-quiz-opt");
        var radio = el("input");
        radio.type = "radio"; radio.name = "q" + qi; radio.value = oi;
        if (ui.quizCache.answers[qi] === oi) radio.checked = true;
        radio.addEventListener("change", function () { ui.quizCache.answers[qi] = oi; });
        lab.appendChild(radio); lab.appendChild(el("span", null, opt));
        block.appendChild(lab);
      });
      c.appendChild(block);
    });
    ui.quizStatus = el("div", "coach-status");
    var submit = el("button", "coach-btn coach-btn-primary", t("quiz_submit"));
    submit.addEventListener("click", submitQuiz);
    c.appendChild(submit); c.appendChild(ui.quizStatus);
    if (ui.quizCache.result) renderQuizResult(c, ui.quizCache.result);
  }

  function submitQuiz() {
    var cache = ui.quizCache;
    if (!cache) return;
    if (cache.answers.filter(function (a) { return a != null; }).length < cache.questions.length) {
      ui.quizStatus.textContent = t("quiz_pick"); ui.quizStatus.className = "coach-status coach-warn"; return;
    }
    Api.quizScore(currentLab.key, cache.answers, St.lang()).then(function (res) {
      if (!res.ok || !res.body) { ui.quizStatus.textContent = t("unavailable"); ui.quizStatus.className = "coach-status coach-warn"; return; }
      cache.result = res.body;
      St.setQuizScore(currentLab.key, res.body.score);
      Api.sendEvent("quiz_completed", currentLab.key, {
        score: res.body.score, correct: res.body.correct_count, total: res.body.total,
        student_email: identity()
      });
      render();
    }).catch(function () { ui.quizStatus.textContent = t("unavailable"); ui.quizStatus.className = "coach-status coach-warn"; });
  }
  function renderQuizResult(c, r) {
    var box = el("div", "coach-verdict coach-" + (r.score >= 67 ? "ok" : (r.score >= 34 ? "warn" : "bad")));
    box.appendChild(el("strong", null, t("quiz_score") + " " + r.score + "/100 (" + r.correct_count + "/" + r.total + ")"));
    (r.by_question || []).forEach(function (q, i) {
      var line = el("p", "coach-quiz-explain");
      line.appendChild(el("span", q.ok ? "coach-ok" : "coach-bad",
        (i + 1) + ". " + (q.ok ? t("quiz_correct") : t("quiz_wrong")) + " — "));
      line.appendChild(document.createTextNode(q.explanation || ""));
      box.appendChild(line);
    });
    var redo = el("button", "coach-btn coach-btn-ghost", t("quiz_redo"));
    redo.addEventListener("click", function () { ui.quizCache.result = null; ui.quizCache.answers = []; render(); });
    box.appendChild(redo);
    c.appendChild(box);
  }

  // ---- progress tab (student dashboard) ----
  function renderProgress(c) {
    if (currentLab) {
      var conv = el("div", "coach-summary");
      conv.appendChild(el("span", "coach-label", t("captured")));
      conv.appendChild(el("span", "coach-count", Api.transcript(currentLab.key).length + " " + t("turns")));
      c.appendChild(conv);
      var actions = el("div", "coach-actions");
      var judgeBtn = el("button", "coach-btn coach-btn-primary", t("judge"));
      judgeBtn.addEventListener("click", runJudge);
      var viewBtn = el("button", "coach-btn coach-btn-ghost", t("view"));
      viewBtn.addEventListener("click", function () { toggleConv(c); });
      actions.appendChild(judgeBtn); actions.appendChild(viewBtn);
      c.appendChild(actions);
      ui.judgeStatus = el("div", "coach-status"); c.appendChild(ui.judgeStatus);
      ui.convBox = el("div", "coach-transcript coach-hidden"); c.appendChild(ui.convBox);
      var ch = St.challenge(currentLab.key);
      if (ch.solved) {
        var v = el("div", "coach-verdict coach-ok");
        v.appendChild(el("strong", null, t("solved") + " ✓  —  " + t("score") + " " + St.scoreFor(currentLab.key, costByLevel) + "/100"));
        if (config && config.dashboard_configured) {
          v.appendChild(proofButton(currentLab.key));
        }
        v.appendChild(walkthroughButton(currentLab.key));
        c.appendChild(v);
        ui.wtBox = el("div", "coach-walkthrough"); c.appendChild(ui.wtBox);
        if (St.walkthrough(currentLab.key)) renderWalkthrough(St.walkthrough(currentLab.key));
      }
    }

    var sum = St.summary(costByLevel);
    var grid = el("div", "coach-stats");
    grid.appendChild(stat(sum.solved + (config ? " / " + config.labs.length : ""), t("labs_solved")));
    grid.appendChild(stat(sum.avg + "/100", t("total_score")));
    c.appendChild(el("span", "coach-label", t("progress_title")));
    c.appendChild(grid);

    var chs = St.raw().challenges;
    var keys = Object.keys(chs);
    if (!keys.length) {
      c.appendChild(el("p", "coach-muted", t("progress_none")));
    } else {
      var list = el("div", "coach-lab-list");
      (config ? config.labs : []).forEach(function (lab) {
        if (!chs[lab.key]) return;
        var lch = chs[lab.key];
        var row = el("div", "coach-lab-row");
        row.appendChild(el("span", "coach-lab-row-name", labName(lab)));
        row.appendChild(el("span", "coach-chip " + (lch.solved ? "coach-chip-ok" : "coach-chip-pending"),
          lch.solved ? t("solved") : (lch.hints.length + " " + t("hints_consumed"))));
        if (lch.solved && config && config.dashboard_configured) {
          row.appendChild(proofButton(lab.key));
        }
        list.appendChild(row);
      });
      c.appendChild(list);
    }

    c.appendChild(el("span", "coach-label", t("badges")));
    var earned = St.badgesEarned();
    var bgrid = el("div", "coach-badges");
    I18n.badges.forEach(function (b) {
      var has = earned.indexOf(b.id) !== -1;
      var card = el("div", "coach-badge coach-badge-" + b.tier + (has ? " coach-badge-on" : " coach-badge-off"));
      card.appendChild(el("strong", null, St.lang() === "fr" ? b.label_fr : b.label_en));
      card.appendChild(el("p", null, has ? (St.lang() === "fr" ? b.desc_fr : b.desc_en) : t("badge_locked")));
      bgrid.appendChild(card);
    });
    c.appendChild(bgrid);

    if (config && config.dashboard_configured) c.appendChild(identityBlock());

    var line = el("div", "coach-cohort");
    if (config && config.dashboard_configured) line.textContent = t("cohort") + ": " + (config.cohort_id || "-");
    else line.textContent = t("dashboard_off");
    c.appendChild(line);
  }
  function stat(value, label) {
    var s = el("div", "coach-stat");
    s.appendChild(el("span", "coach-stat-val", value));
    s.appendChild(el("span", "coach-stat-lbl", label));
    return s;
  }

  // Download the dashboard-signed proof for a solved lab. The dashboard
  // signs (HMAC) and returns markdown on 200, or a JSON error otherwise
  // (e.g. no events yet, proof signing disabled). We surface that error on
  // the button rather than downloading an error page.
  function proofButton(key) {
    var btn = el("button", "coach-btn coach-btn-ghost", t("proof_download"));
    btn.addEventListener("click", function () {
      var label = btn.textContent;
      btn.disabled = true; btn.textContent = t("proof_preparing");
      fetch(Api.proofUrl(key, St.lang())).then(function (r) {
        if (!r.ok) {
          return r.json().then(function (j) {
            throw new Error((j && j.error) || ("HTTP " + r.status));
          });
        }
        var fn = "pwnzzai-" + key + ".md";
        var m = (r.headers.get("Content-Disposition") || "").match(/filename="([^"]+)"/);
        if (m) fn = m[1];
        return r.blob().then(function (blob) {
          var url = URL.createObjectURL(blob);
          var a = el("a"); a.href = url; a.download = fn;
          document.body.appendChild(a); a.click(); document.body.removeChild(a);
          setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
          btn.textContent = label; btn.disabled = false;
        });
      }).catch(function () {
        btn.textContent = t("proof_error"); btn.disabled = false;
      });
    });
    return btn;
  }

  // Reveal the walkthrough (corrige). Server re-judges the transcript and
  // only returns it on a successful verdict, so this stays gated even though
  // the button is shown from the client's solved flag. Cached once fetched
  // because the in-memory transcript is gone after a reload.
  function walkthroughButton(key) {
    var btn = el("button", "coach-btn coach-btn-ghost", t("walkthrough_show"));
    btn.addEventListener("click", function () {
      if (St.walkthrough(key)) { renderWalkthrough(St.walkthrough(key)); return; }
      var label = btn.textContent;
      btn.disabled = true; btn.textContent = t("walkthrough_loading");
      Api.walkthrough(key, Api.transcript(key), St.lang()).then(function (res) {
        btn.textContent = label; btn.disabled = false;
        if (res.ok && res.body && res.body.walkthrough) {
          St.setWalkthrough(key, res.body.walkthrough);
          renderWalkthrough(res.body.walkthrough);
        } else if (res.body && res.body.error === "solve_first") {
          renderWalkthrough(t("walkthrough_gate"));
        } else {
          renderWalkthrough(t("unavailable"));
        }
      }).catch(function () {
        btn.textContent = label; btn.disabled = false;
        renderWalkthrough(t("unavailable"));
      });
    });
    return btn;
  }

  // Render walkthrough markdown as readable text blocks (no HTML injection:
  // split on blank lines, keep bullets as-is).
  function renderWalkthrough(md) {
    if (!ui.wtBox) return;
    ui.wtBox.innerHTML = "";
    ui.wtBox.appendChild(el("span", "coach-label", t("walkthrough_title")));
    String(md).split(/\n{2,}/).forEach(function (block) {
      var txt = block.trim();
      if (txt) ui.wtBox.appendChild(el("p", "coach-wt-block", txt));
    });
  }

  // Identity used to attribute dashboard events. Auto-filled from the
  // PwnzzAI navbar when the student is logged in; otherwise the student
  // sets it here once. Read-only on the OWASP side.
  function identityBlock() {
    var wrap = el("div", "coach-identity");
    var cur = identity();
    if (cur) {
      wrap.appendChild(el("span", "coach-muted", t("identified_as") + ": " + cur));
      return wrap;
    }
    wrap.appendChild(el("span", "coach-label", t("identity_prompt")));
    var inp = el("input", "coach-input");
    inp.type = "text"; inp.placeholder = t("identity_ph");
    var btn = el("button", "coach-btn", t("save"));
    btn.addEventListener("click", function () { if (St.setIdentity(inp.value)) render(); });
    wrap.appendChild(inp); wrap.appendChild(btn);
    return wrap;
  }
  function toggleConv(c) {
    if (!ui.convBox) return;
    ui.convBox.classList.toggle("coach-hidden");
    if (ui.convBox.classList.contains("coach-hidden")) return;
    ui.convBox.innerHTML = "";
    var tr = Api.transcript(currentLab.key);
    if (!tr.length) { ui.convBox.appendChild(el("p", "coach-muted", t("empty"))); return; }
    tr.forEach(function (turn) {
      var row = el("div", "coach-turn coach-turn-" + turn.role);
      row.appendChild(el("span", "coach-turn-role", turn.role === "user" ? t("you") : t("bot")));
      row.appendChild(el("p", "coach-turn-text", turn.content));
      ui.convBox.appendChild(row);
    });
    var reset = el("button", "coach-btn coach-btn-ghost", t("reset_conv"));
    reset.addEventListener("click", function () { Api.clearTranscript(currentLab.key); render(); });
    ui.convBox.appendChild(reset);
  }

  function runJudge() {
    var tr = Api.transcript(currentLab.key);
    if (!tr.length) { ui.judgeStatus.textContent = t("empty"); ui.judgeStatus.className = "coach-status coach-warn"; return; }
    ui.judgeStatus.textContent = t("judging"); ui.judgeStatus.className = "coach-status coach-muted";
    Api.judge(currentLab.key, tr).then(function (res) {
      if (!res.ok || !res.body || res.body.error) {
        ui.judgeStatus.textContent = (res.body && res.body.reason) || t("unavailable");
        ui.judgeStatus.className = "coach-status coach-warn"; return;
      }
      ui.judgeStatus.textContent = "";
      var v = res.body;
      var kind = v.success ? "ok" : (v.partial ? "warn" : "bad");
      var label = v.success ? t("solved") : (v.partial ? t("partial") : t("notyet"));
      var box = el("div", "coach-verdict coach-" + kind);
      box.appendChild(el("strong", null, label + "  —  " + t("score") + " " + v.score + "/100"));
      if (v.reason) box.appendChild(el("p", "coach-verdict-reason", v.reason));
      ui.judgeStatus.parentNode.insertBefore(box, ui.judgeStatus.nextSibling);
      if (v.success) {
        St.setSolved(currentLab.key, v.verdict);
        Api.sendEvent("challenge_solved", currentLab.key, {
          score: St.scoreFor(currentLab.key, costByLevel), verdict: v.verdict,
          rationale: v.reason, judged_by: "llm", student_email: identity()
        });
        maybeAwardBadges();
      }
    }).catch(function () { ui.judgeStatus.textContent = t("unavailable"); ui.judgeStatus.className = "coach-status coach-warn"; });
  }

  function maybeAwardBadges() {
    var newly = St.reevaluateBadges();
    newly.forEach(function (id) {
      Api.sendEvent("badge_earned", currentLab ? currentLab.key : null, { badge: id, student_email: identity() });
    });
  }

  // Read the username PwnzzAI renders in its own navbar, read-only, without
  // touching the OWASP code. PwnzzAI auth is a server-side Flask session
  // (signed httpOnly cookie, not JS-readable), so unlike Juice Shop's JWT
  // we cannot parse a token; the rendered name is the only browser-exposed
  // identity. Generic — any account, not a hardcoded user list.
  function detectPwnzzUser() {
    try {
      var span = document.querySelector(".welcome-text");
      if (span) {
        var m = span.textContent.match(/[:,]\s*(.+?)\s*!?\s*$/);
        if (m && m[1]) return m[1].trim();
      }
    } catch (e) { /* ignore */ }
    return "";
  }

  // Resolved student identity for dashboard events: the PwnzzAI username if
  // detected (cached so it survives navigation to a page with no navbar),
  // otherwise the explicit identity the student typed into the coach.
  function identity() {
    var detected = detectPwnzzUser();
    if (detected) return St.setIdentity(detected);
    return St.identity();
  }

  // ---- boot ----
  function boot() {
    Api.installCapture();
    Api.config().then(function (res) {
      config = res.body || { labs: [] };
      if (config.hint_cost_by_level) costByLevel = config.hint_cost_by_level;
      window.__COACH_TOTAL_LABS__ = (config.labs || []).length || 13;
      currentLab = detectLab();
      Api.setCurrentLab(currentLab ? currentLab.key : null);
      Api.onTurn(function () { if (activeTab === "progress" || !currentLab) render(); });
      buildShell();
      Api.flushQueue();
      Api.sendEvent("session_start", currentLab ? currentLab.key : null, {
        path: window.location.pathname, student_email: identity()
      });
      installSessionEnd();
    }).catch(function () {
      config = { labs: [], dashboard_configured: false };
      buildShell();
    });
  }

  // Emit session_end exactly once when the tab is closed or the student
  // navigates away, so the teacher dashboard can measure real session
  // duration. pagehide fires on close/navigation (and mobile bfcache);
  // sendBeacon survives unload where a normal fetch is dropped. We avoid
  // visibilitychange on purpose: a quick alt-tab is not the end of a
  // session and would cut it short.
  function installSessionEnd() {
    var sent = false;
    window.addEventListener("pagehide", function () {
      if (sent) return;
      sent = true;
      Api.sendBeacon("session_end", currentLab ? currentLab.key : null, {
        path: window.location.pathname, student_email: identity()
      });
    });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();
})();
