/*
 * JuiceLab Coach for PwnzzAI — backend calls, dashboard sync, transcript
 * capture. Exposed as window.CoachApi.
 *
 * Transcript capture monkey-patches fetch/XHR so any POST the lab page makes
 * (student->assistant) is recorded — lab-agnostic, no per-lab parsing.
 */
(function () {
  "use strict";
  if (window.CoachApi) return;

  var BASE = window.__COACH_BASE__ || "/__coach";
  var QUEUE_KEY = "pwnzzai_coach_queue_v1";

  var USER_FIELDS = ["message", "query", "prompt", "input", "question",
    "text", "user_message", "msg", "content", "doc", "document"];
  var BOT_FIELDS = ["response", "answer", "reply", "result", "output",
    "message", "content", "text", "completion", "data"];

  var origFetch = window.fetch ? window.fetch.bind(window) : null;
  var transcripts = {};          // lab_key -> [{role,content,ts}]
  var currentKey = null;
  var onTurn = null;             // callback(labKey) when a turn is recorded

  function transcriptFor(key) {
    if (!transcripts[key]) transcripts[key] = [];
    return transcripts[key];
  }
  function pushTurn(role, content) {
    if (!currentKey || !content) return;
    var text = String(content).trim();
    if (!text) return;
    var tr = transcriptFor(currentKey);
    tr.push({ role: role, content: text.slice(0, 8000), ts: Date.now() });
    if (tr.length > 200) tr.splice(0, tr.length - 200);
    if (onTurn) { try { onTurn(currentKey); } catch (e) { /* ignore */ } }
  }
  function pick(obj, fields) {
    if (!obj || typeof obj !== "object") return null;
    for (var i = 0; i < fields.length; i++) {
      var v = obj[fields[i]];
      if (typeof v === "string" && v.trim()) return v;
    }
    return null;
  }
  function isOwn(url) { return typeof url === "string" && url.indexOf(BASE + "/") !== -1; }
  function captureReq(bodyStr) {
    if (!bodyStr) return;
    try { var m = pick(JSON.parse(bodyStr), USER_FIELDS); if (m) pushTurn("user", m); }
    catch (e) { /* not json */ }
  }
  function captureResp(text) {
    if (!text) return;
    try { var r = pick(JSON.parse(text), BOT_FIELDS); if (r) pushTurn("assistant", r); }
    catch (e) { /* not json */ }
  }

  function installCapture() {
    if (origFetch) {
      window.fetch = function (input, init) {
        var url = (typeof input === "string") ? input : (input && input.url) || "";
        var method = ((init && init.method) || (input && input.method) || "GET").toUpperCase();
        if (method === "POST" && currentKey && !isOwn(url) && init && typeof init.body === "string") {
          captureReq(init.body);
        }
        return origFetch(input, init).then(function (resp) {
          if (method === "POST" && currentKey && !isOwn(url)) {
            try { resp.clone().text().then(captureResp).catch(function () {}); } catch (e) { /* */ }
          }
          return resp;
        });
      };
    }
    var XHR = window.XMLHttpRequest;
    if (XHR) {
      var oOpen = XHR.prototype.open, oSend = XHR.prototype.send;
      XHR.prototype.open = function (m, u) {
        this.__coach = { method: (m || "GET").toUpperCase(), url: u || "" };
        return oOpen.apply(this, arguments);
      };
      XHR.prototype.send = function (body) {
        var meta = this.__coach, self = this;
        if (meta && meta.method === "POST" && currentKey && !isOwn(meta.url) && typeof body === "string") {
          captureReq(body);
        }
        if (meta) {
          this.addEventListener("load", function () {
            if (meta.method === "POST" && currentKey && !isOwn(meta.url)) {
              try { captureResp(self.responseText); } catch (e) { /* */ }
            }
          });
        }
        return oSend.apply(this, arguments);
      };
    }
  }

  function post(path, payload) {
    return origFetch(BASE + path, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    }).then(function (r) { return r.json().then(function (j) { return { ok: r.ok, body: j }; }); });
  }
  function get(path) {
    return origFetch(BASE + path).then(function (r) {
      return r.json().then(function (j) { return { ok: r.ok, body: j }; });
    });
  }

  // --- offline queue for dashboard events ---
  function loadQueue() {
    try { return JSON.parse(localStorage.getItem(QUEUE_KEY) || "[]"); } catch (e) { return []; }
  }
  function saveQueue(q) {
    try { localStorage.setItem(QUEUE_KEY, JSON.stringify(q)); } catch (e) { /* */ }
  }
  function enqueue(ev) { var q = loadQueue(); q.push(ev); saveQueue(q.slice(-300)); }

  window.CoachApi = {
    installCapture: installCapture,
    setCurrentLab: function (key) { currentKey = key; },
    onTurn: function (cb) { onTurn = cb; },
    transcript: function (key) { return transcriptFor(key); },
    clearTranscript: function (key) { transcripts[key] = []; },

    config: function () { return get("/config"); },
    quizQuestions: function (key) { return get("/quiz/questions?lab_key=" + encodeURIComponent(key)); },
    quizScore: function (key, answers, lang) { return post("/quiz/score", { lab_key: key, answers: answers, lang: lang }); },
    hint: function (key, level, lang, transcript) {
      return post("/hint", { lab_key: key, level: level, lang: lang, transcript: transcript });
    },
    judge: function (key, transcript) { return post("/judge", { lab_key: key, transcript: transcript }); },
    walkthrough: function (key, transcript, lang) {
      return post("/walkthrough", { lab_key: key, transcript: transcript, lang: lang });
    },

    sendEvent: function (type, key, data) {
      var ev = {
        event_type: type, challenge_key: key, data: data || {},
        student_token: window.CoachState.token(),
        client_timestamp: new Date().toISOString()
      };
      return post("/event", ev).then(function (res) {
        if (!res.body || !res.body.ok) enqueue(ev);
        return res.body;
      }).catch(function () { enqueue(ev); return { ok: false, queued: true }; });
    },
    // Reliable best-effort event for page unload (session_end). A normal
    // fetch is killed when the tab closes; sendBeacon survives. Falls back
    // to a keepalive fetch where Beacon is unavailable.
    sendBeacon: function (type, key, data) {
      var ev = {
        event_type: type, challenge_key: key, data: data || {},
        student_token: window.CoachState.token(),
        client_timestamp: new Date().toISOString()
      };
      var url = BASE + "/event";
      try {
        if (navigator && navigator.sendBeacon) {
          var blob = new Blob([JSON.stringify(ev)], { type: "application/json" });
          if (navigator.sendBeacon(url, blob)) return true;
        }
      } catch (e) { /* fall through */ }
      try {
        origFetch(url, {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify(ev), keepalive: true
        }).catch(function () { enqueue(ev); });
      } catch (e) { enqueue(ev); }
      return false;
    },
    // Absolute URL of a signed lab proof (markdown download). The dashboard
    // signs it; cohort is server-side. Returns a string to open/download.
    proofUrl: function (key, lang) {
      return BASE + "/proof?lab_key=" + encodeURIComponent(key)
        + "&student_token=" + encodeURIComponent(window.CoachState.token())
        + "&student_name=" + encodeURIComponent(window.CoachState.identity())
        + "&lang=" + encodeURIComponent(lang || "fr");
    },

    flushQueue: function () {
      var q = loadQueue();
      if (!q.length) return;
      saveQueue([]);
      q.forEach(function (ev) {
        post("/event", ev).then(function (res) { if (!res.body || !res.body.ok) enqueue(ev); })
          .catch(function () { enqueue(ev); });
      });
    }
  };
})();
