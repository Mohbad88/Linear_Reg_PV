# PV Production Forecasting - Linear Regression Pipeline

## 📋 Architecture

4 phases MLOps :
1. **Collecte Données** : Open-Meteo API (météo) + Tydom (production locale)
2. **Apprentissage** : Entraînement LinearRegression sur données historiques
3. **Inférence** : Prédictions production PV future
4. **Log Erreurs** : Métriques et comparaison réel vs prédictions

---

## 🚀 Installation & Setup

### 1. Créer et activer l'environnement virtuel

```bash
# Créer venv
python -m venv .venv

# Activer venv (PowerShell)
.\.venv\Scripts\Activate.ps1

# Ou (CMD)
.venv\Scripts\activate.bat
```

> **Windows PowerShell?** Si erreur d'exécution : `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process`

### 2. Installer les dépendances

```bash
pip install -r requirements.txt
```

---

## 🏋️ Entraînement du modèle

### Lancer l'entraînement local

```bash
python main_training_pipeline.py
```

**Options disponibles :**

```bash
# Avec paramètres custom
python main_training_pipeline.py \
  --data_source weather_api_local_production \
  --start_date 2018-01-01 \
  --end_date 2021-12-31 \
  --latitude 48.7667 \
  --longitude 2.6667 \
  --split_date 2020-07-31 \
  --register_model true
```

**Paramètres :**
- `--data_source` : `api` | `file` | `weather_api_local_production` (défaut)
- `--input_path` : Chemin CSV local (défaut: `data/raw/dfmodelpierrerozir.csv`)
- `--start_date` : Date début API (format YYYY-MM-DD)
- `--end_date` : Date fin API
- `--latitude` / `--longitude` : Coordonnées géographiques (défaut: Bussy-Saint-Georges)
- `--split_date` : Date train/test split
- `--register_model` : Enregistrer dans Azure ML (true/false)

**Résultat :**
```
Dataset loaded successfully: (25502, 28)
Train samples  : 816
Test samples   : 167
R2   : 0.830
MAE  : 1440.3 Wh/day
RMSE : 1926.1 Wh/day
✅ Model saved to: outputs/model.pkl
✅ Scaler saved to: outputs/scaler.pkl
✅ Metadata saved to: outputs/metadata.json
```

---

## 🎯 Inférence (Prédictions)

### Lancer l'inférence

```bash
python inference.py
```

**Résultat :**
```json
{
  "predicted_production_wh": 4250.5,
  "confidence_interval": [3800.2, 4700.8],
  "timestamp": "2026-04-28T10:30:00Z"
}
```

Résultats sauvegardés dans : `inference_results.json`

---

## 📊 Visualisation & Tests

### Tester les visualisations

```bash
python -m src.visualization.test
```

Génère des graphiques :
- `outputs/predictions_vs_actual.png`
- `outputs/residuals_plot.png`

---

## ☁️ Déploiement Azure ML (Optionnel)

### Soumettre le job d'entraînement à Azure ML

```bash
python submit_training_job.py
```

---

## 📁 Structure du projet

```
Linear_Reg_PV/
├── main_training_pipeline.py    # Entraînement complet
├── inference.py                  # Inférence/prédictions
├── submit_training_job.py        # Soumission Azure ML
├── requirements.txt              # Dépendances
├── config.json                   # Configuration projet
│
├── data/
│   ├── raw/                     # Données brutes
│   │   └── dfmodelpierrerozir.csv
│   └── processed/               # Données nettoyées
│
├── src/
│   ├── data/
│   │   ├── fetch_api_data.py   # Ingestion Open-Meteo + Tydom
│   │   ├── aggregation.py       # Agrégation horaire→journalière
│   │   └── cleaning.py          # Nettoyage données
│   ├── features/
│   │   ├── clearsky_features.py # Rayonnement ciel clair
│   │   ├── kc_features.py       # Index clarté Kc
│   │   └── time_features.py     # Features calendaires
│   ├── models/
│   │   ├── train_linear_model.py # Entraînement LinearRegression
│   │   ├── predict.py           # Prédictions
│   │   ├── split.py             # Train/test split
│   │   └── evaluate_model.py    # Évaluation métriques
│   └── visualization/
│       ├── plot_predictions.py  # Graphiques
│       └── test.py              # Tests visualisation
│
└── outputs/                      # Modèles & résultats
    ├── model.pkl
    ├── scaler.pkl
    └── metadata.json
```

---

## 🔧 Commandes rapides

| Tâche | Commande |
|-------|----------|
| **Setup complet** | `.\.venv\Scripts\Activate.ps1 && pip install -r requirements.txt` |
| **Entraîner** | `python main_training_pipeline.py` |
| **Prédire** | `python inference.py` |
| **Visualiser** | `python -m src.visualization.test` |
| **Azure ML** | `python submit_training_job.py` |

---

## ⚠️ Prérequis

- **Python 3.11+** (Azure ML supporte 3.8-3.12 ; en local 3.13+ OK)
- **Internet** : Open-Meteo API (météo historique)
- **CSV local** : Production PV historique (`data/raw/dfmodelpierrerozir.csv`)

---

## 📝 Notes

- **Tydom** : Données en temps réel du capteur local
- **Open-Meteo** : API météo gratuite (lat/lon configurables)
- **Azure ML** : Optionnel, non requis pour entraînement local

