# 🤖 AI — Endpoints IA livrés

**Documentation de référence** des endpoints réellement implémentés et montés dans `healthai-ai`.

> **Contexte :** Les chemins ci-dessous sont ceux exposés par chaque micro-service en direct (sans préfixe gateway). Si une gateway NestJS est mise devant, les routes pourront être ré-préfixées (`/workout/...`, `/vision/...`).

> D'autres Endpoints sont disponibles, mais ils ne sont pas documentés ici car pas principaux (voir Swagger)

---

### POST `/calorie-estimation/predict`

Prédiction des calories brûlées à partir de **11 features fournies en entier**.

#### Entrée (obligatoires)

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

#### Contraintes

- `sexe` ∈ `{M, F}`
- `niveau_experience` ∈ [0, 5]
- `pourcentage_gras` ∈ [0, 100]
- `bpm_repos < bpm_moyen < bpm_max`

#### Sortie

```json
{
    "prediction": 412.5,
    "model_version": "string",
    "features_used": 11,
    "model_name": "string"
}
```

#### Processus interne

1. Encodage des données catégoriques
2. Normalisation (scaler)
3. Prédiction RandomForest
4. **Aucune écriture en base de données**

---

### POST `/calorie-estimation/predict-with-defaults`

Identique à `/predict` mais avec tous les champs **optionnels**. Les champs manquants (`null` ou absents) sont imputés par la moyenne du dataset d'entraînement.

#### Entrée exemple

```json
{
    "imc": 23.5,
    "age": null,
    "sexe": "M",
    "bpm_max": 180
}
```

#### Sortie

```json
{
    "prediction": 412.5,
    "model_version": "string",
    "features_used": 11,
    "model_name": "string",
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

### POST `/calorie-estimation/predict-from-session` ⭐

Prédit les calories d'une séance déjà enregistrée en base et met à jour `log_seance.calorie_brulee`.

#### Entrée

- **Query param :** `user_id` (int)  
  _TODO : à remplacer par l'extraction du JWT ZITADEL._
- **Body :** uniquement `id_seance`. Toutes les autres features sont reconstituées depuis la base.

```json
{
    "id_seance": 123
}
```

#### Sources des features

| Feature                                                               | Source                                   |
| --------------------------------------------------------------------- | ---------------------------------------- |
| `bpm_max`, `consommation_eau_ml`, `bpm_moyen`, `duree`, `type_seance` | `log_seance`                             |
| `bpm_repos`, `pourcentage_gras`                                       | dernier `log_sante`                      |
| `imc`, `age`, `sexe`                                                  | `profil_sante` + `utilisateur`           |
| `niveau_experience`                                                   | _non disponible_ — imputé par la moyenne |

#### Sortie

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

#### Processus interne

1. Lit la séance (`log_seance` par `id_seance_log`)
    - Récupère `bpm_max` et `consommation_eau_ml`
    - Retourne `404` si absente
2. Vérifie l'appartenance à `user_id` → `403` sinon
3. Lit `utilisateur` (âge calculé, sexe normalisé M/F)
4. Lit `profil_sante` (IMC, sinon dérivé de poids/taille)
5. Lit le **dernier** `log_sante` (bpm_repos, % gras)
6. Assemble les 11 features ; imputées si manquantes
7. Prédiction RandomForest
8. **UPDATE** `log_seance.calorie_brulee` + commit
    - `calorie_brulee` a été rendu nullable : `NULL` = "pas encore estimé"
9. Trace dans Mongo (`predictions`, best-effort)

---

### POST `/recommendations/workout` (bonus)

Programme d'entraînement personnalisé via **moteur hybride** :

- Classifieur sklearn (type/intensité/muscles)
- LLM Ollama pour structurer la séance

#### Entrée

- **Header :** `X-User-Id` (temporaire)  
  _TODO : à remplacer par l'extraction du JWT ZITADEL._
- **Aucun body.** Le profil (biométrie, objectif, limitations) et l'historique récent sont reconstitués depuis la base à partir de l'id.

#### Sources des données

| Donnée                         | Source                                              |
| ------------------------------ | --------------------------------------------------- |
| `age`, `poids_kg`, `taille_cm` | `utilisateur` + `profil_sante`                      |
| `niveau_experience` (1–3)      | `profil_sante.experience_sportive` (texte → niveau) |
| `frequence_sport_jour_semaine` | `profil_sante.frequence_entrainement`               |
| `objectif`                     | `profil_sante.objectif_principal`                   |
| `limitations`                  | `profil_sante.type_maladie`                         |
| `historique_seances`           | 5 dernières `log_seance`                            |
| `bpm_repos`                    | _non disponible_ — défaut 65                        |

> **Asynchrone (202 + polling).** L'appel Ollama étant lent, la route ne bloque pas :
> elle renvoie un `job_id` immédiatement et le travail tourne en tâche de fond.
> Récupérer le résultat via [`GET /ai/jobs/{job_id}`](#get-aijobsjob_id). Le schéma de
> séance ci-dessous est aussi **envoyé à Ollama** (`response_format`) pour contraindre sa sortie.

#### Processus interne

1. Vérifie le modèle de reco chargé (`503` sinon) et Mongo disponible (`503` sinon)
2. Crée un job (`status="processing"`) et renvoie `202 { job_id }`
3. **En tâche de fond :** reconstruit le profil (`404` reporté dans le job si utilisateur introuvable)
4. Classifieur sklearn → type / intensité / muscles cibles + scores de confiance
5. LLM Ollama structure la séance complète (schéma JSON imposé)
6. **Aucune écriture Postgres.** Le résultat est stocké dans le job (Mongo `ai_jobs`)

#### Sortie immédiate

```json
{ "job_id": "665f...", "status": "processing" }
```

#### Résultat (dans le job, via `GET /ai/jobs/{job_id}`)

Le champ `result` du job contient :

```json
{
    "status": "success",
    "predictions_classifier": {
        "type_seance": "string",
        "intensite": "string",
        "muscles_cibles": ["array"],
        "confidence": {}
    },
    "seance": {
        "titre": "Nom de la séance",
        "duree_minutes": 45,
        "intensite": "modérée",
        "exercices": [
            {
                "nom": "Nom de l'exercice",
                "muscles_cibles": ["muscle1"],
                "series": 3,
                "repetitions": "10-12",
                "repos_secondes": 90,
                "conseil": "Astuce technique"
            }
        ]
    }
}
```

#### Erreurs

- **503** (immédiat) : modèle `RecoIA_1_0_0` non chargé (→ `scripts/train_recommendation_model.py`) **ou** MongoDB indisponible
- **404** (dans le job) : utilisateur introuvable → `status="failed"`, `error_code=404`
- **500** (dans le job) : erreur de génération (classifier/LLM) → `status="failed"`

---

## 🧠 Service WORKOUT — Génération IA (Ollama)

Préfixe : `/ai`

### Configuration commune

#### Mode asynchrone (202 + polling) ⭐

Les appels Ollama sont lents (chargement modèle CPU, jusqu'à 180 s). **Toutes les routes
LLM workout sont donc non bloquantes** (calquées sur le service vision) :

1. La route crée un job, lance le travail en **tâche de fond**, et renvoie aussitôt :
    ```json
    { "job_id": "665f...", "status": "processing" }
    ```
    avec le code HTTP **202**.
2. Le front interroge ensuite [`GET /ai/jobs/{job_id}`](#get-aijobsjob_id) jusqu'à
   `status="completed"` (ou `"failed"`).
3. Le résultat (ou l'erreur) est stocké dans MongoDB (collection `ai_jobs`).
   **MongoDB est donc requis** : `503` si indisponible.

> Conséquence : les erreurs métier (`404` utilisateur/séance, `403`, `502` LLM) ne
> remontent plus en HTTP direct mais sont reportées **dans le job** (`status="failed"`,
> champ `error_code`). Seules les erreurs de pré-requis (`422` validation du body,
> `503` Mongo) restent synchrones.

#### Schéma de sortie imposé à Ollama

Chaque route envoie le **schéma JSON de sa réponse** à Ollama via `response_format`
(argument de `healthai_common.llm`), ce qui contraint la structure générée. La sortie
est ensuite revalidée côté serveur contre le schéma Pydantic (sinon job `failed` 502).

#### Authentification

- **Header :** `X-User-Id` (temporaire)
- _TODO : Remplacer par extraction JWT ZITADEL_

#### Récupération de contexte

- Contexte utilisateur et historique des séances **lus en base** à partir de l'id
- Le front **ne les envoie plus**

#### Logging

- Chaque appel tracé dans Mongo (best-effort)
- N'interrompt jamais la réponse

#### Erreurs courantes

| Code             | Signification                                     |
| ---------------- | ------------------------------------------------- |
| `202`            | Job accepté et lancé en tâche de fond             |
| `422`            | Validation du body échoue (synchrone)             |
| `503`            | MongoDB indisponible (store des jobs) — synchrone |
| `404` (dans job) | Utilisateur / séance introuvable                  |
| `403` (dans job) | Séance n'appartient pas à l'utilisateur           |
| `502` (dans job) | LLM renvoie une structure inattendue              |

---

### Forme commune d'un exercice (JSON)

```json
{
    "nom": "texte",
    "type": "texte?",
    "series": "int?",
    "repetitions": "int?",
    "duree_secondes": "int?",
    "repos_secondes": "int?",
    "muscles_cibles": "texte?"
}
```

- **En entrée** : tous les champs (hors `nom`) sont optionnels
- **En sortie LLM** : on attend tous les champs renseignés

---

### POST `/ai/generate-session`

Génère une proposition de séance personnalisée depuis le profil + l'historique.

#### Entrée

- **Header :** `X-User-Id`
- **Query param :** `sauvegarder` (bool, défaut `false`)
- **Body :**

```json
{
    "duree_souhaitee_minutes": 45,
    "equipement_disponible": ["Haltères"],
    "focus_musculaire": "Jambes"
}
```

_Tous les champs body sont optionnels._

#### Processus (en tâche de fond)

1. Récupère contexte + dernières séances (DB)
2. Envoie prompt + schéma à Ollama
3. Valide la structure retournée (sinon job `failed` 502)
4. Si `sauvegarder=true` :
    - Insert `log_seance` avec `statut='proposee'`
    - Trace dans Mongo
5. Écrit le résultat dans le job

#### Sortie immédiate

```json
{ "job_id": "665f...", "status": "processing" }
```

#### Résultat (champ `result` du job)

```json
{
    "id_seance_log": 123,
    "log_date": "2025-05-25T10:30:00Z",
    "statut": "proposee",
    "type_seance": "Musculation",
    "titre_seance": "Jambes intensives",
    "duree_minutes": 45,
    "difficulte": "Intermédiaire",
    "objectif": "Hypertrophie",
    "conseils_generaux": "...",
    "exercices": []
}
```

- `id_seance_log`, `log_date`, `statut` renseignés **seulement si sauvegardé**
- Par défaut (pas de `sauvegarder`), rien n'est persisté → le front décide

---

### POST `/ai/evaluate-sessions`

Évalue des séances **déjà enregistrées**, désignées par leurs ids. **Aucune écriture Postgres.**

#### Entrée

- **Header :** `X-User-Id`
- **Body :**

```json
{
    "ids_seances": [123, 124, 125]
}
```

#### Processus (en tâche de fond)

1. Récupère les séances en base
2. Job `failed` 404 si un id introuvable
3. Job `failed` 403 si une séance n'appartient pas à l'utilisateur
4. Transmet à Ollama (schéma imposé)

#### Sortie immédiate

```json
{ "job_id": "665f...", "status": "processing" }
```

#### Résultat (champ `result` du job)

```json
{
    "avis_global": "Très bonne progression...",
    "note_globale": 4,
    "avis_par_seance": [
        {
            "index": 0,
            "points_positifs": ["Bonne intensité", "Repos adéquat"],
            "points_amelioration": ["Plus de variété"],
            "suggestion": "..."
        }
    ]
}
```

---

### GET `/ai/evaluate-my-recent-sessions`

Évalue automatiquement les dernières séances de l'utilisateur. **Aucune écriture Postgres.**

#### Entrée

- **Header :** `X-User-Id`
- Aucun body

#### Processus (en tâche de fond)

1. Récupère :
    - Les **7 dernières séances `terminee`** (plus récentes)
    - Jusqu'à **5 séances `prevue`** (dates les plus proches)
2. Transmet à Ollama (schéma imposé)
3. Job `failed` 404 si aucune séance à évaluer

#### Sortie immédiate

```json
{ "job_id": "665f...", "status": "processing" }
```

#### Résultat (champ `result` du job)

Identique à [`/ai/evaluate-sessions`](#post-aievaluate-sessions)

---

### POST `/ai/explain-exercises`

Explique une liste d'exercices (technique, erreurs, variantes, sécurité). **Aucune écriture Postgres.**

#### Entrée

- **Header :** `X-User-Id`
- **Body :**

```json
{
    "exercices": [{ "nom": "Développé couché" }, { "nom": "Squat" }]
}
```

#### Sortie immédiate

```json
{ "job_id": "665f...", "status": "processing" }
```

#### Résultat (champ `result` du job)

```json
{
    "explications": [
        {
            "nom": "Développé couché",
            "description": "Exercice de base...",
            "muscles_cibles": "Poitrine, triceps, épaules",
            "technique": "Gardez le dos à 45°...",
            "erreurs_courantes": ["Manque de contrôle", "Coup de rein excessif"],
            "variantes": ["Incliné", "Haltères", "Machine"],
            "conseils_securite": "..."
        }
    ]
}
```

---

### GET `/ai/jobs/{job_id}`

**Endpoint de polling** commun à toutes les routes IA asynchrones du service workout
(les 4 routes `/ai/*` **et** `/recommendations/workout`).

#### Entrée

- **Path param :** `job_id` (renvoyé par la route async)
- _Aucun header requis_

#### Sortie

```json
{
    "job_id": "665f...",
    "type": "generate-session",
    "status": "completed",
    "result": {
        /* la sortie de l'endpoint d'origine, ou null tant que processing/failed */
    },
    "error": null,
    "error_code": null,
    "created_at": "2026-05-25T10:30:00Z",
    "updated_at": "2026-05-25T10:30:07Z"
}
```

| `status`     | Signification                                                |
| ------------ | ------------------------------------------------------------ |
| `processing` | Ollama travaille encore — `result` est `null`, ré-interroger |
| `completed`  | `result` contient la sortie de l'endpoint                    |
| `failed`     | `error` + `error_code` renseignés (ex : 404, 403, 502)       |

- **404** : `job_id` inconnu (ou mal formé)
- **503** : MongoDB indisponible

---

## 🍽️ Service VISION — port 8001

#### À venir

- `/analyze`
- `evaluate-diet` — analyse complète du régime
- `suggest-meal` — suggestion de repas équilibrés

---

## ⚠️ Codes d'erreur courants

| Code    | Signification              | Exemple                                                    |
| ------- | -------------------------- | ---------------------------------------------------------- |
| **422** | Validation Pydantic échoue | `bpm_repos ≥ bpm_moyen`, sexe hors `M/F`                   |
| **404** | Ressource introuvable      | Séance, utilisateur, modèle                                |
| **403** | Accès refusé               | Séance n'appartient pas à l'utilisateur                    |
| **503** | Service indisponible       | Modèle non chargé (`.pkl` manquant, `RecoIA` non entraîné) |
| **502** | Bad Gateway / Erreur LLM   | LLM renvoie une structure inattendue                       |

---

## Reste à faire :

- Ajouter le routeur/ API/ pour avoir une seule base url ia pour le front pour le workout et vision
- ajouter les JWT plutôt que l'id actuellement
- optionnel : faire en sorte que les jobs Async gardent en mémoire les prompts et les réponses JSON dans de mauvais formats

## Fait :

- **Routes LLM workout passées en asynchrone (202 + polling)**, comme vision : `/ai/generate-session`, `/ai/evaluate-sessions`, `/ai/evaluate-my-recent-sessions`, `/ai/explain-exercises` et `/recommendations/workout` renvoient un `job_id` et délèguent Ollama à une tâche de fond ; nouvel endpoint `GET /ai/jobs/{job_id}` pour récupérer le résultat (Mongo requis → 503 sinon)
- **Schéma de sortie envoyé à Ollama** (`response_format`) sur toutes les routes LLM workout pour contraindre la structure générée
- Plafonds anti-requête trop lourde sur les routes IA : `/ai/generate-session` (durée ≤ 180 min), `/ai/evaluate-sessions` (≤ 20 ids), `/ai/explain-exercises` (≤ 20 exercices), `/recommendations/workout` (champs texte/historique bornés)
- Doublon corrigé : `evaluate_sessions()` n'ajoute plus l'historique récent (les séances à évaluer le sont déjà) → plus de données en double sur `/ai/evaluate-sessions` et `/ai/evaluate-my-recent-sessions`
- Suppression du CRUD `/sessions` (code mort)
- `/recommendations/workout` (route de Loric) : cartographiée + entrée réduite au seul `X-User-Id`, le contexte/santé/historique étant désormais lus en base
