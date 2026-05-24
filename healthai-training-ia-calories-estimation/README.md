# healthai-training-ia-calories-estimation

Système d'entraînement IA pour la **prédiction des calories brûlées** basé sur les paramètres physiologiques et d'activité d'un utilisateur.

## 📋 Vue d'ensemble

Ce service entraîne et évalue des modèles de machine learning pour prédire les calories brûlées lors d'une séance d'exercice. Les modèles entraînés sont sauvegardés avec leurs métriques et peuvent ensuite être intégrés dans `healthai-workout`.

**Pipeline :** Données brutes → Prétraitement → Entraînement (RF + GB) → Évaluation → Sauvegarde versionnée

## 🎯 Objectif

Fournir un système reproductible et traçable pour :

- Entraîner des modèles de prédiction des calories brûlées
- Évaluer les performances avec des métriques pertinentes (R², MAE, RMSE, MAPE)
- Gérer les versions des modèles avec historique complet
- Extraire les meilleurs modèles pour déploiement en production

## 🏗️ Architecture

```
healthai-training-ia-calories-estimation/
├── data/
│   ├── raw/                          # Données brutes (CSV)
│   │   └── dataset_historique_seance_exercice.*.csv
│   └── models/                       # Modèles entraînés (versionnés)
│       └── CaloriesPOC/
│           └── v1_x_yyyymmdd_hhmmss/
│               ├── random_forest/
│               ├── gradient_boosting/
│               ├── training_data/
│               ├── scaler.pkl
│               ├── transformation_metadata.json
│               ├── training_log.md
│               └── training_data/    # Cache des données d'entraînement
├── src/
│   ├── data_loading.py               # Chargement et validation des données
│   ├── preprocessing.py              # Normalisation, encoding, split train/test
│   ├── model_training.py             # Entraînement RF + GB
│   ├── model_evaluation.py           # Calcul des métriques et comparaison
│   └── model_serialization.py        # Sauvegarde versionnée des artefacts
├── config.py                         # Configuration centralisée (hyperparamètres, seuils)
├── main.py                           # Orchestration du pipeline complet
└── pyproject.toml                    # Dépendances (pandas, sklearn, joblib)
```

## ⚙️ Configuration

Tous les paramètres sont centralisés dans `config.py` :

| Paramètre                 | Défaut                                              | Description                            |
| ------------------------- | --------------------------------------------------- | -------------------------------------- |
| `CSV_FILE`                | `data/raw/dataset_historique_seance_exercice.*.csv` | Données d'entraînement                 |
| `TRAIN_TEST_SPLIT_RATIO`  | `0.8`                                               | Ratio train/test (80/20)               |
| `NORMALIZE_NUMERIC`       | `True`                                              | StandardScaler sur features numériques |
| `RF_PARAMS.n_estimators`  | `150`                                               | Nombre d'arbres Random Forest          |
| `RF_PARAMS.max_depth`     | `12`                                                | Profondeur max des arbres              |
| `GB_PARAMS.learning_rate` | `0.1`                                               | Taux d'apprentissage Gradient Boosting |
| `METRICS_THRESHOLDS`      | Voir config.py                                      | Seuils bon/moyen pour chaque métrique  |

### Features utilisées

- **Données physiologiques** : âge, sexe, IMC (poids + taille), pourcentage gras
- **Paramètres d'activité** : durée, type sport (cardio/force), BPM (repos/moyen/max)
- **Hydratation** : consommation eau
- **Expérience** : niveau d'expérience (1-5)

### Target

- **calories_brulees** : calories brûlées estimées (valeur continue)

## 🚀 Utilisation

### Prérequis

- Python 3.10+
- `uv` installé

### Installation et lancement

```bash
# 1. Installer les dépendances
uv sync

# 2. Lancer le pipeline d'entraînement complet
python main.py
```

Les résultats seront sauvegardés dans `data/models/CaloriesPOC/v1_x_yyyymmdd_hhmmss/`

## 📁 Structure des versions

Chaque entraînement crée une version versionnée :

```
data/models/CaloriesPOC/v1_12_20260522_115951/
├── random_forest/
│   ├── model.pkl                    # Modèle RF
│   ├── metrics.json                 # R², MAE, RMSE, MAPE, etc.
│   ├── predictions.csv              # Prédictions sur test dataset
│   └── feature_importance.json      # Importance des features
├── gradient_boosting/               # Structure identique à random_forest
├── training_data/
│   ├── train_X.csv                  # Features d'entraînement
│   ├── train_y.csv                  # Target d'entraînement
│   ├── test_X.csv                   # Features de test
│   ├── test_y.csv                   # Target de test
│   └── Dataset_*.csv                # Dataset original utilisé
├── scaler.pkl                       # StandardScaler (pour normalisation future)
├── transformation_metadata.json     # Métadonnées d'encodage (sexe, type_sport)
└── training_log.md                  # Résumé complet
```

## 🔄 Workflow d'extraction pour production

1. **Identifier la meilleure version**

2. **Copier le modèle dans healthai-workout**

3. **Mettre à jour healthai-workout** pour charger le nouveau modèle

4. **Tester l'intégration** dans healthai-workout

## 📈 Métriques utilisées

- **R² (Coefficient de Détermination)** : Part de variance expliquée (plus haut = meilleur)
- **MAE (Mean Absolute Error)** : Erreur absolue moyenne en calories (plus bas = meilleur)
- **RMSE (Root Mean Square Error)** : Racine de l'erreur quadratique moyenne (plus bas = meilleur)
- **MAPE (Mean Absolute Percentage Error)** : Erreur en pourcentage (plus bas = meilleur)
- **Median AE** : Médiane de l'erreur absolue (plus bas = meilleur)
