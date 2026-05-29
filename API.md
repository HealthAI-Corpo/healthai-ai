# HealthAI — API IA

Contrat d'API du périmètre IA (services `healthai-workout` et `healthai-vision`)

---

## 1. Vue d'ensemble

| Service            | Rôle                                                           | Routes exposées                                        |
| ------------------ | -------------------------------------------------------------- | ------------------------------------------------------ |
| `healthai-api`     | Gateway (auth Zitadel + reverse proxy)                         | `/vision/*` + `/workout/*`                             |
| `healthai-workout` | Calories ML + génération/évaluation/explication séances + reco | `/calorie-estimation/*`, `/ai/*`, `/recommendations/*` |
| `healthai-vision`  | Analyse photo repas + conseils nutritionnels + recettes        | `/analyze`, `/nutrition/*`                             |

**Une seule base URL pour le front** :

- Dev local : `http://localhost:8000`
- Prod (via `healthai-infra`) : `http://localhost:8003` (ou domaine public)

Toutes les routes du front passent par la gateway, qui ajoute le préfixe `/vision/` ou
`/workout/`. Ex : `POST /workout/ai/generate-session` → en interne `POST /ai/generate-session`
sur le service workout.

### Swagger

Chaque service expose son propre Swagger UI :

| URL                          | Description                             |
| ---------------------------- | --------------------------------------- |
| `http://localhost:8000/docs` | Gateway (vue agrégée — proxy routes)    |
| `http://localhost:8001/docs` | Vision (en dev seulement, pas en prod)  |
| `http://localhost:8002/docs` | Workout (en dev seulement, pas en prod) |

> En prod, **seul le Swagger de la gateway est accessible** (les autres services ne sont
> pas exposés). Pour explorer le contrat complet on consulte les services localement
> en dev, ou directement ce document.

---

## 2. Authentification

### Production / Zitadel branché

Header `Authorization: Bearer <jwt>` sur toutes les routes proxifiées.

La gateway valide le JWT (signature JWKS, issuer, audience, expiration), résout
l'`id_utilisateur` Postgres depuis le claim `email`, puis injecte `X-User-Id`
côté interne. **Le client n'envoie jamais `X-User-Id`** — la gateway le strip
de toute manière.

### Dev local (mode `dev_stub`)

Aucun header requis. Toutes les requêtes sont attribuées à `DEV_STUB_USER_ID=1`.
Activé tant que `AUTH_MODE=dev_stub` dans `healthai-api/.env`.

---

## 3. Pattern asynchrone (LLM)

Les appels Ollama peuvent prendre 180 s (chargement modèle CPU). Toutes les routes IA
sont donc **non bloquantes** :

1. POST → réponse immédiate `202 { "job_id": "...", "status": "processing" }`
2. Polling sur `GET .../jobs/{job_id}` (ou `GET .../consumption/{id}` pour vision advice)
   toutes les 2-3 s jusqu'à `status="completed"` ou `"failed"`.
3. Le résultat est dans le champ `result` du job.

```
POST /workout/ai/generate-session   →  202 { job_id: "abc123" }
GET  /workout/ai/jobs/abc123        →  { status: "processing", result: null }
GET  /workout/ai/jobs/abc123        →  { status: "completed",  result: { ... } }
```

**Ownership** : un job (ou un document Mongo de vision) n'est lisible que par son
propriétaire. Une lecture par un autre utilisateur renvoie **404** identique à un id
inconnu (pas d'énumération possible).

---

## 4. Service Workout — via `/workout/...`

### 4.1 Estimation de calories (ML — synchrone)

#### `POST /workout/calorie-estimation/predict`

Estimation à partir des 11 features fournies manuellement. **Aucune écriture en base.**

**Entrée — tous champs obligatoires :**

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

- `sexe ∈ {"M", "F", "m", "f"}`
- `niveau_experience ∈ [0, 5]`
- `type_sport` : valeurs orientantes (`"Cardio"`, `"HIIT"`, `"Strength"`, `"Yoga"`)
- `bpm_repos < bpm_moyen < bpm_max` : cohérence sémantique recommandée (non validée)

**Sortie :**

```json
{
    "prediction": 412.5,
    "model_version": "1.0.0",
    "features_used": 11,
    "model_name": "CaloriesIA_1_0_0"
}
```

---

#### `POST /workout/calorie-estimation/predict-with-defaults`

Identique mais tous champs optionnels. Les champs absents ou `null` sont imputés
par la moyenne du dataset d'entraînement.

**Sortie additionnelle** :

```json
{
    "prediction": 412.5,
    "model_version": "1.0.0",
    "features_used": 11,
    "model_name": "CaloriesIA_1_0_0",
    "imputed_features": { "age": 35.2, "bpm_moyen": 125.5 },
    "original_values": { "imc": 23.5, "sexe": "M", "bpm_max": 180 }
}
```

---

#### `POST /workout/calorie-estimation/predict-from-session`

Prédit pour une séance **déjà enregistrée** et **met à jour** `log_seance.calorie_brulee`.
Toutes les features sont reconstituées depuis Postgres (`log_seance`, `log_sante`,
`profil_sante`, `utilisateur`).

**Entrée** :

```json
{ "id_seance": 123 }
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

Erreurs : `404` (séance introuvable), `403` (n'appartient pas à l'utilisateur).

---

### 4.2 IA Sessions (Ollama — asynchrone)

Toutes les routes ci-dessous : `POST` → `202 { job_id }`, polling via `GET /workout/ai/jobs/{job_id}`.

#### `POST /workout/ai/generate-session`

Génère une séance personnalisée depuis profil + historique récent (lus en base).

**Query param** : `sauvegarder` (bool, défaut `false`) — si `true`, la séance est insérée
dans `log_seance` avec statut `"proposee"`.

**Entrée — tous champs optionnels** :

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

#### `POST /workout/ai/evaluate-sessions`

Évalue des séances déjà enregistrées (identifiées par leurs ids). Aucune écriture.

**Entrée** : `{ "ids_seances": [123, 124] }` (max 20)

**Résultat** :

```json
{
    "avis_global": "...",
    "note_globale": 4,
    "avis_par_seance": [
        {
            "index": 0,
            "points_positifs": ["..."],
            "points_amelioration": ["..."],
            "suggestion": "..."
        }
    ]
}
```

---

#### `GET /workout/ai/evaluate-my-recent-sessions`

Évalue automatiquement les 7 dernières séances `terminee` + jusqu'à 5 `prevue`. Pas de body.
Résultat identique à `evaluate-sessions`.

---

#### `POST /workout/ai/explain-exercises`

Explique une liste d'exercices (max 20).

**Entrée — `nom` obligatoire, autres champs optionnels** :

```json
{
    "exercices": [
        { "nom": "Développé couché" },
        {
            "nom": "Squat",
            "series": 4,
            "repetitions": 10,
            "repos_secondes": 90,
            "muscles_cibles": "Quadriceps"
        }
    ]
}
```

**Résultat** :

```json
{
    "explications": [
        {
            "nom": "Développé couché",
            "description": "...",
            "muscles_cibles": "Poitrine, triceps, épaules",
            "technique": "...",
            "erreurs_courantes": ["Dos cambré excessif"],
            "variantes": ["Incliné", "Haltères"],
            "conseils_securite": "..."
        }
    ]
}
```

---

#### `POST /workout/recommendations/workout`

Programme d'entraînement personnalisé via moteur hybride (classifieur sklearn + LLM).

**Entrée** : aucun body.

**Résultat** :

```json
{
    "status": "success",
    "predictions_classifier": {
        "type_seance": "Musculation",
        "intensite": "Modérée",
        "muscles_cibles": ["Dos", "Biceps"],
        "confidence": { "type_seance": 0.82, "intensite": 0.74 }
    },
    "seance": {
        "titre": "Séance Dos/Biceps",
        "duree_minutes": 50,
        "intensite": "modérée",
        "exercices": [ ... ]
    }
}
```

> Requiert que le modèle `RecoIA_1_0_0` soit entraîné. Si absent : `503` immédiat.

---

#### `GET /workout/ai/jobs/{job_id}` — Polling

Endpoint partagé par toutes les routes asynchrones workout (LLM + reco).

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
    "llm_calls": [
        {
            "system_prompt": "Tu es le coach sportif expert de HealthAI...",
            "user_prompt": "Profil de l'utilisateur :...",
            "raw_response": "{\"type_seance\":\"Musculation\",...}",
            "parsed_ok": true,
            "error": null,
            "timestamp": "2026-05-25T10:30:05Z"
        }
    ],
    "created_at": "2026-05-25T10:30:00Z",
    "updated_at": "2026-05-25T10:30:07Z"
}
```

| `status`     | Signification                                        |
| ------------ | ---------------------------------------------------- |
| `processing` | En cours — `result` est `null`, re-poller dans 2-3 s |
| `completed`  | `result` contient la réponse finale                  |
| `failed`     | `error` + `error_code` (404, 403, 502...)            |

`llm_calls` contient les prompts envoyés à Ollama et la réponse brute (utile pour debug
des sorties JSON invalides).

**404** si le job n'existe pas **ou n'appartient pas à l'utilisateur** (réponse identique).

---

## 5. Service Vision — via `/vision/...`

### 5.1 Analyse photo (YOLO — synchrone)

#### `POST /vision/analyze`

Détecte les aliments sur une image, recherche les macros dans la table `aliment`,
persiste un document Mongo `consumptions`.

**Entrée** : `multipart/form-data` avec un champ `file` (image JPEG/PNG).

**Sortie** :

```json
{
    "filename": "repas.jpg",
    "user_id": "1",
    "consumption_id": "6a13684c67a8a0c84da543fb",
    "count": 3,
    "total_repas": {
        "calories": 723.5,
        "proteines": 32.1,
        "glucides": 88.4,
        "lipides": 24.2,
        "eau_ml": 250
    },
    "detections": [
        {
            "label": "pizza",
            "confidence": 0.92,
            "id_aliment": 42,
            "display_name": "Pizza Margherita",
            "nutrition": {
                "calories": 540,
                "proteines": 22,
                "glucides": 70,
                "lipides": 18,
                "eau": 0
            }
        }
    ]
}
```

Le `consumption_id` est ensuite passé à `POST /vision/nutrition/ai/advice`.

---

### 5.2 Conseils nutritionnels (Ollama — asynchrone, polling Mongo)

#### `POST /vision/nutrition/ai/advice`

Déclenche le calcul Ollama en tâche de fond, qui écrit le conseil dans le document
`consumptions` (champ `recommandation_ia`).

**Entrée** : `{ "consumption_id": "6a13684c67a8a0c84da543fb" }`

**Sortie immédiate** : `{ "status": "processing", "message": "...", "consumption_id": "..." }`

> Renvoie 404 si le `consumption_id` n'existe pas ou n'appartient pas à l'utilisateur.

---

#### `GET /vision/nutrition/consumption/{consumption_id}`

Polling : tant que `recommandation_ia` est `null`, status = `processing`.

**Sortie** :

```json
{
    "consumption_id": "6a13684c67a8a0c84da543fb",
    "status": "completed",
    "total_repas": { "calories": 723.5, "proteines": 32.1, "glucides": 88.4, "lipides": 24.2, "eau_ml": 250 },
    "detections": [ ... ],
    "recommandation_ia": {
        "bilan_macros": "Apport calorique cohérent...",
        "conseils_sante": "Pensez à boire plus d'eau dans l'après-midi..."
    }
}
```

> 404 si le `consumption_id` n'appartient pas à l'utilisateur.

---

### 5.3 Suggestion de recettes (Ollama — asynchrone, polling Mongo)

#### `POST /vision/nutrition/ai/suggest-meal`

Calcule le besoin calorique restant de la journée à partir du profil + de
l'historique Mongo, puis génère une recette via Ollama en tâche de fond.

**Entrée** : aucun body.

**Sortie immédiate** : `{ "status": "processing", "message": "...", "suggestion_id": "..." }`

---

#### `GET /vision/nutrition/suggestion/{suggestion_id}`

Polling.

**Sortie** :

```json
{
    "suggestion_id": "6a13684c67a8a0c84da543fc",
    "status": "completed",
    "validation_status": "pending",
    "resultat": {
        "titre_repas": "Bowl de quinoa au poulet",
        "estimation_calories": "650 kcal",
        "ingredients": "150g de blanc de poulet, 60g de quinoa, ...",
        "instructions": "Cuire le quinoa. Griller le poulet..."
    }
}
```

> 404 si la suggestion n'appartient pas à l'utilisateur.

---

#### `POST /vision/nutrition/ai/validate-suggestion`

Marque la suggestion comme `approved` dans Mongo et **insère un log de repas** dans
Postgres.

**Entrée** : `{ "suggestion_id": "6a13684c67a8a0c84da543fc" }`

**Sortie** : `{ "message": "Repas validé et inscrit avec succès dans PostgreSQL", "suggestion_id": "..." }`

> 404 si la suggestion n'appartient pas à l'utilisateur. 400 si elle n'est pas
> `completed`.

---

## 6. Codes d'erreur

| Code  | Contexte                                  | Signification                                                    |
| ----- | ----------------------------------------- | ---------------------------------------------------------------- |
| `202` | Routes async (LLM, vision advice/suggest) | Job créé, lancé en tâche de fond                                 |
| `400` | Vision validate-suggestion                | Suggestion invalide                                              |
| `401` | Gateway (mode JWKS)                       | Bearer absent / token invalide                                   |
| `403` | Gateway / workout                         | Rôle Zitadel manquant / séance n'appartient pas à l'utilisateur  |
| `404` | Workout / vision                          | Ressource introuvable **ou pas propriétaire** (silencieux)       |
| `422` | Tous                                      | Validation Pydantic échoue (champ manquant, contrainte cassée)   |
| `500` | Vision /analyze                           | Erreur interne lors de l'analyse image                           |
| `502` | Workout (dans le job)                     | LLM renvoie une structure inattendue                             |
| `503` | Workout / vision                          | MongoDB indisponible, modèle ML non chargé, JWKS Zitadel indispo |

---

## 7. Flux types côté front

### Tracking d'une séance

```
1. POST /workout/ai/generate-session                 → 202 { job_id }
2. Poll  /workout/ai/jobs/{job_id}                    → status: "completed"
3. Si l'utilisateur valide :
   POST /workout/ai/generate-session?sauvegarder=true → 202 { job_id }
```

### Analyse d'un repas

```
1. POST /vision/analyze (multipart image)             → { consumption_id, detections, total_repas }
2. POST /vision/nutrition/ai/advice { consumption_id} → 200 processing
3. Poll  /vision/nutrition/consumption/{id}           → status: "completed"
```

### Suggestion de recette

```
1. POST /vision/nutrition/ai/suggest-meal             → 200 { suggestion_id }
2. Poll  /vision/nutrition/suggestion/{id}            → status: "completed"
3. POST /vision/nutrition/ai/validate-suggestion      → 200 message
```
