# Training Log - v1_12_20260522_115951

**Date d'entraînement** : 2026-05-22 11:59:51

---

## 📊 Résumé Général

| Métrique | Valeur |
|----------|--------|
| Version | v1_12_20260522_115951 |
| Échantillons Train | 1963 |
| Échantillons Test | 491 |
| Temps RF | 0.24s |
| Temps GB | 0.41s |

---

## 🌲 Random Forest Regressor

### Paramètres
- `n_estimators`: 150
- `max_depth`: 12
- `min_samples_split`: 10
- `min_samples_leaf`: 4
- `random_state`: 42
- `n_jobs`: -1

### Résultats d'Évaluation
| Métrique | Valeur |
|----------|--------|
| R² | 0.1751 |
| MAE | 200.39 |
| RMSE | 280.22 |
| MSE | 78524.49 |
| MAPE (%) | 24.59 |
| Median AE | 126.07 |

---

## 🚀 Gradient Boosting Regressor

### Paramètres
- `n_estimators`: 100
- `learning_rate`: 0.1
- `max_depth`: 5
- `min_samples_split`: 5
- `min_samples_leaf`: 2
- `random_state`: 42

### Résultats d'Évaluation
| Métrique | Valeur |
|----------|--------|
| R² | 0.1441 |
| MAE | 203.03 |
| RMSE | 285.44 |
| MSE | 81475.95 |
| MAPE (%) | 24.68 |
| Median AE | 135.54 |

---

## 📦 Baseline (DummyRegressor - Mean)

### Résultats d'Évaluation
| Métrique | Valeur |
|----------|--------|
| R² | -0.0030 |
| MAE | 247.93 |
| RMSE | 309.01 |
| MSE | 95486.97 |
| MAPE (%) | 31.93 |
| Median AE | 206.82 |

---

## 🏆 Comparaison et Rankings

**Meilleur modèle global** : `RANDOM_FOREST`

### Points par Métrique
| Métrique | RF | GB | Baseline | Gagnant |
|----------|----|----|----------|---------|
| r2 | 1 | 2 | 3 | RANDOM FOREST |
| mae | 1 | 2 | 3 | RANDOM FOREST |
| mse | 1 | 2 | 3 | RANDOM FOREST |
| rmse | 1 | 2 | 3 | RANDOM FOREST |
| mape | 1 | 2 | 3 | RANDOM FOREST |
| median_absolute_error | 1 | 2 | 3 | RANDOM FOREST |


---

## 📊 Feature Importance

| Feature | RF Importance (%) | GB Importance (%) |
|---------|-------------------|-------------------|
| duree_seance_minutes | 27.90 | 25.55 |
| pourcentage_gras | 13.15 | 13.92 |
| bpm_moyen | 10.57 | 10.23 |
| consommation_eau_ml | 9.20 | 8.54 |
| imc | 9.07 | 11.85 |
| niveau_experience | 7.15 | 7.88 |
| age | 7.12 | 5.83 |
| bpm_repos | 7.04 | 7.06 |
| bpm_max | 5.99 | 6.34 |
| sexe | 1.84 | 2.16 |
| type_sport | 0.98 | 0.66 |


---

## 📌 Fichiers Sauvegardés

- ✅ Modèles (.pkl)
- ✅ Métriques (metrics.json)
- ✅ Données d'entraînement (CSV)
- ✅ Métadonnées de transformation (transformation_metadata.json)
- ✅ Scaler (scaler.pkl)
- ✅ Log d'entraînement (training_log.md)
