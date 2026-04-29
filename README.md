# healthai-ai

Monorepo des micro-services IA — MSPR TPRE502.

> Document indicatif. Les choix techniques peuvent évoluer lors de l'implémentation.

---

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

| Fichier | Contenu |
|---------|---------|
| `000006_analyse_repas.up.sql` | Cache + historique analyses photos |
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

| # | Service | Statut |
|---|---------|--------|
| 1 | Vision Alimentaire (`healthai-vision`) | À faire |
| 2 | Moteur Reco Sportive (`healthai-workout`) | À faire |
| 3 | Métriques IA (precision/recall/F1) | À faire |
| 5 | Micro-service isolé (`healthai-workout`) | À faire (inclus dans #2) |
