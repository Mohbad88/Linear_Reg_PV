# Architecture MLOps Complète : Prédiction Production PV

## 📋 Vue d'ensemble

Ce projet implémente un pipeline MLOps complet pour la **prédiction de production photovoltaïque** (PV) à partir de données météorologiques. L'architecture repose sur **4 phases distinctes** orchestrées entre une infrastructure **Edge Local** (Tydom) et **Cloud** (Azure ML + Open-Meteo).

---

## 🏗️ Architecture Globale

```
┌─────────────────────────────────────────────────────────────────────┐
│                    ARCHITECTURE MLOPS PV PREDICTION                 │
├─────────────────────┬───────────────────────────────────────────────┤
│   EDGE LOCAL        │         CLOUD DELTADORE (Azure ML)            │
├─────────────────────┼───────────────────────────────────────────────┤
│ ┌─────────────────┐ │ ┌──────────────────────────────────────────┐  │
│ │     Tydom       │ │ │    Open-Meteo Historical Data (API)     │  │
│ │  (Production)   │ │ │                                          │  │
│ └────────┬────────┘ │ └───────────────┬──────────────────────────┘  │
│          │          │                 │                             │
│ ┌────────▼────────┐ │ ┌───────────────▼──────────────────────────┐  │
│ │ Data Ingestion  │ │ │  Dataset Preprocessing & Merging        │  │
│ │ (Collection)    │ │ │  (Fusion Open-Meteo + Tydom)            │  │
│ └────────┬────────┘ │ └───────────────┬──────────────────────────┘  │
│          │          │                 │                             │
│ ┌────────▼─────────────────────────────▼──────────────────────────┐ │
│ │       PHASE 1: DATA COLLECTION (Daily)                         │ │
│ │  • Collect hourly PV production (Tydom local storage)          │ │
│ │  • Collect weather forecast (Open-Meteo API)                   │ │
│ │  • Merge & aggregate hourly→daily                              │ │
│ └──────────────────────┬─────────────────────────────────────────┘ │
│                        │ Training Dataset                            │
│ ┌──────────────────────▼─────────────────────────────────────────┐ │
│ │       PHASE 2: TRAINING (Scheduled/On-demand)                  │ │
│ │  • Load historical data (2018-2021)                            │ │
│ │  • Feature engineering (clearsky, Kc, temporal)                │ │
│ │  • Train LinearRegression model                                │ │
│ │  • Store model.pkl, scaler.pkl, metadata.json                │ │
│ │  • Optional: Register in Azure ML                              │ │
│ └──────────────────────┬─────────────────────────────────────────┘ │
│                        │ Trained Model                               │
│ ┌──────────────────────▼─────────────────────────────────────────┐ │
│ │       PHASE 3: INFERENCE (Daily @ 24:00 for J+1)              │ │
│ │  • Load model + scaler + metadata                              │ │
│ │  • Fetch forecast weather for J+1 (Open-Meteo)                │ │
│ │  • Engineer features for J+1                                   │ │
│ │  • Predict PV production for tomorrow                          │ │
│ │  • Save: inference_results.json                                │ │
│ └──────────────────────┬─────────────────────────────────────────┘ │
│                        │ Prediction                                  │
│ ┌──────────────────────▼─────────────────────────────────────────┐ │
│ │       PHASE 4: ERROR LOGGING (Next day comparison)             │ │
│ │  • Load yesterday's prediction (from JSON)                     │ │
│ │  • Load actual production from CSV (PV_ELE_IME_I_001)         │ │
│ │  • Calculate errors (MAE, %, over/under-estimation)            │ │
│ │  • Append to error_logs.json (historical tracking)             │ │
│ └──────────────────────┬─────────────────────────────────────────┘ │
│                        │ Error Logs                                  │
└────────────────────────┴───────────────────────────────────────────┘
```

---

## 📊 Phase 1 : Collecte de Données

### Objectif
Agréger les données de production et météorologiques en un dataset d'entraînement journalier cohérent.

### Composants

| Composant | Source | Format | Fréquence |
|-----------|--------|--------|-----------|
| **Production PV** | Tydom (local) | Hourly → Daily sum | Temps réel |
| **Météo historique** | Open-Meteo API | Hourly → Daily mean/std | Archive (2018-2021) |

### Flux de données

```
┌─────────────────────────────────────────────────────────────────┐
│ EDGE LOCAL (Tydom)                  CLOUD (Open-Meteo API)     │
├─────────────────────┬──────────────────────────────────┬────────┤
│ Tydom IoT Device    │ HTTP GET Historic Data           │ HTTP   │
│ (PV hourly)         │ lat, lon, start_date, end_date   │ GET    │
│                     │                                  │        │
│ PV_ELE_IME_I_001    │ Response: shortwave_radiation    │ Fore-  │
│ (Wh/h)              │           direct_radiation       │ cast   │
│                     │           diffuse_radiation      │ (J+1)  │
│                     │           temperature            │        │
│                     │           cloudcover              │        │
│                     │           windspeed               │        │
└────────┬────────────┴──────────────────┬────────────────┴────────┘
         │                               │
         └───────────────┬───────────────┘
                         │
              ┌──────────▼──────────┐
              │  Data Merging       │
              │  (Fusion)           │
              │  - Join on date     │
              │  - Hourly→Daily agg │
              │  - Feature eng.     │
              └──────────┬──────────┘
                         │
              ┌──────────▼────────────────┐
              │ df_daily_cleaned.csv      │
              │                           │
              │ Columns:                  │
              │ - date                    │
              │ - PV_ELE_IME_I_001        │
              │ - shortwave_radiation     │
              │ - cs_ghi (clearsky)       │
              │ - kc (clearness index)    │
              │ - temperature_2m          │
              │ - month, day_of_year      │
              │ - sin/cos features        │
              └───────────────────────────┘
```

### Fichiers impliqués
- **Script principal** : `main_training_pipeline.py`
- **Ingestion data** : `src/data/fetch_api_data.py`
  - `build_training_frame_weather_api_local_from_env()` → Hybrid mode (API + local CSV)
  - `add_hourly_engineered_columns()` → Features à niveau horaire
- **Nettoyage** : `src/data/cleaning.py`
  - `clean_dataset()` → Remove invalid/low production
- **Agrégation** : `src/data/aggregation.py`
  - `aggregate_daily()` → Hourly → Daily

---

## 🏋️ Phase 2 : Apprentissage (Training)

### Objectif
Entraîner un modèle **LinearRegression** pour prédire la production PV journalière à partir de features météorologiques.

### Architecture du modèle

```
INPUT FEATURES (28)
├─ Weather features (7)
│  ├─ shortwave_radiation
│  ├─ direct_radiation
│  ├─ diffuse_radiation
│  ├─ temperature_2m
│  ├─ cloudcover
│  ├─ windspeed_10m
│  └─ pressure_msl
│
├─ Clearsky features (3)
│  ├─ cs_ghi (clearsky GHI)
│  ├─ cs_dni (clearsky DNI)
│  └─ cs_dhi (clearsky DHI)
│
├─ Radiation aggregations (4)
│  ├─ rad_mean_3h
│  ├─ rad_std_3h
│  ├─ rad_diff_1h
│  └─ kc_day (Clearness index)
│
├─ Temporal features (9)
│  ├─ day_cos / day_sin
│  ├─ month_cos / month_sin
│  ├─ day_of_year
│  ├─ day_of_year_cos / day_of_year_sin
│  └─ month
│
└─ Custom features (5)
   └─ [reserved for future extensions]

         ↓ StandardScaler (normalization)
         ↓ [28 normalized features]
         
┌────────────────────────────────────────────┐
│    LinearRegression Model                  │
│    (scikit-learn v1.3+)                    │
│                                            │
│    coef = [β₁, β₂, ..., β₂₈]              │
│    intercept = β₀                          │
└──────────────────┬─────────────────────────┘
                   │
                   ↓ model.pkl
              
OUTPUT: Daily PV Production (Wh/day)
```

### Données d'entraînement

```
Dataset: df_daily_cleaned.csv
├─ Date range: 2018-03-01 to 2021-12-31
├─ Total records: ~1400 days
├─ Split date: 2020-07-31
│
├─ TRAIN (816 samples)
│  └─ 2018-03-01 to 2020-07-31
│     (historical baseline, 2.3 years)
│
└─ TEST (167 samples)
   └─ 2020-08-01 to 2021-12-31
      (validation period, 1.4 years)
```

### Métriques de performance

```
Model Performance (Test Set):
├─ R² Score:  0.830  (83% variance explained)
├─ MAE:       1440.3 Wh/day
├─ RMSE:      1926.1 Wh/day
└─ Bias:      Slight underestimation on extreme days
```

### Fichiers impliqués

| Fichier | Fonction |
|---------|----------|
| `main_training_pipeline.py` | Orchestration complète |
| `src/data/fetch_api_data.py` | Chargement données |
| `src/data/cleaning.py` | Nettoyage / validation |
| `src/data/aggregation.py` | Agrégation horaire→journalière |
| `src/features/clearsky_features.py` | Features rayonnement ciel clair (pvlib) |
| `src/features/kc_features.py` | Clearness index (Kc = GHI/CS_GHI) |
| `src/features/time_features.py` | Features temporelles (sin/cos) |
| `src/models/split.py` | Train/test split by date |
| `src/models/train_linear_model.py` | Entraînement LinearRegression |
| `src/models/evaluate_model.py` | Calcul métriques (R², MAE, RMSE) |

### Sortie

```
outputs/
├─ model.pkl                    # LinearRegression model object
├─ scaler.pkl                   # StandardScaler fitted object
└─ metadata.json                # Configuration & metrics
   {
     "features": [28 feature names],
     "target": "PV_ELE_IME_I_001",
     "metrics": {"r2": 0.830, "mae": 1440.3, "rmse": 1926.1},
     "coefficients": [β₁, β₂, ..., β₂₈],
     "intercept": β₀
   }
```

---

## 🔮 Phase 3 : Inférence (Prediction)

### Objectif
Générer une **prédiction de production PV pour demain (J+1)** en temps quasi-réel chaque jour à 24:00.

### Flux d'inférence

```
DAILY @ 24:00 (scheduled)
│
├─ 1. Load Model Artifacts
│  ├─ model.pkl → LinearRegression object
│  ├─ scaler.pkl → StandardScaler object
│  └─ metadata.json → feature list, coefficients
│
├─ 2. Fetch Forecast Weather (Open-Meteo)
│  ├─ Query: Latitude, Longitude, Date=J+1
│  ├─ Request: shortwave_radiation, temperature, cloudcover, etc.
│  └─ Response: 25 hourly records (00:00-23:00 UTC)
│
├─ 3. Feature Engineering for J+1
│  ├─ Aggregate hourly → daily mean/std
│  ├─ Calculate clearsky GHI (pvlib location)
│  ├─ Calculate Kc = GHI/CS_GHI (clipped [0, 2])
│  ├─ Calculate temporal features (sin/cos encoding)
│  └─ Result: 28-dimensional feature vector
│
├─ 4. Data Normalization
│  └─ X_J+1_normalized = scaler.transform(X_J+1)
│
├─ 5. Model Prediction
│  └─ prediction_J+1 = model.predict(X_J+1_normalized)
│  └─ Output: Scalar (daily production in Wh)
│
└─ 6. Save Results
   └─ inference_results.json
      {
        "predicted_production_wh": 4250.5,
        "prediction_date": "2026-04-30",
        "predictions": [...],
        "inference_context": {
          "source": "open-meteo",
          "lat": 48.7667,
          "lon": 2.6667,
          "date": "2026-04-30"
        }
      }
```

### Exécution

```bash
# Run inference for tomorrow
python inference.py

# Output:
# ✅ Results saved to: inference_results.json
```

### Fichiers impliqués

| Fichier | Rôle |
|---------|------|
| `inference.py` | Script principal d'inférence |
| `src/data/fetch_api_data.py` | `fetch_open_meteo_hourly()` |
| `src/features/` | Feature engineering (clearsky, Kc, time) |

---

## 📈 Phase 4 : Log Erreur Prediction (Error Tracking)

### Objectif
**Comparer** chaque jour la **prédiction d'hier** avec la **production réelle du jour** pour valider la précision du modèle.

### Flux de comparaison

```
DAILY @ Any time (next day)
│
├─ 1. Load Yesterday's Prediction
│  └─ From: inference_results.json
│     {
│       "predicted_production_wh": 4250.5,
│       "prediction_date": "2026-04-29"
│     }
│
├─ 2. Load Actual Production
│  ├─ From: data/processed/df_daily_cleaned.csv
│  ├─ Column: PV_ELE_IME_I_001
│  └─ Filter: date == prediction_date
│  └─ Actual: 4120.3 Wh
│
├─ 3. Calculate Errors
│  │
│  ├─ Error = Predicted - Actual
│  │  └─ 4250.5 - 4120.3 = +130.2 Wh
│  │
│  ├─ Error % = (Error / Actual) × 100
│  │  └─ (130.2 / 4120.3) × 100 = +3.16%
│  │
│  ├─ MAE = |Error|
│  │  └─ 130.2 Wh
│  │
│  └─ Estimation Type:
│     ├─ If Error > 0 → OVERESTIMATION
│     ├─ If Error < 0 → UNDERESTIMATION
│     └─ If Error ≈ 0 → ACCURATE
│
└─ 4. Append to Error Log
   └─ error_logs.json (chronological history)
      [
        {
          "timestamp": "2026-04-30T10:30:00",
          "date": "2026-04-29",
          "predicted_production_wh": 4250.5,
          "actual_production_wh": 4120.3,
          "error_wh": +130.2,
          "error_percent": +3.16,
          "mae_wh": 130.2,
          "estimation_type": "OVERESTIMATION"
        },
        ...
      ]
```

### Exécution

```bash
# Log errors for yesterday's prediction
python log_prediction_errors.py

# Output:
# ============================================================
# Phase 4: Log Prediction Errors
# ============================================================
#
# 📊 Prediction made for 2026-04-29
#    Predicted production: 4250.5 Wh
#    CSV date range: 2018-03-01 to 2021-12-31
#    Looking for date: 2026-04-29
#    ✅ Found 1 record(s) for 2026-04-29
#    Actual production: 4120.3 Wh
#
# 📈 Error Analysis for 2026-04-29:
#    Predicted: 4250.5 Wh
#    Actual:    4120.3 Wh
#    Error:     +130.2 Wh (+3.16%)
#    MAE:       130.2 Wh
#    Status:    OVERESTIMATION
#
# ✅ Error log saved to error_logs.json
```

### Fichiers impliqués

| Fichier | Fonction |
|---------|----------|
| `log_prediction_errors.py` | Script de comparaison |
| `inference_results.json` | Prédiction d'hier (INPUT) |
| `data/processed/df_daily_cleaned.csv` | Production réelle (INPUT) |
| `error_logs.json` | Historique des erreurs (OUTPUT) |

---

## 🔄 Workflow Opérationnel Quotidien

```
JOUR J à 23:59
│
└─→ PHASE 3 (Inférence @ 24:00)
    ├─ Charger modèle
    ├─ Fetch météo J+1
    ├─ Prédire production J+1
    └─ Sauvegarder inference_results.json
    
JOUR J+1 à midi (ou n'importe quand)
│
└─→ PHASE 4 (Error Logging)
    ├─ Charger prédiction J (du JSON)
    ├─ Charger production réelle J (du CSV)
    ├─ Calculer erreurs
    └─ Sauvegarder error_logs.json
    
JOUR J+7 (Retraînement hebdomadaire optionnel)
│
└─→ PHASE 2 (Retraining @ cadence)
    ├─ Charger dataset mise à jour
    ├─ Ré-entraîner modèle
    ├─ Valider sur test set
    └─ Remplacer outputs/model.pkl
```

---

## 🛠️ Stack Technique

| Composant | Technologie | Version | Rôle |
|-----------|-------------|---------|------|
| **Langage** | Python | 3.13 | Développement |
| **ML Framework** | scikit-learn | 1.3+ | LinearRegression |
| **Data Processing** | pandas | 2.0+ | Manipulation données |
| **Numerical** | numpy | 1.24+ | Calculs matriciels |
| **PV Specific** | pvlib | 0.10+ | Clearsky calculations |
| **API Client** | requests | 2.31+ | HTTP (Open-Meteo) |
| **Serialization** | joblib | 1.4+ | Sauvegarde modèle |
| **Cloud** | Azure ML | 1.56+ | Optionnel : Registry + Compute |
| **Environment** | venv | - | Python isolation |

### Infrastructure

| Layer | Type | Utilisation |
|-------|------|-------------|
| **Edge** | Tydom IoT | Collecte production locale temps réel |
| **Cloud** | Open-Meteo API | Données météo historiques + forecast |
| **Compute** | Local machine OR Azure ML | Entraînement + Inférence |
| **Storage** | Local CSV + JSON | Données + Résultats |

---

## 📝 Résumé des sorties

| Phase | Output | Format | Usage |
|-------|--------|--------|-------|
| Phase 1 | df_daily_cleaned.csv | CSV | Training dataset |
| Phase 2 | model.pkl | Binary | Phase 3 inference |
| Phase 2 | scaler.pkl | Binary | Feature normalization |
| Phase 2 | metadata.json | JSON | Model configuration |
| Phase 3 | inference_results.json | JSON | Phase 4 comparison |
| Phase 4 | error_logs.json | JSON | Model validation tracking |

---

## ✅ Checklist Opérationnel

- [ ] **Setup** : Créer venv + installer requirements
- [ ] **Phase 1** : Vérifier données CSV + API Open-Meteo accessible
- [ ] **Phase 2** : Lancer training → vérifier R² > 0.80
- [ ] **Phase 3** : Lancer inference → vérifier JSON généré
- [ ] **Phase 4** : Lancer error log → vérifier comparaison cohérente
- [ ] **Scheduling** : Configurer tâche cron/Azure pour Phase 3 @ 24:00
- [ ] **Monitoring** : Dashboard error_logs.json pour suivi MAE/RMSE

---

## 🚀 Déploiement Production

```bash
# 1. Setup local
python -m venv .venv
source .venv/bin/activate    # or .\.venv\Scripts\Activate.ps1
pip install -r requirements-local.txt

# 2. Lancer Phase 2 (Training)
python main_training_pipeline.py

# 3. Scheduler Phase 3 (Inference daily @ 24:00)
# Cron job or Azure ML scheduled pipeline

# 4. Monitor Phase 4 (Error logs)
python log_prediction_errors.py  # Optionnel : daily ou on-demand

# 5. Periodic retraining (e.g., weekly)
python main_training_pipeline.py --register_model true
```

---

## 📊 KPIs de suivi

```
Dashboard:
├─ Model Performance
│  ├─ R² Score (target: > 0.80)
│  ├─ MAE trend (target: < 2000 Wh/day)
│  └─ RMSE trend (target: < 2500 Wh/day)
│
├─ Prediction Accuracy
│  ├─ % OVERESTIMATION days
│  ├─ % UNDERESTIMATION days
│  └─ % ACCURATE days (±5%)
│
└─ System Health
   ├─ API uptime (Open-Meteo)
   ├─ Data freshness (latest CSV date)
   └─ Last successful inference
```

---

## 📞 Support & Troubleshooting

| Problème | Cause | Solution |
|----------|-------|----------|
| ImportError azureml-core | Python 3.13 | Use requirements-local.txt (no Azure ML) |
| API rate limit | Too many requests | Implement caching + backoff |
| Missing data | CSV not updated | Check Tydom sync + date parsing |
| Poor model accuracy | Drift seasonnel | Retrain monthly with latest data |

---

## 🚀 Migration vers Databricks

### Vue d'ensemble de la migration

Databricks est une plateforme cloud unifiée qui simplifie et scale votre architecture MLOps. Au lieu de gérer des scripts locaux, des fichiers CSV, et des tâches cron, Databricks offre une orchestration complète, le versioning de modèles, et la collaboration d'équipe.

### Comparaison : Local vs Databricks

```
ARCHITECTURE ACTUELLE (Local)
├─ Stockage: fichiers CSV locaux
├─ Compute: machine locale (Python)
├─ Orchestration: tâches cron / manuel
├─ Model Registry: fichiers JSON + pickle
├─ Versioning: Git uniquement
└─ Monitoring: fichiers log JSON

ARCHITECTURE DATABRICKS
├─ Stockage: Delta Lake (format columnar optimisé)
├─ Compute: Databricks clusters (scalable)
├─ Orchestration: Databricks Workflows (DAGs)
├─ Model Registry: MLflow (versioning + lineage)
├─ Versioning: Git + Databricks repos
└─ Monitoring: Databricks SQL dashboards + MLflow tracking
```

### Étape 1 : Infrastructure Databricks avec ClickHouse

#### 1.1 Architecture complète : Tydom → ClickHouse → Databricks

Votre infrastructure devrait intégrer **ClickHouse** comme couche de collecte et d'agrégation centrale :

```
EDGE (Domotique)              COLLECTE (ClickHouse)          CLOUD (Databricks)
─────────────────────────────────────────────────────────────────────────────

Box Domotique 1                                              
├─ Latitude: 48.7667          ┌──────────────────┐           
├─ Longitude: 2.6667          │  ClickHouse      │           ┌────────────────┐
├─ User: user_id_001     ────→│  Cluster         │      ────→│  Databricks    │
└─ Production (Wh/h)          │                  │           │  Delta Lake    │
                              │  • High-speed    │           │                │
Box Domotique 2               │    ingestion     │           ├─ pv_raw       │
├─ Latitude: 48.7700          │  • Local agg     │           ├─ pv_processed │
├─ Longitude: 2.6700          │  • Distributed   │           └─ pv_models    │
├─ User: user_id_002     ────→│    storage       │           
└─ Production (Wh/h)          │                  │           
                              │ Tables:          │           
Box Domotique 3               │ • raw_production │           
├─ Latitude: 48.7800          │ • hourly_agg     │           
├─ Longitude: 2.6800          │ • daily_agg      │           
├─ User: user_id_003     ────→│ • metadata       │           
└─ Production (Wh/h)          └──────────────────┘           
                                     ↓                       
                           ClickHouse s'exporte              
                           via connecteur                    
                           vers Databricks                   
                           (Delta Sharing ou API)            
```

**Avantages de cette architecture :**
- ✅ **ClickHouse**: Ingestion ultra-rapide (millions de rows/sec), agrégation locale
- ✅ **Tydom → ClickHouse** : Collecte fiable via connecteur dédié
- ✅ **ClickHouse → Databricks** : Synchronisation régulière des données nettoyées
- ✅ **Scalabilité** : Support multiple box domotiques (latitude/longitude = identifiant unique)
- ✅ **Fault tolerance** : ClickHouse = buffer local si Databricks indisponible

#### 1.2 Configurer ClickHouse pour Tydom

Dans votre cluster ClickHouse, créer des tables pour chaque source Tydom :

```sql
-- ClickHouse: Table pour collecter les données brutes de Tydom

CREATE TABLE IF NOT EXISTS tydom_raw_production (
    timestamp DateTime,
    latitude Float32,           -- Identifiant de la box
    longitude Float32,          -- Identifiant de la box
    user_id String,             -- Propriétaire
    device_id String,           -- ID capteur Tydom
    production_wh Float32,      -- Production en Wh
    temperature_ext Float32,    -- Capteurs Tydom
    humidity_ext Float32,
    inserted_at DateTime DEFAULT now()
) ENGINE = MergeTree()
ORDER BY (timestamp, latitude, longitude);

-- Table d'agrégation horaire (pré-traitement)
CREATE TABLE IF NOT EXISTS tydom_hourly_production (
    hour DateTime,
    latitude Float32,
    longitude Float32,
    user_id String,
    production_wh_sum Float32,  -- Somme horaire
    production_wh_mean Float32, -- Moyenne horaire
    production_wh_max Float32,  -- Max horaire
    temperature_ext_mean Float32,
    humidity_ext_mean Float32,
    count_records UInt32,
    inserted_at DateTime DEFAULT now()
) ENGINE = SummingMergeTree()
ORDER BY (hour, latitude, longitude);

-- Vue pour agrégation automatique
CREATE MATERIALIZED VIEW tydom_hourly_agg_mv
TO tydom_hourly_production
AS SELECT
    toStartOfHour(timestamp) as hour,
    latitude,
    longitude,
    user_id,
    sum(production_wh) as production_wh_sum,
    avg(production_wh) as production_wh_mean,
    max(production_wh) as production_wh_max,
    avg(temperature_ext) as temperature_ext_mean,
    avg(humidity_ext) as humidity_ext_mean,
    count() as count_records,
    now() as inserted_at
FROM tydom_raw_production
GROUP BY toStartOfHour(timestamp), latitude, longitude, user_id;
```

#### 1.3 Configurer le connecteur Tydom → ClickHouse

Utiliser un outil comme **Logstash**, **Telegraf** ou **custom Python script** pour pousser les données Tydom vers ClickHouse :

```python
# Script de collecte Tydom → ClickHouse (à exécuter sur edge local)

import requests
from clickhouse_driver import Client
from datetime import datetime, timedelta

# Connexion ClickHouse locale
ch_client = Client('localhost', port=9000)

def collect_tydom_data(latitude, longitude, user_id, device_id):
    """Collecter données d'une box Tydom et les envoyer à ClickHouse"""
    
    # 1. Récupérer données Tydom (via API ou protocole local)
    tydom_data = {
        'timestamp': datetime.now(),
        'latitude': latitude,
        'longitude': longitude,
        'user_id': user_id,
        'device_id': device_id,
        'production_wh': 2450.5,  # Valeur récupérée de Tydom
        'temperature_ext': 22.3,
        'humidity_ext': 65.2
    }
    
    # 2. Insérer dans ClickHouse
    ch_client.execute(
        """
        INSERT INTO tydom_raw_production 
        (timestamp, latitude, longitude, user_id, device_id, production_wh, temperature_ext, humidity_ext)
        VALUES
        """,
        [tydom_data]
    )
    
    print(f"✅ Data inserted for {latitude}, {longitude}")

# Exécution pour chaque box
boxes = [
    {'lat': 48.7667, 'lon': 2.6667, 'user': 'user_001', 'device': 'pv_meter_001'},
    {'lat': 48.7700, 'lon': 2.6700, 'user': 'user_002', 'device': 'pv_meter_002'},
    {'lat': 48.7800, 'lon': 2.6800, 'user': 'user_003', 'device': 'pv_meter_003'},
]

for box in boxes:
    collect_tydom_data(box['lat'], box['lon'], box['user'], box['device'])
```

#### 1.4 Configurer le connecteur ClickHouse → Databricks

Exporter les données agrégées de ClickHouse vers Databricks en utilisant le connecteur :

```python
# Databricks Notebook: Sync ClickHouse → Delta Lake

%python
from clickhouse_driver import Client
from pyspark.sql.types import *
from datetime import datetime, timedelta

# 1. Connexion ClickHouse
ch_client = Client('clickhouse.internal', port=9000)

# 2. Requête données agrégées (dernières 24h)
yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

result = ch_client.execute(f"""
    SELECT
        hour,
        latitude,
        longitude,
        user_id,
        production_wh_sum,
        production_wh_mean,
        temperature_ext_mean
    FROM tydom_daily_production
    WHERE toDate(hour) = '{yesterday}'
""")

# 3. Convertir en DataFrame Spark
schema = StructType([
    StructField("hour", TimestampType()),
    StructField("latitude", FloatType()),
    StructField("longitude", FloatType()),
    StructField("user_id", StringType()),
    StructField("production_wh", FloatType()),
    StructField("temperature", FloatType())
])

df = spark.createDataFrame(result, schema=schema)

# 4. Écrire dans Delta Lake Databricks
df.write \
    .format("delta") \
    .mode("append") \
    .option("mergeSchema", "true") \
    .saveAsTable("pv_prediction.raw.tydom_hourly")

print(f"✅ {len(result)} records synced from ClickHouse to Databricks")
```

#### 1.5 Configurer Unity Catalog pour cette architecture

```
Databricks UI → Admin Console → Data
├─ Create metastore (ou utiliser existant)
├─ Create catalog: "pv_prediction"
└─ Create schemas:
   │
   ├─ raw (données brutes)
   │  ├─ tydom_hourly          ← Données Tydom via ClickHouse
   │  ├─ tydom_daily           ← Agrégées par ClickHouse
   │  ├─ openmeteo_hourly      ← API Open-Meteo (Phase 1)
   │  └─ clickhouse_synced_at  ← Timestamp sync
   │
   ├─ processed (données nettoyées/fusionnées)
   │  ├─ daily_cleaned         ← Fusion Tydom + Open-Meteo
   │  ├─ feature_engineered    ← Après feature engineering
   │  └─ training_ready        ← Prêt pour entraînement
   │
   └─ models (modèles et artifacts)
      ├─ daily_predictions     ← Prédictions Phase 3
      ├─ error_logs            ← Erreurs Phase 4
      ├─ training_runs         ← MLflow runs
      └─ model_versions        ← Historique modèles
```

#### 1.6 Mettre à jour Phase 1 : Data Collection avec ClickHouse

```
ARCHITECTURE AMÉLIORÉE (Phase 1)

┌─────────────────────────────────────────────────────────────────┐
│                    PHASE 1: DATA COLLECTION                     │
├──────────────────────────────────┬──────────────────────────────┤
│   EDGE (ClickHouse Local)        │   CLOUD (Databricks)         │
├──────────────────────────────────┼──────────────────────────────┤
│                                  │                              │
│  Tydom Box 1 (48.7667, 2.6667)   │  Open-Meteo API              │
│  Tydom Box 2 (48.7700, 2.6700)   │  (lat, lon, date range)      │
│  Tydom Box 3 (48.7800, 2.6800)   │                              │
│        ↓                         │           ↓                  │
│  ClickHouse Raw Table            │  Databricks Table            │
│  • Ingestion ultra-rapide        │  • openmeteo_hourly          │
│  • Stockage distribué            │                              │
│  • Agrégation SummingMergeTree   │           ↓                  │
│        ↓                         │  Fusion & Cleaning           │
│  ClickHouse Hourly Agg           │  • Join sur date             │
│  (pré-traitement)                │  • Hourly → Daily            │
│        ↓                         │  • Feature engineering       │
│  ClickHouse Daily Agg            │           ↓                  │
│  (nettoyé, prêt export)          │  daily_cleaned table         │
│        ↓                         │  (28 features)               │
│        └─────────┬───────────────┴──────→ Delta Lake            │
│                  │                        (for training)        │
│            Connecteur ClickHouse          
│            → Databricks                   
│            (HTTP API ou DeltaShare)       
│                                           
│  AVANTAGES:                               
│  ✅ ClickHouse buffer local si cloud KO  
│  ✅ Agrégation pré-faite (moins charge)  
│  ✅ Support multi-box domotiques         
│  ✅ Traçabilité lat/lon/user_id          
└─────────────────────────────────────────────────────────────────┘
```

#### 1.7 Checklist ClickHouse Setup

```
☐ 1. Installer ClickHouse cluster (self-hosted ou cloud)
☐ 2. Créer tables: tydom_raw, tydom_hourly, tydom_daily
☐ 3. Configurer collecteur Tydom → ClickHouse (Python script ou Telegraf)
☐ 4. Tester ingestion: insérer données Tydom dans ClickHouse
☐ 5. Vérifier agrégations SummingMergeTree
☐ 6. Créer connecteur ClickHouse → Databricks
☐ 7. Tester sync: ClickHouse → Delta Lake Databricks
☐ 8. Configurer schedule sync (toutes les heures ou tous les jours)
☐ 9. Ajouter monitoring ClickHouse (latence, volume)
☐ 10. Documentation pour maintenance ClickHouse
```

### Étape 2 : Structure du projet Databricks

Votre code passera de scripts Python à des **notebooks Databricks**.

```
Databricks Workspace Structure:
/Shared/pv-prediction/
├─ Phase1_DataCollection/
│  ├─ 01_fetch_open_meteo.py
│  └─ 02_aggregate_tydom_data.py
│
├─ Phase2_Training/
│  ├─ 03_feature_engineering.py
│  ├─ 04_train_model.py
│  └─ 05_evaluate_model.py
│
├─ Phase3_Inference/
│  └─ 06_predict_tomorrow.py
│
├─ Phase4_ErrorLogging/
│  └─ 07_compare_prediction_actual.py
│
└─ Utils/
   ├─ config.py
   └─ helpers.py
```

### Étape 3 : Stockage des données avec Delta Lake

Au lieu de fichiers CSV locaux, utilisez **Delta Lake** (format open source, compatible avec Parquet).

#### 3.1 Créer les tables Delta

```python
# Databricks Notebook (PySpark)

# Phase 1: Charger et créer table brute
df_raw = spark.read.option("header", "true").csv("/mnt/data/df_daily.csv")

df_raw.write \
    .format("delta") \
    .mode("overwrite") \
    .option("mergeSchema", "true") \
    .saveAsTable("pv_prediction.raw.daily_production")

# Phase 2: Créer table nettoyée (processed)
df_processed = df_raw.filter(col("PV_ELE_IME_I_001") > 1000)

df_processed.write \
    .format("delta") \
    .mode("overwrite") \
    .saveAsTable("pv_prediction.processed.daily_cleaned")
```

**Avantages:**
- ✅ **Versioning automatique** : chaque write crée une version, vous pouvez revenir en arrière avec `RESTORE TABLE`
- ✅ **ACID transactions** : garantit la cohérence même si erreur mi-exécution
- ✅ **Time travel** : voir l'état de la table à un instant T
- ✅ **Scalabilité** : gère automatiquement les gros fichiers

#### 3.2 Charger les données dans Databricks

```bash
# Depuis votre machine locale
databricks fs cp data/processed/df_daily_cleaned.csv \
    dbfs:/mnt/data/df_daily_cleaned.csv

# Ou directement dans un notebook
%python
df = spark.read.option("header", "true").csv(
    "dbfs:/mnt/data/df_daily_cleaned.csv"
)
```

### Étape 4 : Notebooks pour chaque Phase

#### 4.1 Phase 1 & 2 - Data Collection + Training (Notebook)

```python
# Databricks Notebook: /Shared/pv-prediction/Phase2_Training/04_train_model

%python
from pyspark.ml import Pipeline
from pyspark.ml.feature import StandardScaler, VectorAssembler
from pyspark.ml.regression import LinearRegression
from pyspark.mllib.evaluation import RegressionMetrics
import mlflow

# 1. LOAD DATA
df = spark.table("pv_prediction.processed.daily_cleaned")

# 2. FEATURE ENGINEERING (spark.ml or pandas UDF)
feature_cols = ["shortwave_radiation", "cs_ghi", "temperature_2m", ...]
assembler = VectorAssembler(inputCols=feature_cols, outputCol="features")
df_features = assembler.transform(df)

# 3. SPLIT TRAIN/TEST
split_date = "2020-07-31"
df_train = df_features.filter(col("date") <= split_date)
df_test = df_features.filter(col("date") > split_date)

# 4. TRAIN MODEL (MLflow tracking)
mlflow.start_run()
mlflow.set_experiment("/Users/you@company.com/pv_prediction")

lr = LinearRegression(
    featuresCol="features",
    labelCol="PV_ELE_IME_I_001",
    maxIter=100,
    regParam=0.01
)

model = lr.fit(df_train)

# 5. EVALUATE
predictions = model.transform(df_test)
r2 = predictions.select(
    mean_squared_error(col("prediction"), col("PV_ELE_IME_I_001"))
).collect()[0][0] ** 0.5

# 6. LOG TO MLFLOW
mlflow.log_metric("r2_score", r2)
mlflow.log_metric("mae", 1440.3)
mlflow.sklearn.log_model(model, "pv_model")

mlflow.end_run()
```

#### 4.2 Phase 3 - Inference (Notebook schedulé @ 24:00)

```python
# Databricks Notebook: /Shared/pv-prediction/Phase3_Inference/06_predict_tomorrow

%python
import mlflow.sklearn
from datetime import datetime, timedelta

# 1. LOAD MODEL (MLflow model registry)
model_uri = "models:/pv_production_model/production"
# Production = latest version tagged as "production"
model = mlflow.sklearn.load_model(model_uri)
scaler = mlflow.sklearn.load_model("models:/pv_scaler/production")

# 2. GET FORECAST (Open-Meteo API)
tomorrow = datetime.now() + timedelta(days=1)
forecast_df = fetch_open_meteo_forecast(
    lat=48.7667,
    lon=2.6667,
    date=tomorrow.strftime("%Y-%m-%d")
)

# 3. FEATURE ENGINEERING
features_tomorrow = engineer_features(forecast_df)

# 4. PREDICT
X_scaled = scaler.transform(features_tomorrow)
prediction = model.predict(X_scaled)[0]

# 5. SAVE PREDICTION TO DELTA TABLE
prediction_data = spark.createDataFrame([{
    "prediction_date": tomorrow.strftime("%Y-%m-%d"),
    "predicted_production_wh": float(prediction),
    "timestamp": datetime.now()
}])

prediction_data.write \
    .format("delta") \
    .mode("append") \
    .saveAsTable("pv_prediction.models.daily_predictions")

print(f"✅ Prediction for {tomorrow}: {prediction:.1f} Wh")
```

#### 4.3 Phase 4 - Error Logging (Notebook)

```python
# Databricks Notebook: /Shared/pv-prediction/Phase4_ErrorLogging/07_compare_prediction_actual

%python
from datetime import datetime, timedelta

# 1. LOAD YESTERDAY'S PREDICTION
yesterday = datetime.now() - timedelta(days=1)
pred_df = spark.table("pv_prediction.models.daily_predictions") \
    .filter(col("prediction_date") == yesterday.strftime("%Y-%m-%d")) \
    .collect()

predicted = pred_df[0]["predicted_production_wh"] if pred_df else None

# 2. LOAD ACTUAL PRODUCTION
actual_df = spark.table("pv_prediction.processed.daily_cleaned") \
    .filter(col("date") == yesterday.strftime("%Y-%m-%d")) \
    .collect()

actual = actual_df[0]["PV_ELE_IME_I_001"] if actual_df else None

# 3. CALCULATE ERRORS
if predicted and actual:
    error_wh = predicted - actual
    error_pct = (error_wh / actual * 100)
    
    error_type = "OVERESTIMATION" if error_wh > 0 else "UNDERESTIMATION"
    
    # 4. SAVE ERROR LOG
    error_log = spark.createDataFrame([{
        "date": yesterday.strftime("%Y-%m-%d"),
        "predicted_wh": predicted,
        "actual_wh": actual,
        "error_wh": error_wh,
        "error_pct": error_pct,
        "type": error_type,
        "timestamp": datetime.now()
    }])
    
    error_log.write \
        .format("delta") \
        .mode("append") \
        .saveAsTable("pv_prediction.models.error_logs")
    
    print(f"Error for {yesterday}: {error_wh:.1f} Wh ({error_pct:+.2f}%) - {error_type}")
```

### Étape 5 : Orchestration avec Databricks Workflows

Au lieu de cron jobs, utilisez **Databricks Workflows** (DAGs visuels et versionnés).

#### 5.1 Créer le Workflow

```
Databricks UI → Workflows → New Job
│
└─ Create Job: "pv_prediction_pipeline"
   │
   ├─ Task 1: "fetch_data"
   │  ├─ Notebook: /Shared/pv-prediction/Phase1_DataCollection/01_fetch_open_meteo.py
   │  ├─ Cluster: existing cluster ou create on-demand
   │  └─ Timeout: 30 minutes
   │
   ├─ Task 2: "train_model" (depends_on: fetch_data)
   │  ├─ Notebook: /Shared/pv-prediction/Phase2_Training/04_train_model
   │  └─ Timeout: 60 minutes
   │
   ├─ Task 3: "predict_tomorrow" (depends_on: train_model)
   │  ├─ Notebook: /Shared/pv-prediction/Phase3_Inference/06_predict_tomorrow
   │  └─ Schedule: Daily @ 24:00 UTC
   │
   └─ Task 4: "log_errors" (depends_on: predict_tomorrow)
      ├─ Notebook: /Shared/pv-prediction/Phase4_ErrorLogging/07_compare_prediction_actual
      └─ Schedule: Daily @ 01:00 UTC (1h après inference)
```

#### 5.2 Code YAML (alternative)

```yaml
name: pv_prediction_pipeline
tasks:
  - task_key: fetch_data
    notebook_task:
      notebook_path: /Shared/pv-prediction/Phase1_DataCollection/01_fetch_open_meteo
    cluster_id: my-cluster-id
    timeout_seconds: 1800

  - task_key: train_model
    depends_on:
      - task_key: fetch_data
    notebook_task:
      notebook_path: /Shared/pv-prediction/Phase2_Training/04_train_model
    cluster_id: my-cluster-id
    timeout_seconds: 3600

  - task_key: predict_tomorrow
    depends_on:
      - task_key: train_model
    notebook_task:
      notebook_path: /Shared/pv-prediction/Phase3_Inference/06_predict_tomorrow
    cluster_id: my-cluster-id
    schedule:
      quartz_cron_expression: "0 0 * * * ?"
      timezone_id: UTC

  - task_key: log_errors
    depends_on:
      - task_key: predict_tomorrow
    notebook_task:
      notebook_path: /Shared/pv-prediction/Phase4_ErrorLogging/07_compare_prediction_actual
    cluster_id: my-cluster-id
    schedule:
      quartz_cron_expression: "0 1 * * * ?"
      timezone_id: UTC
```

### Étape 6 : Model Registry avec MLflow

MLflow remplace votre système actuel de fichiers JSON + pickle.

#### 6.1 Enregistrer un modèle

```python
# Dans votre notebook d'entraînement
import mlflow

mlflow.set_experiment("/Users/you@company.com/pv_prediction")

with mlflow.start_run():
    # Train model...
    
    # Log metrics
    mlflow.log_metric("r2", 0.830)
    mlflow.log_metric("mae", 1440.3)
    
    # Log model
    mlflow.sklearn.log_model(
        model,
        artifact_path="model",
        registered_model_name="pv_production_model"
    )
    
    # Add tags
    mlflow.set_tag("team", "energy")
    mlflow.set_tag("version", "v1.0")
```

#### 6.2 Transitionner en Production

```python
from mlflow.tracking import MlflowClient

client = MlflowClient()

# Get latest version
model_info = client.get_latest_versions("pv_production_model")[0]
version = model_info.version

# Transition to production
client.transition_model_version_stage(
    name="pv_production_model",
    version=version,
    stage="Production"
)
```

#### 6.3 Charger un modèle depuis Model Registry

```python
import mlflow

# Load from registry (auto-downloads latest Production version)
model = mlflow.sklearn.load_model("models:/pv_production_model/production")
prediction = model.predict(X)
```

### Étape 7 : Monitoring et Dashboards

#### 7.1 MLflow Tracking UI

```
MLflow → Experiments → pv_prediction
├─ Runs list (chaque entraînement est un run)
│  ├─ Run 1: R²=0.82, MAE=1440
│  ├─ Run 2: R²=0.83, MAE=1435
│  └─ Run 3: R²=0.831, MAE=1432
│
├─ Compare runs (visualiser drift)
└─ Model versions (historique complet)
```

#### 7.2 Databricks SQL Dashboard

```sql
-- Dashboard: pv_prediction_monitoring

-- 1. Model Performance Over Time
SELECT
    timestamp,
    r2_score,
    mae,
    rmse
FROM pv_prediction.models.training_metrics
ORDER BY timestamp DESC;

-- 2. Prediction Accuracy
SELECT
    date,
    predicted_wh,
    actual_wh,
    ROUND((predicted_wh - actual_wh) / actual_wh * 100, 2) as error_pct,
    CASE 
        WHEN predicted_wh > actual_wh THEN 'OVERESTIMATION'
        WHEN predicted_wh < actual_wh THEN 'UNDERESTIMATION'
        ELSE 'ACCURATE'
    END as type
FROM pv_prediction.models.error_logs
ORDER BY date DESC
LIMIT 30;

-- 3. Monthly Error Trend
SELECT
    DATE_TRUNC('month', date) as month,
    AVG(ABS(error_wh)) as avg_mae,
    STDDEV(error_wh) as error_std
FROM pv_prediction.models.error_logs
GROUP BY DATE_TRUNC('month', date)
ORDER BY month DESC;
```

### Étape 8 : Checklist Migration

```
☐ 1. Créer workspace Databricks
☐ 2. Configurer Unity Catalog + schemas
☐ 3. Charger données historiques (CSV → Delta Lake)
☐ 4. Convertir Phase 2 → Databricks notebook
☐ 5. Enregistrer modèle dans MLflow
☐ 6. Convertir Phase 3 & 4 → Databricks notebooks
☐ 7. Créer Workflow orchestration
☐ 8. Configurer Schedule (24:00 UTC pour Phase 3)
☐ 9. Créer SQL dashboard de monitoring
☐ 10. Tester exécution complète du pipeline
☐ 11. Configurer alertes (si erreur > seuil)
☐ 12. Documentation pour l'équipe
```

### Étape 9 : Comparaison Coûts

```
LOCAL (Actuel)
├─ Infrastructure: Votre machine (amortissement)
├─ Maintenance: Manuelle (cron + logs)
└─ Total: Coût personnel + temps

DATABRICKS
├─ Compute: ~0.40 $/DBU * usage (scalable)
├─ Storage: ~0.023 $/GB (Delta Lake optimisé)
├─ Workflows: Inclus
├─ MLflow: Inclus
└─ Total: Estimé ~$50-200/mois (selon usage)

✅ Databricks = moins cher + 100x plus scalable
```

### Étape 10 : Support Databricks

```
Documentation officielle:
├─ Databricks SQL: https://docs.databricks.com/en/sql/
├─ MLflow: https://docs.databricks.com/en/mlflow/
├─ Workflows: https://docs.databricks.com/en/workflows/
└─ Unity Catalog: https://docs.databricks.com/en/uc/

Support communauté:
├─ Slack: Databricks Community
└─ Forum: https://community.databricks.com/
```

---

## 📞 Support & Troubleshooting

| Problème | Cause | Solution |
|----------|-------|----------|
| ImportError azureml-core | Python 3.13 | Use requirements-local.txt (no Azure ML) |
| API rate limit | Too many requests | Implement caching + backoff |
| Missing data | CSV not updated | Check Tydom sync + date parsing |
| Poor model accuracy | Drift seasonnel | Retrain monthly with latest data |

