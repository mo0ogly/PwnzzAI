/*
 * JuiceLab Coach for PwnzzAI — persistent state, scoring, badges.
 * Exposed as window.CoachState. Mirrors JuiceLab's model:
 *   scoring = max(50, 100 - sum(hint costs))   (floor 50)
 * localStorage key: pwnzzai_coach_v1
 */
(function () {
  "use strict";
  if (window.CoachState) return;

  var STORE_KEY = "pwnzzai_coach_v1";
  var SCORE_INITIAL = 100;
  var SCORE_FLOOR = 50;

  function uuid() {
    if (window.crypto && crypto.randomUUID) return crypto.randomUUID();
    return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, function (c) {
      var r = (Math.random() * 16) | 0, v = c === "x" ? r : (r & 0x3) | 0x8;
      return v.toString(16);
    });
  }

  function emptyState() {
    return {
      schema_version: 1,
      student: { token: uuid(), language: "fr", identity: "", email: "", join_status: "" },
      challenges: {},
      badges_earned: []
    };
  }

  function load() {
    try {
      var raw = localStorage.getItem(STORE_KEY);
      if (raw) {
        var s = JSON.parse(raw);
        if (s && s.student && s.student.token) {
          if (!s.challenges) s.challenges = {};
          if (!s.badges_earned) s.badges_earned = [];
          return s;
        }
      }
    } catch (e) { /* ignore */ }
    return emptyState();
  }

  var state = load();

  function save() {
    try { localStorage.setItem(STORE_KEY, JSON.stringify(state)); } catch (e) { /* ignore */ }
  }

  function challenge(key) {
    if (!state.challenges[key]) {
      state.challenges[key] = {
        hints: [],            // levels revealed, e.g. [1,2]
        journal: { before: "", after: "" },
        quiz_score: null,
        solved: false,
        verdict: null
      };
    }
    return state.challenges[key];
  }

  // scoring: 100 - sum of revealed hint costs, floored at 50
  function scoreFor(key, costByLevel) {
    var c = challenge(key);
    var spent = 0;
    c.hints.forEach(function (lvl) { spent += (costByLevel[lvl] || costByLevel[String(lvl)] || 0); });
    return Math.max(SCORE_FLOOR, SCORE_INITIAL - spent);
  }

  window.CoachState = {
    raw: function () { return state; },
    token: function () { return state.student.token; },
    lang: function () { return state.student.language || "fr"; },
    setLang: function (l) { state.student.language = l; save(); },
    identity: function () { return state.student.identity || ""; },
    setIdentity: function (id) {
      var v = (id || "").trim();
      if (v && v !== state.student.identity) { state.student.identity = v; save(); }
      return state.student.identity || "";
    },
    // Cohort enrolment: the email is the canonical identity the teacher sees
    // in the roster; join_status is unknown/pending/validated/rejected.
    email: function () { return state.student.email || ""; },
    setEmail: function (e) { state.student.email = (e || "").trim(); save(); },
    joinStatus: function () { return state.student.join_status || ""; },
    setJoinStatus: function (s) {
      var v = (s || "").trim();
      if (v !== state.student.join_status) { state.student.join_status = v; save(); }
      return state.student.join_status || "";
    },

    challenge: challenge,
    scoreFor: scoreFor,
    SCORE_FLOOR: SCORE_FLOOR,
    SCORE_INITIAL: SCORE_INITIAL,

    // next hint level to reveal (1..5), or 0 if all 5 done
    nextHintLevel: function (key) {
      var c = challenge(key);
      for (var lvl = 1; lvl <= 5; lvl++) {
        if (c.hints.indexOf(lvl) === -1) return lvl;
      }
      return 0;
    },
    revealHint: function (key, level) {
      var c = challenge(key);
      if (c.hints.indexOf(level) === -1) { c.hints.push(level); c.hints.sort(); save(); }
    },
    setJournal: function (key, phase, text) {
      challenge(key).journal[phase] = text; save();
    },
    setQuizScore: function (key, score) {
      challenge(key).quiz_score = score; save();
    },
    setSolved: function (key, verdict) {
      var c = challenge(key); c.solved = true; c.verdict = verdict; save();
    },
    // Cache the post-success walkthrough so it survives a reload (the
    // in-memory transcript needed to regenerate it does not).
    setWalkthrough: function (key, text) { challenge(key).walkthrough = text; save(); },
    walkthrough: function (key) { return challenge(key).walkthrough || ""; },

    // --- badges ---
    badgesEarned: function () { return state.badges_earned.slice(); },
    /** Recompute badges; returns the list of NEWLY earned badge ids. */
    reevaluateBadges: function () {
      var chs = state.challenges;
      var keys = Object.keys(chs);
      var solved = keys.filter(function (k) { return chs[k].solved; });
      var solvedNoHint = solved.filter(function (k) { return chs[k].hints.length === 0; });
      var afterJournals = keys.filter(function (k) {
        var a = (chs[k].journal.after || "").trim();
        return a.split(/\s+/).filter(Boolean).length >= 50;
      });
      // 'apex' needs every known lab solved with no hint; total labs injected at runtime
      var totalLabs = window.__COACH_TOTAL_LABS__ || 13;

      var earned = {
        ai_red_teamer: solvedNoHint.length >= 3,
        persistent: solved.length >= 6,
        reflective: afterJournals.length >= 5,
        apex: solved.length >= totalLabs && solvedNoHint.length >= totalLabs
      };
      var newly = [];
      Object.keys(earned).forEach(function (id) {
        if (earned[id] && state.badges_earned.indexOf(id) === -1) {
          state.badges_earned.push(id); newly.push(id);
        }
      });
      if (newly.length) save();
      return newly;
    },

    /** Aggregate stats for the progress tab. */
    summary: function (costByLevel) {
      var chs = state.challenges;
      var keys = Object.keys(chs);
      var solved = keys.filter(function (k) { return chs[k].solved; });
      var scores = solved.map(function (k) { return scoreFor(k, costByLevel); });
      var avg = scores.length
        ? Math.round(scores.reduce(function (a, b) { return a + b; }, 0) / scores.length)
        : 0;
      return { started: keys.length, solved: solved.length, avg: avg };
    }
  };
})();
