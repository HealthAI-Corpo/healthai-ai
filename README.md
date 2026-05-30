# healthai-ai

Monorepo des micro-services IA HealthAI — MSPR TPRE502.

Python 3.12 + FastAPI + `uv`, orchestré par Docker Compose. Le déploiement
production est géré dans le repo `healthai-infra` (qui pull les images ghcr.io
construites depuis ce repo).

## Services

| Package                                    | Rôle                                                                     | Port |
| ------------------------------------------ | ------------------------------------------------------------------------ | ---- |
| `healthai-api`                             | Gateway publique : auth Zitadel + reverse proxy `/vision/*` `/workout/*` | 8000 |
| `healthai-vision`                          | Analyse photo de repas (YOLO) + conseils + suggestion recettes           | 8001 |
| `healthai-workout`                         | Estimation calories ML + génération/évaluation séances + reco            | 8002 |
| `healthai-common`                          | Lib partagée (client Ollama) — path dependency                           | —    |
| `healthai-training-ia-calories-estimation` | Pipeline ML offline (génère le modèle CaloriesIA)                        | —    |

## Démarrage

Pré-requis : Docker, [uv](https://docs.astral.sh/uv/).

```powershell
# 1. Recopier les .env.example
Get-ChildItem -Recurse -Filter ".env.example" `
  | Where-Object { $_.FullName -notmatch "\.venv" } `
  | ForEach-Object { Copy-Item $_.FullName ($_.FullName -replace ".env.example$", ".env") -Force }

# 2a. Stack 100 % embarquée (Postgres + Mongo + Ollama locaux)
docker compose up -d --build
#   gateway → http://localhost:8000/docs
#   vision  → http://localhost:8001/docs
#   workout → http://localhost:8002/docs

# 2b. Alternative : si healthai-infra tourne déjà à côté
docker compose -f docker-compose.dev.yml up -d --build
```

Le premier build prend ~10-15 min (vision pulle Torch + YOLO).

## Documentation

- **[API.md](./API.md)** — contrat d'API détaillé (workout + vision), via la gateway.
- Swagger UI de chaque service : `/docs` sur le port correspondant.

## Tests + lint

```powershell
# Par service (workout, vision, common, api)
cd healthai-workout
uv sync --reinstall-package healthai-common   # apres modif healthai-common
uv run pytest -q
uv run ruff check src/ tests/
```

## Architecture rapide

```
                    +------------------+
   front  --JWT-->  | healthai-api     |
                    | (gateway 8000)   |
                    +--------+---------+
                             |
                X-User-Id injecté après auth Zitadel
                             |
              +--------------+--------------+
              v                             v
     +-----------------+           +-----------------+
     | healthai-vision |           | healthai-workout|
     | (8001)          |           | (8002)          |
     +--------+--------+           +--------+--------+
              |                             |
              +-------------+---------------+
                            v
                   +----------------+
                   |  Ollama        |
                   |  Mongo (jobs)  |
                   |  Postgres      |
                   +----------------+
```

## Déploiement

Aucun build à faire ici pour la prod. Le pipeline CI pousse les images sur
`ghcr.io/healthai-corpo/{healthai-ai-gateway,healthai-vision,healthai-workout}`,
et le compose `healthai-infra/docker-compose.yml` les pull. Voir le repo
`healthai-infra` pour les variables d'env Zitadel et l'isolation réseau.
