# 📣 PwnzzAI — Communication élèves : corrigé des challenges + option Groq

Message prêt à diffuser (chat / mail). Adapté FR.

---

## 1) Récupérer le corrigé

Le corrigé de tous les challenges est dans le dépôt. Mettez à jour votre copie :

```bash
cd PwnzzAI
git pull
```

Le corrigé est ici : **`docs/CORRECTIONS-CHALLENGES-FR.md`**
(ouvrez-le dans VS Code ou sur GitHub). Pour chaque lab : la page à ouvrir, le
prompt exact à coller, et la preuve de réussite. Tout a été **testé en vrai**.

## 2) Tirer les modèles Ollama (obligatoire la 1re fois)

```bash
./pwnzzai.sh models
```

**Pourquoi :** les labs tournent sur des modèles locaux (`llama3.2:1b` pour la
cible, `llama3.2:3b` pour le coach et le lab *agentic-SQL*). Sans ce pull, la page
affiche « Ollama indisponible » et rien ne répond.

➡️ **Faites vos exercices sur Ollama** : le petit modèle ne résiste à aucune
attaque, donc les exploits passent facilement. C'est la cible recommandée pour
**réussir** les challenges.

## 3) (Optionnel) Activer Groq — la cible « cloud »

Groq sert à voir un **vrai** modèle qui, lui, **résiste** à certaines attaques
(plugin SQLi, QR) : utile pour comprendre *pourquoi une défense tient*. Pas
nécessaire pour valider la majorité des labs.

**a.** Créez **votre propre** clé gratuite sur <https://console.groq.com> →
*API Keys* (elle commence par `gsk_`).
⚠️ **N'utilisez jamais la clé d'un autre / du prof** — chacun la sienne, elle reste privée.

**b.** Ouvrez le fichier **`.env`** à la racine du dépôt et mettez ces 3 lignes :

```bash
MODEL_PROVIDER=openai
LITELLM_MODEL=groq/llama-3.3-70b-versatile
GROQ_API_KEY=gsk_VOTRE_CLE_ICI
```

*(On utilise `llama-3.3-70b`, pas `gpt-oss-20b` : ce dernier renvoyait des réponses vides.)*
Le fichier `.env` est **ignoré par git** → votre clé ne part jamais en ligne.

**c. Redémarrez la stack** — étape indispensable :

```bash
./pwnzzai.sh restart
```

**Pourquoi redémarrer :** Docker ne lit le `.env` qu'au (re)démarrage des
conteneurs. Tant que vous n'avez pas relancé, l'ancienne config reste active et
votre clé n'est pas prise en compte.

## 4) Changer un paramètre APRÈS l'installation

Tous les réglages sont dans le fichier **`.env`** à la racine du dépôt. La règle
est toujours la même :

> **Éditer `.env` → enregistrer → redémarrer la stack.**
> Une modif de `.env` n'est **jamais** prise en compte « à chaud » : Docker ne
> relit ce fichier qu'au (re)démarrage des conteneurs.

```bash
# 1. éditer le fichier
nano .env            # ou VS Code

# 2. redémarrer pour appliquer
./pwnzzai.sh restart
```

**Exemples de réglages courants :**

| Je veux… | Ligne dans `.env` | Étape en plus |
|---|---|---|
| Changer le modèle des labs | `OLLAMA_MODEL=llama3.2:3b` | tirer le modèle : `./pwnzzai.sh models` **avant** le restart |
| Changer le modèle du coach | `COACH_JUDGE_MODEL=llama3.2:3b` | idem : `./pwnzzai.sh models` |
| Passer en cloud Groq | `MODEL_PROVIDER=openai` + `LITELLM_MODEL=groq/llama-3.3-70b-versatile` + `GROQ_API_KEY=gsk_…` | clé perso |
| Revenir en tout-local | `MODEL_PROVIDER=ollama` | — |

⚠️ **Si vous changez `OLLAMA_MODEL` pour un modèle non encore téléchargé**, lancez
`./pwnzzai.sh models` **avant** `restart`, sinon la page affichera « modèle
indisponible » (Docker ne télécharge pas tout seul).

## 5) Reprendre le lendemain

Pas besoin de tout réinstaller. Au début de séance :

```bash
cd PwnzzAI
git pull              # récupère les dernières corrections / docs
./pwnzzai.sh up       # relance la stack (ou ./pwnzzai.sh restart si déjà lancée)
./pwnzzai.sh status   # vérifie que les 3 services tournent
```

Les modèles déjà tirés la veille **restent** (pas besoin de re-`models`, sauf si
vous avez changé de modèle dans `.env`).

---

**En résumé :** Ollama pour **gagner** les exos, Groq pour **comprendre** les
défenses. Toute modif de `.env` → **`./pwnzzai.sh restart`**. Le corrigé est dans
`docs/CORRECTIONS-CHALLENGES-FR.md` après un `git pull`.
