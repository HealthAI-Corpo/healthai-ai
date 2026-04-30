# healthai-ai

Monorepo des micro-services IA — MSPR TPRE502.

> Document indicatif. Les choix techniques peuvent évoluer lors de l'implémentation.

# Stack technique commune

- Langage : Python 3.12 (via uv)
- Framework : FastAPI
- Orchestration : Docker Compose (développement avec volumes miroirs)
- Communication : HTTPX (appels asynchrones entre services)

## Structure

```text
healthai-ai/
├── healthai-api/ # GATEWAY : Point d'entrée unique du Front-end
│ ├── src/
│ │ ├── api/ # Routes REST et agrégation
│ │ ├── core/ # Config (Zitadel, Secrets) et Sécurité
│ │ ├── graphql/ # Schéma Strawberry (Fédère Vision + Workout)
│ │ ├── services/ # Clients HTTP (Appels vers Vision/Workout)
│ │ └── main.py # Lancement du serveur (Port 8000)
│ ├── .env # URLs des micro-services et clés API
│ ├── Dockerfile # Build léger pour la Gateway
│ └── pyproject.toml # Dépendances (FastAPI, Strawberry, HTTPX)
│
├── healthai-vision/ # SERVICE IA : Analyse d'image & Nutrition
│ ├── src/
│ │ ├── api/ # Endpoint /analyze/meal
│ │ ├── core/ # Configuration (Modèles HuggingFace)
│ │ ├── infrastructure/ # Connexion Postgres (Table Aliment)
│ │ ├── services/ # Logique IA (YOLO v8 / EfficientNet)
│ │ └── main.py # Serveur (Port 8001)
│ ├── .hf_cache/ # Cache local des modèles IA (évite le download)
│ ├── Dockerfile # Build avec dépendances ML (Torch, OpenCV)
│ └── pyproject.toml # Dépendances (Ultralytics, Transformers)
│
├── healthai-workout/ # SERVICE IA : Moteur de recommandation
│ ├── src/
│ │ ├── api/ # Endpoint /recommend/workout
│ │ ├── core/ # Configuration (Chemin modèle .joblib)
│ │ ├── infrastructure/ # Connexion MongoDB (Historique NoSQL)
│ │ ├── services/ # Logique IA (Scikit-learn Fine-tuning)
│ │ └── main.py # Serveur (Port 8002)
│ ├── models/ # Stockage des modèles entraînés (.joblib)
│ ├── Dockerfile # Build avec Scikit-learn & Pandas
│ └── pyproject.toml # Dépendances (Sklearn, Motor, Asyncpg)
│
├── docker-compose.yml # Orchestration (API + Vision + Workout + DBs)
└── .gitignore # Exclusion des .env, .venv et caches IA
```

# Pré-requis

- Avoir Docker et Docker Desktop installés.
- Installer uv sur votre machine locale (optionnel, pour la gestion des locks).

# Configuration

Pour chaque service (healthai-api, healthai-vision, healthai-workout), créer un fichier .env basé sur les besoins de configuration (voir src/core/config.py).

# Lancement

docker compose up --build (le build sera long la première fois à cause des dépendances)
docker compose up

les services accessible seront donc :

- http://localhost:8000/docs
- http://localhost:8001/docs
- http://localhost:8002/docs

Route de test healcheck des :
curl http://localhost:8000/test-internal

réponse attendue :
{
"gateway": "OK",
"vision_service": {"status": "online", ...},
"workout_service": {"status": "online", ...}
}

# Securité

Gerée par le gateway (healthai-api) config controle le JWT user et la config zitadel

## Services

### `healthai-vision` — Analyse nutritionnelle par photo (port 8001)

Identifie les aliments dans une photo de repas et calcule les macronutriments.

**Stack envisagée :** FastAPI · HuggingFace Transformers (EfficientNet-B0 + YOLO v8) · PostgreSQL · uv

**Flux principal :**

```
POST /analyze/meal (image) → classification Food-101 → cross-ref table aliment → macros → suggestions
```

**Points d'attention :**

- Mapping Food-101 (101 classes anglaises) ↔ table `aliment` à construire
- Cache par hash SHA-256 de l'image dans la table `analyse_repas` (migration 000006)
- Rate limiting : 10 req/min (appels modèle coûteux)
- Marge d'erreur calories : ±20% — à afficher à l'utilisateur

---

### `healthai-workout` — Recommandation sportive (port 8002)

Génère un programme d'entraînement personnalisé selon le profil utilisateur.

**Stack envisagée :** FastAPI · Scikit-learn · MongoDB (Motor async) · PostgreSQL · uv

**Flux principal :**

```
POST /recommend/workout (objectif, niveau, équipements) → feature vector → modèle → programme hebdomadaire → MongoDB
```

**Document MongoDB (structure indicative) :**

```json
{
  "utilisateur_id": "uuid",
  "objectif": "perte_poids",
  "niveau": "intermediaire",
  "programme": {
    "semaine": 1,
    "seances": [{ "jour": "lundi", "exercices": [...] }]
  },
  "metrics": { "model_version": "1.0.0", "confidence_score": 0.87 }
}
```

---

## Migrations BDD à prévoir

| Fichier                                    | Contenu                                      |
| ------------------------------------------ | -------------------------------------------- |
| `000006_analyse_repas.up.sql`              | Cache + historique analyses photos           |
| `000007_historique_recommandations.up.sql` | Trace recommandations (ref ObjectId MongoDB) |

---

## Démarrage local

```bash
cp healthai-vision/.env.example healthai-vision/.env
cp healthai-workout/.env.example healthai-workout/.env
# Éditer les .env avec les valeurs locales
docker compose up -d
```

---

## Tâches backlog

| #   | Service                                   | Statut                   |
| --- | ----------------------------------------- | ------------------------ |
| 1   | Vision Alimentaire (`healthai-vision`)    | À faire                  |
| 2   | Moteur Reco Sportive (`healthai-workout`) | À faire                  |
| 3   | Métriques IA (precision/recall/F1)        | À faire                  |
| 5   | Micro-service isolé (`healthai-workout`)  | À faire (inclus dans #2) |
