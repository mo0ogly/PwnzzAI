# Coach JuiceLab pour PwnzzAI — Guide (FR)

> Version anglaise : [GUIDE-EN.md](./GUIDE-EN.md) · Détails techniques : [ARCHITECTURE.md](./ARCHITECTURE.md)

Le **Coach JuiceLab** transforme [OWASP PwnzzAI](https://github.com/OWASP/PwnzzAI)
— la « pizza shop » volontairement vulnérable pour apprendre la sécurité des
LLM — en un TD guidé et suivi à distance, **sans modifier une seule ligne du
produit OWASP**.

Il ajoute quatre choses à PwnzzAI :

1. **Un juge automatique** (LLM-as-judge) qui lit la conversation de l'élève
   avec l'assistant vulnérable et décide si l'objectif du lab est réellement
   atteint, avec un score de 0 à 100.
2. **Des indices adaptatifs** générés par le modèle local en fonction des
   tentatives ratées de l'élève, gradués sur 3 niveaux, en FR ou EN.
3. **La capture de la conversation d'attaque** dans le navigateur, pour que
   l'élève (et le prof) voient le déroulé complet de l'exploitation.
4. **La remontée vers le dashboard prof JuiceLab** : un TD PwnzzAI apparaît
   dans la même matrice de cohorte que Juice Shop.

---

## 1. Ce qui s'installe

Un seul conteneur supplémentaire (`pwnzzai-coach`) se place **devant**
PwnzzAI. Il n'y a rien à changer dans l'image OWASP.

| Conteneur | Port | Rôle |
|---|---|---|
| `pwnzzai-coach` | **8095** | Entrée élève : proxy + panneau coach |
| `pwnzzai-shop` | 8090 | PwnzzAI brut OWASP (intact, debug) |
| `ollama` | interne | Modèle des labs + modèle du juge/indices |

L'élève utilise **uniquement** `http://localhost:8095`. Le port 8090 reste
disponible pour déboguer PwnzzAI sans le coach.

---

## 2. Prérequis

| Outil | Détail |
|---|---|
| Docker + Docker Compose v2 | déjà requis par PwnzzAI |
| Un modèle Ollama tiré | pour les labs **et** pour le juge/indices |

Sur arm64 (Apple Silicon, Snapdragon X1E), l'image GHCR de PwnzzAI n'est pas
publiée : on construit en local (voir le README PwnzzAI). Le coach, lui, est
une petite image Python pure et se construit partout.

---

## 3. Installation

La stack est autonome (PwnzzAI est cloné au build à un commit pinné, rien à
installer à côté). Depuis la racine de ce dépôt :

```bash
cp .env.example .env    # régler cohorte + dashboard
docker compose up -d --build
```

Puis tirer un modèle si ce n'est pas déjà fait (page *Basics* de PwnzzAI, ou
en ligne de commande) :

```bash
docker exec ollama ollama pull llama3.2:1b   # modèle des labs
docker exec ollama ollama pull llama3.2:3b   # modèle du juge (recommandé)
```

Vérifier que tout répond :

```bash
curl -s http://localhost:8095/__coach/health
# {"ok":true,"ollama":true,"dashboard_configured":true}
```

- `ollama:true` → un modèle de juge est disponible.
- `dashboard_configured:true` → la remontée vers le dashboard prof est activée.

---

## 4. Connexion au dashboard prof (la cohorte)

Tout se règle dans le fichier `.env` de PwnzzAI :

| Variable | Rôle | Exemple |
|---|---|---|
| `JUICELAB_DASHBOARD_URL` | URL du dashboard **vue depuis le conteneur** | `http://host.docker.internal:5000` |
| `JUICELAB_COHORT_ID` | identifiant de la promo | `M2-IA-2026` |
| `JUICELAB_INSTANCE_LABEL` | nom du poste élève dans la matrice prof | `pwnzzai-poste-01` |
| `COACH_JUDGE_MODEL` | modèle Ollama du juge/indices | `llama3.2:3b` |

Remarques importantes :

- **Dashboard sur la même machine que PwnzzAI** → utiliser
  `http://host.docker.internal:5000` (et non `127.0.0.1`, qui pointerait sur
  le conteneur lui-même).
- **Dashboard distant** (le prof héberge le serveur) → mettre son IP ou son
  domaine : `http://<ip-prof>:5000`.
- **Laisser `JUICELAB_DASHBOARD_URL` vide** → mode local : le coach marche
  normalement, mais ne remonte rien. Pratique pour tester seul.
- Le dashboard **enregistre l'élève automatiquement** au premier événement.
  Aucune inscription préalable n'est nécessaire.

Après modification du `.env`, recréer le conteneur coach :

```bash
docker compose up -d pwnzzai-coach
```

---

## 5. Côté élève : comment ça s'utilise

1. Ouvrir `http://localhost:8095` et naviguer vers un lab (ex. *Direct Prompt
   Injection*).
2. Un bouton rond violet **« JL »** apparaît en bas à droite. Cliquer dessus
   ouvre le **panneau coach**.
3. Le panneau affiche :
   - le **nom du lab** et sa **catégorie OWASP** (ex. LLM01) ;
   - l'**objectif** de l'exploitation, en français ou anglais (bouton FR/EN) ;
   - un compteur **« conversation capturée »** qui augmente à chaque échange
     avec l'assistant vulnérable ;
   - les boutons **Indice**, **Vérifier ma réussite**, **Voir la
     conversation** ;
   - un **journal** où l'élève explique sa démarche.
4. L'élève attaque l'assistant comme d'habitude (le coach n'interfère pas).
5. Bloqué ? Le bouton **Indice** donne un conseil adapté à ses tentatives
   ratées (3 niveaux, du simple nudge à l'exemple quasi complet).
6. Quand il pense avoir réussi, **Vérifier ma réussite** soumet la
   conversation au juge, qui répond *Réussi / Partiel / Pas encore* + un score
   + une justification.
7. **Astuce prof** : un lien terminé par `#coach` (ex.
   `http://localhost:8095/indirect-prompt-injection#coach`) ouvre le panneau
   automatiquement — pratique à distribuer aux élèves.

Les données de l'élève (jeton, conversations, journaux, niveau d'indices)
sont stockées dans le navigateur (`localStorage`, clé `pwnzzai_coach_v1`) et
survivent aux rechargements.

---

## 6. Côté prof : ce qui remonte

Le coach envoie au dashboard les événements suivants, via le contrat public
`POST /api/sync` (le même que Juice Shop) :

| Événement | Déclencheur | Données utiles |
|---|---|---|
| `session_start` | ouverture d'une page lab | chemin, identité élève si détectée |
| `hint_revealed` | clic sur **Indice** | niveau d'indice |
| `challenge_solved` | juge → **Réussi** | score, verdict, justification |
| `journal_filled` | **Enregistrer** le journal | longueur, texte |

Le prof retrouve donc, pour chaque poste de la cohorte : quels labs sont
résolus, combien d'indices ont été consommés, et le contenu des journaux —
exactement comme pour un TD Juice Shop.

---

## 7. Choisir le modèle du juge

Le juge est le cœur de la valeur pédagogique. Sa fiabilité dépend
directement de la taille du modèle :

| Modèle | Verdict | Recommandation |
|---|---|---|
| `llama3.2:1b` | **non fiable** (verdicts incohérents) | à éviter pour le juge |
| `llama3.2:3b` | fiable sur les cas nets | **minimum conseillé** |
| `mistral:7b` / `llama3.1:8b` | fiable sur les cas subtils | idéal si la machine suit |

Le modèle du juge est indépendant de celui des labs : on peut faire tourner
les labs en 1b (rapide) et le juge en 3b (fiable) sur la même machine. Réglé
par `COACH_JUDGE_MODEL`.

---

## 8. Dépannage

| Symptôme | Cause probable | Solution |
|---|---|---|
| `« Service coach indisponible »` sur Indice/Vérifier | aucun modèle de juge tiré | `docker exec ollama ollama pull llama3.2:3b` |
| `health` renvoie `ollama:false` | idem | tirer un modèle, vérifier `COACH_JUDGE_MODEL` |
| Verdicts incohérents | modèle de juge trop petit (1b) | passer à 3b ou plus |
| `« Dashboard prof non configuré »` | `JUICELAB_DASHBOARD_URL` vide | renseigner l'URL, recréer le conteneur |
| Rien ne remonte alors que l'URL est mise | dashboard injoignable depuis le conteneur | utiliser `host.docker.internal`, vérifier le port/pare-feu |
| Le bouton « JL » n'apparaît pas | page sans `</head>`/`</body>` | rare ; vérifier la console navigateur |
| Port 8095 déjà pris | autre service | changer le mapping dans `docker-compose.coach.yml` |

Erreurs de DNS Ollama pendant un `pull` (`server misbehaving`) : c'est le
resolver interne du conteneur qui décroche. `docker restart ollama` puis
relancer le `pull`.

---

## 9. Pourquoi ça résiste aux évolutions d'OWASP

Le proxy ne connaît **aucune route interne** de PwnzzAI : il transmet tout et
n'injecte qu'une balise `<script>`. La capture de conversation est générique
(n'importe quel POST `fetch`/XHR portant un champ texte). Si OWASP renomme une
route ou change le style d'une page, le coach continue de fonctionner ; seul
`labs.json` peut nécessiter une mise à jour de chemin pour la **détection** du
lab. Voir [ARCHITECTURE.md](./ARCHITECTURE.md).
