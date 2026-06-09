# Parité JuiceLab — overlay élève

Ce document trace l'audit de parité entre l'overlay élève **JuiceLab** (sur
OWASP Juice Shop) et le **coach sidecar PwnzzAI**, puis le plan de
comblement des écarts. Objectif : un élève PwnzzAI dispose des mêmes
fonctions pédagogiques qu'un élève Juice Shop, et remonte les mêmes
événements au dashboard prof.

Contrainte permanente : **on ne modifie jamais le produit OWASP**. Le coach
est un sidecar (reverse proxy + injection navigateur). Il *lit* ce que
PwnzzAI expose au navigateur, il n'ajoute aucune route ni table à l'app
OWASP.

## Méthode

Inventaire exhaustif des capacités élève des deux côtés, puis diff.

- Côté Juice Shop : `overlay/frontend/src/app/juicelab-overlay/` (composants
  Angular + services), packs YAML, routes Express overlay.
- Côté PwnzzAI : `coach/app.py` (proxy FastAPI), `coach/llm_judge.py`,
  `coach/dashboard_client.py`, `coach/static/*.js`, packs JSON.

## Cœur déjà à parité

Le sidecar reprend fidèlement le modèle JuiceLab :

| Capacité | Juice Shop | PwnzzAI |
|---|---|---|
| Briefing (mission + concepts bilingues) | oui | oui |
| Hints gradués N1..N5, cohorte 5/10/20/35/50 | YAML | LLM Ollama adaptatif |
| Journal before/after + compteur de mots | oui | oui |
| Quiz QCM scoré serveur (clé jamais exposée) | oui | oui |
| Scoring déductif `max(50, 100 - Σ coûts)` | oui | oui |
| 4 badges (bronze/argent/or/platine) | oui | oui (renommés) |
| Sync dashboard `POST /api/sync` | oui | oui |
| File d'attente offline | oui (500) | oui (300) |
| i18n FR/EN | oui | oui |
| En-tête `X-Instance-Label` (multi-poste) | oui | oui |

Différence assumée par design : la détection de réussite passe par le
**LLM-as-judge** côté PwnzzAI (pas de socket « challenge solved » comme
Juice Shop). C'est voulu : les labs PwnzzAI n'ont pas de flag binaire.

## Écarts (le coach n'a pas / a plus faible)

| # | Écart | Priorité | Statut |
|---|---|---|---|
| 1 | Téléchargement de preuve signée HMAC | HAUT | fait |
| 2 | Émission de `session_end` | HAUT | fait |
| 3 | Identité élève robuste (non hardcodée) | HAUT | fait |
| 4 | Corrigé (walkthrough) débloqué après réussite | MOYEN | fait |
| 5 | Question quiz à texte libre (mots-clés) | MOYEN | fait |
| 6 | Endpoint admin (snapshot cohorte) | MOYEN | N/A (archi) |
| 7 | Enrôlement cohorte (join email + approbation) | HAUT | fait |

Hors périmètre (cosmétique ou inadapté au modèle PwnzzAI) : easter eggs
(salle des trophées, ROT13), vérification de flag CTF — les labs PwnzzAI
sont jugés par le LLM, il n'y a pas de flag.

Décisions sur les MOYEN :

- **#6 endpoint admin** : sans objet pour le sidecar. Le coach est
  *stateless* (l'état des indices vit dans le `localStorage` de l'élève,
  pas côté serveur), donc il n'a aucune donnée de cohorte à exposer. La
  vérité de cohorte est détenue par le dashboard JuiceLab, qui a déjà ses
  routes prof protégées par token.

## Design des 3 écarts HAUT

### 1. Téléchargement de preuve signée

Le dashboard JuiceLab expose déjà `GET /api/proof?student_token&cohort&key&name&category&difficulty&description`
qui renvoie un markdown horodaté **signé HMAC-SHA256** sous
`DASHBOARD_PROOF_SECRET`. La signature reste côté dashboard : le coach
n'embarque aucun secret.

- `dashboard_client.py` : nouvelle fonction `fetch_proof(...)` qui appelle
  ce endpoint avec le `cohort_id` serveur (autoritatif) et renvoie
  `(status, contenu, nom_de_fichier)`.
- `app.py` : nouvel endpoint `GET /__coach/proof?lab_key&student_token&student_name`
  qui relaie le markdown en pièce jointe (`Content-Disposition: attachment`)
  et renvoie une erreur propre si le dashboard est absent / 503 / 404.
- `coach.js` : bouton « Télécharger la preuve » dans l'onglet Progression,
  affiché pour chaque lab réussi.

La preuve n'existe que si le dashboard a reçu l'événement `challenge_solved`
(envoyé à la réussite du juge). Le `student_token` vient du navigateur ; le
`cohort_id` vient de l'environnement serveur — un élève ne peut pas usurper
une autre cohorte.

### 2. Émission de `session_end`

`session_end` est déjà autorisé par le dashboard et listé dans
`ALLOWED_EVENT_TYPES`, mais le client ne l'émet jamais : le temps de
session est faussé côté prof.

- `coach-api.js` : helper `sendBeacon(type, key, data)` via
  `navigator.sendBeacon` (un `fetch` au déchargement de page n'est pas
  fiable).
- `coach.js` : handler `pagehide` qui émet `session_end` une fois.

### 3. Identité élève robuste

PwnzzAI authentifie via **session Flask côté serveur** (`session['username']`,
cookie signé httpOnly). Ce cookie n'est pas lisible en JavaScript : on ne
peut donc pas parser un jeton côté navigateur comme l'overlay Juice Shop le
fait avec le JWT. La seule identité exposée au navigateur est le nom rendu
dans la barre de navigation :

```html
<span class="welcome-text">Welcome, {{ session.username }}!</span>
```

Conséquence : l'ancien `studentName()` cherchait en dur `alice|bob` (les
comptes de démo) — c'est à la fois un hardcoding et une identité fragile.

Nouveau résolveur d'identité, lecture seule sur le DOM OWASP :

1. `detectPwnzzUser()` lit `.welcome-text` et en extrait **n'importe quel**
   nom d'utilisateur (plus de liste en dur).
2. Le nom détecté est mis en cache dans `CoachState.identity()` pour
   survivre à une navigation vers une page sans barre de navigation.
3. À défaut (élève non connecté, page sans navbar), le coach propose un
   champ d'identité explicite, persisté localement.

Tous les `student_email: studentName()` deviennent
`CoachState.identity()`. Aucune ligne du code OWASP n'est touchée.

### 4. Corrigé (walkthrough) débloqué après réussite

JuiceLab sert un corrigé markdown statique, débloqué quand le challenge est
résolu (flag `solved` côté serveur Juice Shop). PwnzzAI n'a pas d'état
`solved` serveur, et écrire 13 corrigés statiques de qualité serait lourd.

Approche native PwnzzAI, cohérente avec la génération des indices :

- `llm_judge.py` : fonction `debrief(lab, transcript, lang)` qui génère le
  corrigé via Ollama en trois sections (cause racine, technique gagnante
  tirée du transcript de l'élève, défense en production), < 300 mots.
- `app.py` : `POST /__coach/walkthrough` qui **re-juge d'abord** le
  transcript et ne renvoie le corrigé que si le verdict est un succès. Le
  garde-fou est serveur-side : le drapeau `solved` du `localStorage` est
  falsifiable, donc on ne révèle jamais la solution sans succès démontré.
  C'est un garde plus fort que le flag de Juice Shop.
- `coach.js` : bouton « Voir le corrigé » dans l'onglet Progression pour un
  lab résolu. Le corrigé est mis en cache (`CoachState.setWalkthrough`) car
  le transcript en mémoire qui sert à le régénérer disparaît au rechargement.

### 5. Question quiz à texte libre

JuiceLab mélange QCM et questions à texte libre scorées par mots-clés
serveur. Le quiz PwnzzAI était QCM seul.

- `quiz.json` : nouveau type `type: "text"` (les QCM restent sans `type`,
  rétro-compatible) avec `expected_keywords_fr/en` + `min_keywords`. Une
  question texte-libre réelle par lab (13), bilingue : « cite deux défenses
  contre X » — ancrée sur les mitigations OWASP LLM Top 10.
- `app.py` : l'endpoint questions ne renvoie jamais les `expected_keywords`
  (strip serveur, comme `correct` pour les QCM). Le scoring normalise
  accents + casse (`_norm`) et valide si l'élève cite ≥ `min_keywords`
  notions distinctes.
- `coach.js` : rend un `textarea` pour les questions texte, un groupe de
  radios pour les QCM ; la validation exige une réponse non vide.

Le LLM-as-judge reste l'évaluation principale d'un lab ; ce type texte-libre
n'est qu'une variante de question de quiz, pour la parité de format.

### 7. Enrôlement de cohorte (join email + approbation prof)

Gap majeur découvert via un test live contre le dashboard réel : les élèves
PwnzzAI arrivaient bien dans le dashboard, mais **comme des tokens
anonymes** (`email` et `display_name` à `null`), car le coach n'avait pas le
flux d'enrôlement de JuiceLab. Le prof voyait la progression mais pas *qui*
était chaque token — inexploitable pour une cohorte réelle.

JuiceLab a une modale « rejoindre la cohorte » : l'élève saisit son email,
le dashboard crée une demande `pending`, le prof approuve, et le roster
affiche un nom. Le coach reprend ce flux (sidecar, proxy server-side, sans
CORS) :

- `dashboard_client.py` : `cohort_join(student_token, email)` →
  `POST /api/cohort/join` (cohort_id depuis l'env, autoritatif) ;
  `student_status(student_token)` → `GET /api/student/status`.
- `app.py` : `POST /__coach/join` et `GET /__coach/join/status` relaient le
  dashboard.
- `coach.js` : bloc d'enrôlement dans l'onglet Progression — saisie email →
  `pending` → poll toutes les 60 s → `validated`. L'email **devient
  l'identité canonique** (`student_email` des events + roster), au-dessus du
  username de la navbar.

Implication assumée (choix utilisateur : approbation prof) : tant que
l'élève n'est pas approuvé, le dashboard **bloque ses events** (gate
`/api/sync`). La file d'attente offline du coach les conserve et les rejoue
après approbation, donc aucune perte.

Pré-requis : le prof doit **créer la cohorte** dans le dashboard avant que
les élèves puissent la rejoindre (le join refuse une cohorte inconnue,
pour éviter le spam d'identifiants de cohorte depuis un endpoint public).

Boucle validée de bout en bout contre le dashboard réel : création cohorte
→ join (pending, email au roster) → event bloqué 403 → approbation →
events acceptés 201 → roster `validated` avec email + progression.

## Portes de vérification

- `python -m py_compile coach/app.py coach/dashboard_client.py`
- Parsing JSON des packs inchangé
- Règle 800 lignes par fichier (hook)
- Smoke : le coach démarre, l'onglet Progression affiche le bouton preuve
  pour un lab réussi, `session_end` part au déchargement, l'identité
  détectée s'affiche dans les événements.

## Topologie dashboard

Le dashboard prof est central et unique. PwnzzAI le consomme comme client
(`JUICELAB_DASHBOARD_URL`) ou le deploie via `scripts/deploy-dashboard.sh`
(sparse checkout pinne de la seule partie prof). Le code serveur n'est jamais
duplique dans ce repo. Detail cote juicelab : `docs/DASHBOARD-CENTRAL.md`.

## Parité scripts & docs (vs JuiceLab)

Au-delà de la parité *fonctionnelle* de l'overlay élève, le repo atteint
désormais la parité **outillage + documentation** avec la référence JuiceLab :
mêmes points d'entrée (un lanceur, un installeur élève, un déploieur prof),
mêmes paires de docs bilingues, et des guides Word scindés prof/élève.

| Artefact | JuiceLab (réf.) | PwnzzAI | Statut |
|---|---|---|---|
| Lanceur compose (sh) | oui | [`pwnzzai.sh`](../pwnzzai.sh) | fait |
| Lanceur compose (ps1) | oui | [`pwnzzai.ps1`](../pwnzzai.ps1) | fait |
| Installeur élève (sh) | oui | [`scripts/install-student.sh`](../scripts/install-student.sh) | fait |
| Installeur élève (ps1) | oui | [`scripts/install-student.ps1`](../scripts/install-student.ps1) | fait |
| Déploieur dashboard (sh) | oui | [`scripts/deploy-dashboard.sh`](../scripts/deploy-dashboard.sh) | fait |
| Déploieur dashboard (ps1) | oui | [`scripts/deploy-dashboard.ps1`](../scripts/deploy-dashboard.ps1) | fait |
| STUDENT-INSTALL FR | oui | [STUDENT-INSTALL-FR.md](./STUDENT-INSTALL-FR.md) | fait |
| STUDENT-INSTALL EN | oui | [STUDENT-INSTALL-EN.md](./STUDENT-INSTALL-EN.md) | fait |
| README FR | oui | [README_FR.md](../README_FR.md) | fait |
| README EN | oui | [README.md](../README.md) | fait |
| INSTALL FR | oui | [INSTALL_FR.md](../INSTALL_FR.md) | fait |
| INSTALL EN | oui | [INSTALL.md](../INSTALL.md) | fait |
| ARCHITECTURE FR | oui | [ARCHITECTURE.md](./ARCHITECTURE.md) | fait |
| ARCHITECTURE EN | oui | [ARCHITECTURE-EN.md](./ARCHITECTURE-EN.md) | fait |
| Guide Word élève (.docx) | oui | docs/GUIDE-INSTALL-ELEVE.docx | fait |
| Guide Word prof (.docx) | oui | docs/GUIDE-INSTALL-PROF.docx | fait |

Différences assumées :

- **Installeur élève sans dashboard** : `install-student.*` ne déploie jamais
  le serveur prof (même garde-fou que JuiceLab). Le déploiement dashboard est
  un script prof distinct, et le dashboard reste central/unique (cf.
  *Topologie dashboard* ci-dessus).
- **Guides scindés prof/élève** : le `.docx` combiné historique
  (`GUIDE-COACH-PWNZZAI.docx`) reste présent, mais les deux guides scindés
  (`GUIDE-INSTALL-ELEVE.docx` sans contenu prof, `GUIDE-INSTALL-PROF.docx`)
  sont désormais les supports d'install de référence, comme côté JuiceLab.
- **Régénération `.docx`** : `docs/build_install_guides.py` requiert
  `python3.11` + `python-docx` (le `python3` par défaut de la machine est 3.13
  sans `python-docx`) ; voir l'en-tête du script et la section Documentation
  des README.
