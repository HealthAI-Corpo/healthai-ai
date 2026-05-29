# API IA

## ⚠️ Points critiques à lire avant de commencer

### URLs : préfixe commun non encore ajouté

**Aujourd'hui**, les deux services sont sur des ports séparés, sans préfixe commun :

| Service | Port | Exemple d'URL actuelle                      |
| ------- | ---- | ------------------------------------------- |
| Workout | 8002 | `http://localhost:8002/ai/generate-session` |
| Vision  | 8001 | `http://localhost:8001/analyze`             |

**Prévu** : un routeur commun ajoutera un préfixe (`/workout/...`, `/vision/...`) sur une URL de base unique. **Les URLs vont donc changer.** Les noms d'endpoints et les structures JSON, eux, resteront stables.

> Recommandation : centraliser toutes les URLs dans un fichier de config front (`api.config.ts` ou équivalent) pour faciliter la bascule.

### Pattern asynchrone (routes LLM)

Tous les appels IA (Ollama) sont **non bloquants**, le modèle peut mettre du temps à repondre donc :

**Principe :**

1. Appel POST → réponse immédiate `202` avec un `job_id`
2. Polling sur `GET /ai/jobs/{job_id}` jusqu'à `status = "completed"` ou `"failed"`
3. Le résultat est dans le champ `result` du job

```
POST /ai/generate-session  →  202 { job_id: "abc123" }
GET  /ai/jobs/abc123       →  { status: "processing", result: null }
GET  /ai/jobs/abc123       →  { status: "completed", result: { ... } }
```

---

## Service WORKOUT — port 8002

### Endpoints calorie (ML, synchrones)

Ces routes répondent immédiatement — pas de polling.

---

#### **POST /calorie-estimation/predict**

Estimation de calories à partir de données fournies manuellement. Utile pour une simulation ("si je faisais 30 min de cardio..."). **Aucune écriture en base.**

**Entrée** — tous les champs obligatoires :

```json
{
    "imc": 23.5,
    "age": 30,
    "sexe": "M",
    "bpm_max": 180,
    "bpm_moyen": 140,
    "bpm_repos": 60,
    "duree_seance_minutes": 45,
    "type_sport": "Cardio",
    "pourcentage_gras": 18.0,
    "consommation_eau_ml": 500,
    "niveau_experience": 3
}
```

Contraintes :

- `sexe` ∈ `{"M", "F", "m", "f"}` (casse indifférente)
- `niveau_experience` ∈ `[0, 5]`
- `type_sport` : valeurs orientantes — `"Cardio"`, `"HIIT"`, `"Strength"`, `"Yoga"` (champ libre, le modèle utilise ces valeurs comme référence)
- `bpm_repos < bpm_moyen < bpm_max` est une cohérence **sémantique recommandée** mais **non validée par l'API** (aucune erreur 422 si l'ordre est incorrect)

**Sortie** :

```json
{
    "prediction": 412.5,
    "model_version": "1.0.0",
    "features_used": 11,
    "model_name": "CaloriesIA_1_0_0"
}
```

---

#### **POST /calorie-estimation/predict-with-defaults**

Même chose, mais tous les champs sont **optionnels**. Les champs absents ou `null` sont imputés par la moyenne du dataset.

**Entrée** (exemple partiel) :

```json
{
    "imc": 23.5,
    "sexe": "M",
    "bpm_max": 180
}
```

**Sortie** :

```json
{
    "prediction": 412.5,
    "model_version": "1.0.0",
    "features_used": 11,
    "model_name": "CaloriesIA_1_0_0",
    "imputed_features": {
        "age": 35.2,
        "bpm_moyen": 125.5
    },
    "original_values": {
        "imc": 23.5,
        "sexe": "M",
        "bpm_max": 180
    }
}
```

---

#### **POST /calorie-estimation/predict-from-session**

Prédit les calories d'une séance **déjà en base** et met à jour `log_seance.calorie_brulee`.  
Toutes les features sont lues automatiquement en base — le front n'envoie que l'id de séance et de l'utilisateur.

**Auth actuelle** : query param `?user_id=<int>`

**Entrée** :

```json
{
    "id_seance": 123
}
```

**Sortie** :

```json
{
    "id_seance": 123,
    "calories_estimees": 412.5,
    "calorie_brulee_avant": null,
    "champs_utilises": {
        "fournis": { "bpm_max": 180 },
        "imputes": { "age": 35.2 }
    }
}
```

Erreurs possibles : `404` (séance introuvable), `403` (séance n'appartient pas à l'utilisateur)

---

---

### Endpoints LLM — asynchrones (polling)

**Header requis sur toutes ces routes** : `X-User-Id: <int>`  
**Réponse immédiate** : `202 { "job_id": "...", "status": "processing" }`  
**Résultat** : via `GET /ai/jobs/{job_id}`

---

#### **POST /ai/generate-session**

Génère une séance d'entraînement personnalisée à partir du profil et de l'historique de l'utilisateur (lus en base).

**Query param** : `sauvegarder` (bool, défaut `false`) — si `true`, la séance est insérée dans `log_seance` avec statut `"proposee"`

**Entrée** — tous les champs optionnels :

```json
{
    "duree_souhaitee_minutes": 45,
    "equipement_disponible": ["Haltères", "Tapis"],
    "focus_musculaire": "Jambes"
}
```

**Résultat dans le job** (`result`) :

```json
{
    "id_seance_log": 123,
    "log_date": "2026-05-25T10:30:00Z",
    "statut": "proposee",
    "type_seance": "Musculation",
    "titre_seance": "Jambes intensives",
    "duree_minutes": 45,
    "difficulte": "Intermédiaire",
    "objectif": "Hypertrophie",
    "conseils_generaux": "...",
    "exercices": [
        {
            "nom": "Squat",
            "type": "Compound",
            "series": 4,
            "repetitions": 10,
            "duree_secondes": null,
            "repos_secondes": 90,
            "muscles_cibles": "Quadriceps, fessiers"
        }
    ]
}
```

> `id_seance_log`, `log_date`, `statut` ne sont présents que si `sauvegarder=true`.

---

#### **POST /ai/evaluate-sessions**

Évalue des séances **déjà enregistrées**, identifiées par leurs ids. Aucune écriture Postgres.

**Entrée** :

```json
{
    "ids_seances": [123, 124, 125]
}
```

Limite : 20 ids max

**Résultat dans le job** :

```json
{
    "avis_global": "Très bonne progression cette semaine.",
    "note_globale": 4,
    "avis_par_seance": [
        {
            "index": 0,
            "points_positifs": ["Bonne intensité", "Repos adéquat"],
            "points_amelioration": ["Plus de variété"],
            "suggestion": "Ajouter du cardio léger en fin de séance."
        }
    ]
}
```

**Stabilité** : ✅ Stable

---

#### **GET /ai/evaluate-my-recent-sessions**

Évalue automatiquement les dernières séances de l'utilisateur (7 dernières `terminee` + jusqu'à 5 `prevue`). Aucune entrée requise (hors header X-User-Id: <int>). Aucune écriture Postgres.

**Résultat dans le job** : identique à `evaluate-sessions` ci-dessus.

---

#### `POST /ai/explain-exercises`

Explique une liste d'exercices (technique, erreurs courantes, variantes, sécurité). Aucune écriture Postgres.

**Entrée** — `nom` obligatoire, tous les autres champs sont optionnels mais **enrichissent la réponse LLM** (technique adaptée au contexte, conseils de progression, etc.) :

```json
{
    "exercices": [
        {
            "nom": "Développé couché"
        },
        {
            "nom": "Squat",
            "type": "Compound",
            "series": 4,
            "repetitions": 10,
            "duree_secondes": null,
            "repos_secondes": 90,
            "muscles_cibles": "Quadriceps, fessiers"
        }
    ]
}
```

Schéma complet d'un exercice en entrée :

| Champ             | Type          | Requis | Description                              |
| ----------------- | ------------- | ------ | ---------------------------------------- |
| `nom`             | string (≤200) | ✅     | Nom de l'exercice                        |
| `type`            | string (≤50)  | —      | Ex. `"Compound"`, `"Isolation"`, `"Cardio"` |
| `series`          | int           | —      | Nombre de séries prévues                 |
| `repetitions`     | int           | —      | Nombre de répétitions par série          |
| `duree_secondes`  | int           | —      | Durée de l'effort si exercice chronométré |
| `repos_secondes`  | int           | —      | Temps de repos entre séries              |
| `muscles_cibles`  | string (≤200) | —      | Muscles concernés (libre)                |

Limite : 20 exercices max

**Résultat dans le job** :

```json
{
    "explications": [
        {
            "nom": "Développé couché",
            "description": "Exercice de base pour le haut du corps.",
            "muscles_cibles": "Poitrine, triceps, épaules",
            "technique": "Allongé sur le banc, barre à la largeur des épaules...",
            "erreurs_courantes": ["Dos cambré excessif", "Manque de contrôle à la descente"],
            "variantes": ["Incliné", "Haltères", "Machine"],
            "conseils_securite": "Toujours avoir un pareur pour les charges lourdes."
        }
    ]
}
```

---

#### **POST /recommendations/workout**

Programme d'entraînement personnalisé via moteur hybride (classifieur sklearn + LLM Ollama).  
Retourne un `job_id` — résultat via `GET /ai/jobs/{job_id}`.

> ⚠️ Requiert que le modèle `RecoIA_1_0_0` soit entraîné. Si absent → `503` immédiat.

**Entrée** : aucun body. Seul le header `X-User-Id` est requis.

**Résultat dans le job** :

```json
{
    "status": "success",
    "predictions_classifier": {
        "type_seance": "Musculation",
        "intensite": "Modérée",
        "muscles_cibles": ["Dos", "Biceps"],
        "confidence": {
            "Musculation": 0.82,
            "Cardio": 0.12,
            "HIIT": 0.06
        }
    },
    "seance": {
        "titre": "Séance Dos/Biceps",
        "duree_minutes": 50,
        "intensite": "modérée",
        "exercices": [
            {
                "nom": "Tractions",
                "muscles_cibles": ["Dos"],
                "series": 4,
                "repetitions": "8-10",
                "repos_secondes": 90,
                "conseil": "Contrôler la descente."
            }
        ]
    }
}
```

---

#### **GET /ai/jobs/{job_id}**

Endpoint de polling commun à **toutes** les routes asynchrones workout (LLM + recommandations).

**Pas de header requis.**

**Sortie** :

```json
{
    "job_id": "665f1234abc...",
    "type": "generate-session",
    "status": "completed",
    "result": {
        /* sortie de l'endpoint d'origine */
    },
    "error": null,
    "error_code": null,
    "created_at": "2026-05-25T10:30:00Z",
    "updated_at": "2026-05-25T10:30:07Z"
}
```

| `status`     | Signification                                         |
| ------------ | ----------------------------------------------------- |
| `processing` | En cours — `result` est `null`, re-poller dans 2-3 s  |
| `completed`  | `result` contient la réponse finale                   |
| `failed`     | `error` et `error_code` renseignés (404, 403, 502...) |

---

## Codes d'erreur communs

| Code  | Contexte              | Signification                                                       |
| ----- | --------------------- | ------------------------------------------------------------------- |
| `202` | Routes LLM            | Job créé et lancé en tâche de fond                                  |
| `400` | Vision validate       | Suggestion invalide ou introuvable                                  |
| `403` | Workout (dans le job) | Séance n'appartient pas à l'utilisateur                             |
| `404` | Workout (dans le job) | Séance ou utilisateur introuvable                                   |
| `422` | Tous                  | Validation Pydantic échoue (champ manquant, valeur hors contrainte) |
| `500` | Vision                | Erreur interne lors de l'analyse image                              |
| `502` | Workout (dans le job) | LLM renvoie une structure inattendue                                |
| `503` | Workout (synchrone)   | MongoDB indisponible ou modèle ML non chargé                        |

---

## Flux typiques pour le front

### Générer une séance

```
1. POST /ai/generate-session (body optionnel) → 202 { job_id }
2. Polling GET /ai/jobs/{job_id} (toutes les 3s)
   → status: "completed" → afficher la séance dans result
3. Si l'utilisateur accepte et veut sauvegarder :
   - Rappeler POST /ai/generate-session avec ?sauvegarder=true
   - OU : la sauvegarde directe via l'API NestJS (gateway) selon l'architecture retenue
```

### Estimation calories séance existante

```
1. POST /calorie-estimation/predict-from-session { id_seance: 123 }
   → réponse immédiate { calories_estimees: 412.5 }
```
