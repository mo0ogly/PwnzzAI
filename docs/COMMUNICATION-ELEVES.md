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

---

**En résumé :** Ollama pour **gagner** les exos, Groq pour **comprendre** les
défenses. Le corrigé est dans `docs/CORRECTIONS-CHALLENGES-FR.md` après un `git pull`.
