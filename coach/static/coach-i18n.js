/*
 * JuiceLab Coach for PwnzzAI — i18n catalogue (FR/EN).
 * Exposed as window.CoachI18n. Loaded before the other coach modules.
 */
(function () {
  "use strict";
  if (window.CoachI18n) return;

  var CAT = {
    fr: {
      title: "Coach JuiceLab",
      no_lab: "Aucun lab detecte sur cette page.",
      tab_briefing: "Briefing",
      tab_hints: "Indices",
      tab_journal: "Journal",
      tab_quiz: "Quiz",
      tab_progress: "Progression",
      mission: "Mission",
      concepts: "Concepts",
      goal: "Objectif",
      captured: "Conversation capturee",
      turns: "echange(s)",
      view: "Voir la conversation",
      reset_conv: "Effacer la conversation",
      empty: "Discute d'abord avec l'assistant du lab.",
      you: "Toi",
      bot: "Assistant",
      score: "Score",
      score_lab: "Score du lab",
      hint_reveal: "Reveler l'indice",
      hint_level: "Niveau",
      hint_locked: "Revele d'abord le niveau precedent.",
      hint_cost: "cout",
      hinting: "Generation de l'indice...",
      hints_consumed: "indices reveles",
      judge: "Verifier ma reussite",
      judging: "Evaluation en cours...",
      solved: "Reussi",
      partial: "Partiel",
      notyet: "Pas encore reussi",
      journal_before: "Avant : ton hypothese",
      journal_after: "Apres : ce que tu as compris",
      journal_before_ph: "Qu'est-ce que ce lab t'evoque ? Quelle hypothese sur la faille ? Ton plan en 2-4 phrases.",
      journal_after_ph: "Qu'as-tu compris de la faille ? Comment la detecter plus vite ? Quelle prevention en production ? (50 mots min)",
      save: "Enregistrer",
      saved: "Enregistre",
      words: "mots",
      quiz_submit: "Valider le quiz",
      quiz_score: "Score quiz",
      quiz_redo: "Recommencer",
      quiz_correct: "Bonne reponse",
      quiz_wrong: "Mauvaise reponse",
      quiz_pick: "Choisis une reponse a chaque question.",
      quiz_text_ph: "Reponds en une phrase (cite les notions cles).",
      progress_title: "Ta progression",
      progress_none: "Aucun lab commence.",
      badges: "Badges",
      badge_locked: "Verrouille",
      dashboard_off: "Dashboard prof non configure (mode local).",
      cohort: "Cohorte",
      unavailable: "Service coach indisponible (Ollama ?).",
      total_score: "Score moyen",
      labs_solved: "labs reussis",
      proof_download: "Telecharger la preuve",
      proof_preparing: "Preparation...",
      proof_error: "Preuve indisponible",
      identified_as: "Identifie comme",
      identity_prompt: "Ton identifiant (pour le suivi prof)",
      identity_ph: "ex. ton login PwnzzAI ou ton email",
      walkthrough_show: "Voir le corrige",
      walkthrough_title: "Corrige",
      walkthrough_loading: "Generation du corrige...",
      walkthrough_gate: "Resous d'abord le lab pour debloquer le corrige."
    },
    en: {
      title: "JuiceLab Coach",
      no_lab: "No lab detected on this page.",
      tab_briefing: "Briefing",
      tab_hints: "Hints",
      tab_journal: "Journal",
      tab_quiz: "Quiz",
      tab_progress: "Progress",
      mission: "Mission",
      concepts: "Concepts",
      goal: "Goal",
      captured: "Captured conversation",
      turns: "turn(s)",
      view: "View conversation",
      reset_conv: "Clear conversation",
      empty: "Talk to the lab assistant first.",
      you: "You",
      bot: "Assistant",
      score: "Score",
      score_lab: "Lab score",
      hint_reveal: "Reveal hint",
      hint_level: "Level",
      hint_locked: "Reveal the previous level first.",
      hint_cost: "cost",
      hinting: "Generating hint...",
      hints_consumed: "hints revealed",
      judge: "Check my success",
      judging: "Grading...",
      solved: "Solved",
      partial: "Partial",
      notyet: "Not solved yet",
      journal_before: "Before: your hypothesis",
      journal_after: "After: what you understood",
      journal_before_ph: "What does this lab evoke? Your hypothesis on the flaw? Your plan in 2-4 sentences.",
      journal_after_ph: "What did you understand about the flaw? How to detect it faster? What prevention in production? (50 words min)",
      save: "Save",
      saved: "Saved",
      words: "words",
      quiz_submit: "Submit quiz",
      quiz_score: "Quiz score",
      quiz_redo: "Retry",
      quiz_correct: "Correct",
      quiz_wrong: "Wrong",
      quiz_pick: "Pick an answer for each question.",
      quiz_text_ph: "Answer in one sentence (name the key notions).",
      progress_title: "Your progress",
      progress_none: "No lab started.",
      badges: "Badges",
      badge_locked: "Locked",
      dashboard_off: "Teacher dashboard not configured (local mode).",
      cohort: "Cohort",
      unavailable: "Coach service unavailable (Ollama?).",
      total_score: "Average score",
      labs_solved: "labs solved",
      proof_download: "Download proof",
      proof_preparing: "Preparing...",
      proof_error: "Proof unavailable",
      identified_as: "Identified as",
      identity_prompt: "Your identifier (for teacher tracking)",
      identity_ph: "e.g. your PwnzzAI login or email",
      walkthrough_show: "Show walkthrough",
      walkthrough_title: "Walkthrough",
      walkthrough_loading: "Generating walkthrough...",
      walkthrough_gate: "Solve the lab first to unlock the walkthrough."
    }
  };

  // Badge definitions (tiers adapted to PwnzzAI / OWASP LLM labs).
  var BADGES = [
    {
      id: "ai_red_teamer", tier: "bronze",
      label_fr: "AI Red Teamer", label_en: "AI Red Teamer",
      desc_fr: "Reussir 3 labs sans aucun indice.",
      desc_en: "Solve 3 labs with no hints."
    },
    {
      id: "persistent", tier: "silver",
      label_fr: "Perseverant", label_en: "Persistent",
      desc_fr: "Reussir 6 labs (indices autorises).",
      desc_en: "Solve 6 labs (hints allowed)."
    },
    {
      id: "reflective", tier: "gold",
      label_fr: "Reflexif", label_en: "Reflective",
      desc_fr: "Remplir 5 journaux 'apres' de plus de 50 mots.",
      desc_en: "Fill 5 'after' journals over 50 words."
    },
    {
      id: "apex", tier: "platinum",
      label_fr: "Apex Predator", label_en: "Apex Predator",
      desc_fr: "Reussir tous les labs sans aucun indice.",
      desc_en: "Solve every lab with no hints."
    }
  ];

  window.CoachI18n = {
    t: function (lang, key) {
      var c = CAT[lang] || CAT.fr;
      return c[key] || (CAT.fr[key] || key);
    },
    badges: BADGES
  };
})();
