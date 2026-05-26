# Architecture Databricks Intégrée (Enterprise)

> **Alternative plus complète** : Utiliser TOUS les services Databricks comme plateforme unifiée

## 📊 Vue d'ensemble intégrée

Cette approche utilise chaque composant Databricks de manière coordonnée :

```
┌────────────────────────────────────────────────────────────────────────┐
│                     DATABRICKS WORKSPACE UNIFIÉE                       │
├────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │ 1. REPOS (Git Integration)                                      │  │
│  │    /Repos/github/your-org/pv-prediction                         │  │
│  │    ├── notebooks/           ← Databricks notebooks             │  │
│  │    ├── src/                 ← Code Python modules              │  │
│  │    ├── tests/               ← Unit tests                       │  │
│  │    └── configs/             ← Configuration files              │  │
│  └─────────────────────────────────────────────────────────────────┘  │
│                              │                                         │
│  ┌──────────────────────────▼─────────────────────────────────────┐  │
│  │ 2. WORKSPACE NOTEBOOKS (Orchestration)                         │  │
│  │    /Shared/pv-prediction/                                      │  │
│  │    ├── Utilities/           ← Modules réutilisables            │  │
│  │    ├── Phase1_DataCollection/                                  │  │
│  │    ├── Phase2_Training/                                        │  │
│  │    ├── Phase3_Inference/                                       │  │
│  │    └── Phase4_ErrorTracking/                                   │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                              │                                         │
│  ┌──────────────────────────▼─────────────────────────────────────┐  │
│  │ 3. COMPUTE (Cluster Management)                                │  │
│  │    ├─ pv-prediction-prod (Auto-scaling)                        │  │
│  │    │  • Worker type: i3.xlarge (4-8 nodes)                     │  │
│  │    │  • Auto-terminate: 30 min                                 │  │
│  │    │  • For jobs orchestration                                 │  │
│  │    │                                                            │  │
│  │    ├─ pv-prediction-sql (SQL Warehouse)                        │  │
│  │    │  • 4 Pro cores (OLAP queries)                             │  │
│  │    │  • For dashboards + SQL queries                           │  │
│  │    │  • Always ON                                              │  │
│  │    │                                                            │  │
│  │    └─ Instance pools (cost optimization)                       │  │
│  │       • Pre-warmed instances for fast startup                  │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                              │                                         │
│  ┌──────────────────────────▼─────────────────────────────────────┐  │
│  │ 4. UNITY CATALOG (Data Governance)                             │  │
│  │    pv_prediction (Catalog)                                     │  │
│  │    ├── raw (Schema)                                            │  │
│  │    │   ├── tydom_production_hourly (via ClickHouse)           │  │
│  │    │   └── openmeteo_hourly (from API)                        │  │
│  │    │                                                            │  │
│  │    ├── processed (Schema)                                      │  │
│  │    │   ├── daily_cleaned (merged + cleaned)                   │  │
│  │    │   ├── features_engineered (28 features)                  │  │
│  │    │   └── train_test_split (split by date)                   │  │
│  │    │                                                            │  │
│  │    └── models (Schema)                                         │  │
│  │        ├── predictions_history (daily predictions)            │  │
│  │        ├── error_logs (tracking)                              │  │
│  │        └── model_metadata (versions)                          │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                              │                                         │
│  ┌──────────────────────────▼─────────────────────────────────────┐  │
│  │ 5. MLFLOW (Model Registry)                                     │  │
│  │    Registry URI: databricks-uc (Unity Catalog)                │  │
│  │    ├── Model: pv_linear_regression                             │  │
│  │    │   ├── Version 1 (Prod)  ← Deployed to inference           │  │
│  │    │   ├── Version 2 (Stage) ← Testing before prod             │  │
│  │    │   └── Version 3 (Dev)   ← Latest training                 │  │
│  │    │                                                            │  │
│  │    └── Experiment tracking (auto)                              │  │
│  │        └── Store runs, metrics, artifacts                      │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                              │                                         │
│  ┌──────────────────────────▼─────────────────────────────────────┐  │
│  │ 6. SECRETS MANAGEMENT                                          │  │
│  │    Scope: pv_prediction_secrets                                │  │
│  │    ├── clickhouse_host                                         │  │
│  │    ├── clickhouse_password                                     │  │
│  │    ├── api_keys (Open-Meteo if premium)                       │  │
│  │    └── service_account_tokens                                  │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                              │                                         │
│  ┌──────────────────────────▼─────────────────────────────────────┐  │
│  │ 7. JOBS & WORKFLOWS (Orchestration)                            │  │
│  │    ├─ pv-prediction-daily-pipeline (Scheduled)                 │  │
│  │    │  ├── Phase1_DataCollection                                │  │
│  │    │  ├── Phase3_Inference (@ 24:00)                           │  │
│  │    │  └── Phase4_ErrorTracking                                 │  │
│  │    │                                                            │  │
│  │    └─ pv-prediction-weekly-retrain (Monday 02:00)              │  │
│  │       └── Phase2_Training only                                 │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                              │                                         │
│  ┌──────────────────────────▼─────────────────────────────────────┐  │
│  │ 8. SQL & DASHBOARDS                                            │  │
│  │    SQL Warehouse: pv-prediction-sql                            │  │
│  │    ├─ Dashboard 1: Data Quality Monitor                        │  │
│  │    ├─ Dashboard 2: Model Performance                           │  │
│  │    ├─ Dashboard 3: Predictions Accuracy                        │  │
│  │    └─ Dashboard 4: Error Analysis                              │  │
│  │                                                                 │  │
│  │    Shared Queries (for team)                                   │  │
│  │    ├─ Daily data ingestion check                               │  │
│  │    ├─ Model metrics evolution                                  │  │
│  │    └─ Prediction accuracy by date                              │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                              │                                         │
│  ┌──────────────────────────▼─────────────────────────────────────┐  │
│  │ 9. ALERTS & MONITORING                                         │  │
│  │    ├─ Data Quality Alert                                       │  │
│  │    │  If ingestion fails or coverage < 90%                     │  │
│  │    │  → Email to data-team@company.com                         │  │
│  │    │                                                            │  │
│  │    ├─ Model Alert                                              │  │
│  │    │  If MAE > 2000 Wh                                         │  │
│  │    │  → Slack + Email + Trigger manual retraining              │  │
│  │    │                                                            │  │
│  │    ├─ Pipeline Alert                                           │  │
│  │    │  If job fails                                             │  │
│  │    │  → Escalation protocol                                    │  │
│  │    │                                                            │  │
│  │    └─ Cost Optimization                                        │  │
│  │       Monitor cluster usage + auto-scale config                │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 🛠️ Architecture ClickHouse → Databricks intégrée

### Flux complet de données

```
EDGE (Domotique)             COLLECTE (ClickHouse)        CLOUD (Databricks)
────────────────────────────────────────────────────────────────────────────

Box Tydom 1              ┌──────────────────┐
├─ Lat: 48.7667    ────→│  ClickHouse      │              ┌──────────────┐
├─ Lon: 2.6667          │  Cluster         │         ────→│ Unity Cat.   │
├─ User: user_001   │   │                  │             │ pv_prediction│
└─ Prod: Wh/h       │   │  Tables:         │              │              │
                    │   │  • raw_prod      │              ├─ raw         │
Box Tydom 2         │   │  • hourly_agg    │              │ • tydom_hour │
├─ Lat: 48.7700    ────→│  • daily_agg     │        ────→│ • om_hour    │
├─ Lon: 2.6700          │                  │              │              │
├─ User: user_002   │   │  Features:       │              ├─processed    │
└─ Prod: Wh/h       │   │  • Aggregation   │              │ • cleaned    │
                    │   │  • Cleansing     │              │ • features   │
Box Tydom 3         │   │  • Dedup         │              │              │
├─ Lat: 48.7800    ────→│                  │              ├─models       │
├─ Lon: 2.6800          │                  │              │ • predictions│
├─ User: user_003   │   └──────────────────┘              │ • errors     │
└─ Prod: Wh/h       │          ↓                           └──────────────┘
                    │   ClickHouse Connector
                    │   • HTTP API
                    │   • Delta Sharing
                    │   • Python clickhouse-driver
                    │   Exécution: Hebdomadaire
                    │   ou Daily @ 01:00 UTC
                    └──────→ Databricks

Open-Meteo API ─────────────────→ Databricks (Direct HTTP)
```

### Intégration ClickHouse dans Databricks

**1. Configuration des secrets ClickHouse**

```python
# Databricks Workspace: Secrets

# CLI: databricks secrets create-scope --scope pv_prediction_secrets

# Ajouter credentials
databricks secrets put --scope pv_prediction_secrets \
  --key clickhouse_host --string-value "192.168.x.x ou clickhouse.company.com"

databricks secrets put --scope pv_prediction_secrets \
  --key clickhouse_port --string-value "9000"

databricks secrets put --scope pv_prediction_secrets \
  --key clickhouse_user --string-value "default"

databricks secrets put --scope pv_prediction_secrets \
  --key clickhouse_password --string-value "***"
```

**2. Notebook pour lire ClickHouse**

```python
# Databricks Notebook: /Shared/pv-prediction/Phase1_DataCollection/01_read_tydom_from_clickhouse

%python
from clickhouse_driver import Client
from datetime import datetime, timedelta
import pandas as pd

# Configuration depuis secrets
ch_host = dbutils.secrets.get(scope="pv_prediction_secrets", key="clickhouse_host")
ch_port = int(dbutils.secrets.get(scope="pv_prediction_secrets", key="clickhouse_port"))
ch_user = dbutils.secrets.get(scope="pv_prediction_secrets", key="clickhouse_user")
ch_password = dbutils.secrets.get(scope="pv_prediction_secrets", key="clickhouse_password")

# Connexion
client = Client(host=ch_host, port=ch_port, user=ch_user, password=ch_password)

# Récupérer derniers 7 jours (data buffer)
seven_days_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

query = f"""
SELECT
    hour,
    latitude,
    longitude,
    user_id,
    device_id,
    production_wh_sum,
    production_wh_mean,
    temperature_ext_mean,
    count_records
FROM pv_data.tydom_daily_production
WHERE hour >= '{seven_days_ago}'
ORDER BY hour DESC
"""

print(f"📡 Querying ClickHouse: {ch_host}")
result = client.execute(query)

# Convertir en Spark DataFrame
df_pandas = pd.DataFrame(result, columns=[
    "hour", "latitude", "longitude", "user_id", "device_id",
    "production_wh_sum", "production_wh_mean", "temperature_ext_mean", "count"
])

df = spark.createDataFrame(df_pandas)

# Écrire dans Delta Lake
df.write \
    .format("delta") \
    .mode("append") \
    .saveAsTable("pv_prediction.raw.tydom_production_daily")

print(f"✅ {len(result)} records from ClickHouse → Databricks")

client.disconnect()
```

---

## 📋 1. REPOS + Git Integration

Structure complète dans Git :

```
github.com/your-org/pv-prediction
├── .github/workflows/     ← CI/CD
│   ├── test.yml
│   └── lint.yml
│
├── notebooks/
│   ├── Phase1_DataCollection/
│   │   ├── 01_read_tydom_from_clickhouse.py
│   │   ├── 02_collect_openmeteo_historical.py
│   │   ├── 03_merge_and_aggregate.py
│   │   └── 04_data_quality_checks.py
│   │
│   ├── Phase2_Training/
│   │   ├── 01_feature_engineering.py
│   │   ├── 02_train_linear_model.py
│   │   ├── 03_evaluate_model.py
│   │   └── 04_register_model_mlflow.py
│   │
│   ├── Phase3_Inference/
│   │   ├── 01_prepare_inference_data.py
│   │   ├── 02_load_model_predict.py
│   │   └── 03_save_predictions.py
│   │
│   └── Phase4_ErrorTracking/
│       ├── 01_compare_predictions_actual.py
│       ├── 02_calculate_metrics.py
│       └── 03_log_errors.py
│
├── src/                   ← Modules réutilisables
│   ├── __init__.py
│   ├── config/
│   │   ├── __init__.py
│   │   └── databricks_config.py
│   │
│   ├── data/
│   │   ├── __init__.py
│   │   ├── aggregation.py
│   │   ├── cleaning.py
│   │   ├── load_dataset.py
│   │   └── clickhouse_connector.py
│   │
│   ├── features/
│   │   ├── __init__.py
│   │   ├── clearsky_features.py
│   │   ├── kc_features.py
│   │   └── time_features.py
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── train_linear_model.py
│   │   ├── evaluate_model.py
│   │   ├── split.py
│   │   └── predict.py
│   │
│   └── utils/
│       ├── __init__.py
│       ├── validation.py
│       └── logging_utils.py
│
├── tests/
│   ├── __init__.py
│   ├── test_data_quality.py
│   ├── test_model.py
│   └── test_inference.py
│
├── sql/
│   ├── schema_definition.sql
│   ├── dashboards_queries.sql
│   └── data_quality_checks.sql
│
├── configs/
│   ├── databricks_config.yml
│   ├── model_config.yml
│   └── data_config.yml
│
├── README.md
├── requirements.txt
├── setup.py
└── .gitignore
```

**Avantages:**
- ✅ Version control complet
- ✅ Pull requests + code review
- ✅ Branches: dev/staging/prod
- ✅ Traçabilité = qui a changé quoi et pourquoi

---

## 🗄️ 2. UNITY CATALOG (Data Governance)

### Créer le catalogue

```sql
-- Databricks SQL

-- 1. Catalog principal
CREATE CATALOG IF NOT EXISTS pv_prediction
COMMENT 'PV Production Forecasting - Complete MLOps Pipeline'
OWNER = 'data_platform_team@company.com';

-- 2. Schemas avec isolation
CREATE SCHEMA IF NOT EXISTS pv_prediction.raw
COMMENT 'Raw data from ClickHouse and Open-Meteo API'
OWNER = 'data_eng_team@company.com';

CREATE SCHEMA IF NOT EXISTS pv_prediction.processed
COMMENT 'Cleaned, aggregated, feature-engineered data'
OWNER = 'ml_team@company.com';

CREATE SCHEMA IF NOT EXISTS pv_prediction.models
COMMENT 'ML models, predictions, metrics'
OWNER = 'ml_team@company.com';

CREATE SCHEMA IF NOT EXISTS pv_prediction.monitoring
COMMENT 'Monitoring tables and logs'
OWNER = 'ops_team@company.com';
```

### Créer les tables

```sql
-- 3. Table brute: Tydom depuis ClickHouse
CREATE TABLE IF NOT EXISTS pv_prediction.raw.tydom_production_hourly (
    timestamp TIMESTAMP NOT NULL,
    latitude FLOAT,
    longitude FLOAT,
    user_id STRING,
    device_id STRING,
    production_wh FLOAT,
    temperature FLOAT,
    quality_flag STRING,
    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
)
USING DELTA
PARTITIONED BY (month(timestamp))
TBLPROPERTIES (
    'delta.enableChangeDataFeed' = 'true',
    'delta.retentionDays' = '2555'  -- 7 years
);

-- 4. Table: Open-Meteo
CREATE TABLE IF NOT EXISTS pv_prediction.raw.openmeteo_hourly (
    timestamp TIMESTAMP NOT NULL,
    latitude FLOAT,
    longitude FLOAT,
    shortwave_radiation FLOAT,
    direct_radiation FLOAT,
    diffuse_radiation FLOAT,
    temperature_2m FLOAT,
    cloudcover FLOAT,
    windspeed_10m FLOAT,
    pressure_msl FLOAT,
    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
)
USING DELTA
PARTITIONED BY (month(timestamp));

-- 5. Table nettoyée (Production)
CREATE TABLE IF NOT EXISTS pv_prediction.processed.daily_cleaned (
    date DATE,
    production_wh_daily FLOAT,
    production_wh_mean FLOAT,
    production_wh_max FLOAT,
    production_wh_std FLOAT,
    shortwave_radiation_mean FLOAT,
    direct_radiation_mean FLOAT,
    temperature_2m_mean FLOAT,
    cloudcover_mean FLOAT,
    windspeed_10m_mean FLOAT,
    latitude FLOAT,
    longitude FLOAT,
    user_id STRING,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
)
USING DELTA
PARTITIONED BY (year(date), month(date))
CLUSTERED BY (user_id) INTO 4 BUCKETS
TBLPROPERTIES (
    'delta.enableChangeDataFeed' = 'true',
    'delta.targetFileSize' = '134217728'
);

-- 6. Prédictions
CREATE TABLE IF NOT EXISTS pv_prediction.models.predictions_history (
    prediction_date DATE,
    predicted_production_wh FLOAT,
    actual_production_wh FLOAT,
    error_wh FLOAT,
    error_percent FLOAT,
    model_version STRING,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
)
USING DELTA
PARTITIONED BY (year(prediction_date));

-- 7. Erreurs
CREATE TABLE IF NOT EXISTS pv_prediction.models.error_logs (
    log_date TIMESTAMP,
    prediction_date DATE,
    error_wh FLOAT,
    error_percent FLOAT,
    estimation_type STRING,
    model_version STRING,
    notes STRING
)
USING DELTA
PARTITIONED BY (month(log_date));

-- 8. Permissions
GRANT SELECT ON SCHEMA pv_prediction.raw TO `data_analysts@company.com`;
GRANT SELECT ON SCHEMA pv_prediction.processed TO `ml_team@company.com`;
GRANT SELECT, MODIFY ON SCHEMA pv_prediction.models TO `ml_team@company.com`;
GRANT SELECT ON SCHEMA pv_prediction.monitoring TO `ops_team@company.com`;
```

---

## 💻 3. COMPUTE (Clusters + SQL Warehouses)

### Cluster pour orchestration

```yaml
# Databricks UI > Compute > Create Cluster

Cluster Name: pv-prediction-prod
Databricks Runtime: 14.3 LTS
Cluster Mode: All-purpose

Worker Config:
  node_type_id: i3.xlarge        # 4 vCores, 30.5 GB RAM
  num_workers: 4                 # Min: 2, Max: 8 (auto-scaling)
  
Driver:
  node_type_id: i3.xlarge

Advanced:
  auto_termination_minutes: 30
  enable_elastic_disk: true
  
Spark Config:
  spark.databricks.delta.preview.enabled: true
  spark.sql.shuffle.partitions: 200
  
Init Scripts:
  - /Workspace/Shared/pv-prediction/init_scripts/setup.sh
  
Instance Pool: pv-prediction-pool  (optional, for faster startup)

Tags:
  - environment: production
  - team: ml
  - cost-center: analytics
```

**Script init (setup.sh):**

```bash
#!/bin/bash
# Install packages
pip install --quiet \
    clickhouse-driver==0.2.8 \
    pvlib==0.10.2 \
    requests==2.31.0 \
    mlflow==2.10.0

# Log success
echo "✅ Init scripts completed at $(date)"
```

### SQL Warehouse pour dashboards

```yaml
# Databricks UI > SQL > SQL Warehouses > Create

Name: pv-prediction-sql
Cluster Size: 4 cores (medium)
Auto-stop Minutes: 15
Enable Photon: true          # Fast analytics
Max Connections: 50
Tags:
  - environment: production
  - team: analytics
```

---

## 🏛️ 4. MLflow Model Registry

Gérer les modèles de manière centralisée :

```python
# Databricks Notebook: Phase2_Training/04_register_model_mlflow

%python
import mlflow
import mlflow.sklearn
from sklearn.linear_model import LinearRegression
from sklearn.metrics import r2_score, mean_absolute_error

# Configuration
mlflow.set_registry_uri("databricks-uc")  # Unity Catalog
mlflow.set_experiment("/Shared/pv-prediction/Phase2_Training/experiments")

# Training
with mlflow.start_run(run_name="linear_regression_v2_retrain") as run:
    
    # Params
    mlflow.log_params({
        "model_type": "LinearRegression",
        "features_count": len(feature_cols),
        "train_samples": len(X_train),
        "split_date": "2020-07-31"
    })
    
    # Train
    model = LinearRegression()
    model.fit(X_train, y_train)
    
    # Evaluate
    y_pred = model.predict(X_test)
    r2 = r2_score(y_test, y_pred)
    mae = mean_absolute_error(y_test, y_pred)
    
    # Log metrics
    mlflow.log_metrics({
        "r2_score": r2,
        "mae": mae,
        "rmse": np.sqrt(np.mean((y_test - y_pred) ** 2))
    })
    
    # Log model
    mlflow.sklearn.log_model(model, "model")
    mlflow.log_artifact("metadata.json")
    
    # Register to MLflow Registry
    model_uri = f"runs:/{run.info.run_id}/model"
    registered_model = mlflow.register_model(
        model_uri=model_uri,
        name="pv_linear_regression"
    )

# Transition to Staging (for testing)
client = mlflow.tracking.MlflowClient()
client.transition_model_version_stage(
    name="pv_linear_regression",
    version=registered_model.version,
    stage="Staging"
)

print(f"✅ Model registered: {registered_model.name} v{registered_model.version}")

# In a few days, after validation:
# client.transition_model_version_stage(
#     name="pv_linear_regression",
#     version=registered_model.version,
#     stage="Production"
# )
```

**Lifecycle dans MLflow:**

```
Development  ──→  Staging  ──→  Production
├─ New runs       ├─ Test        ├─ Inference
├─ Fresh data     ├─ Validation  ├─ Active
└─ Latest tests   └─ A/B compare └─ Serving
```

---

## 📅 5. JOBS & WORKFLOWS (Orchestration)

### Workflow 1: Daily Pipeline

```yaml
# Databricks UI > Workflows > Create Job

name: pv-prediction-daily-pipeline
description: Collecte données, inférence, suivi erreurs
trigger:
  pause_status: UNPAUSED
  schedule:
    quartz_cron_expression: "0 1 * * * ?"  # Daily 01:00 UTC
    timezone_id: UTC

tasks:
  # ===== PHASE 1: Data Collection =====
  - task_key: phase1_read_clickhouse
    notebook_task:
      notebook_path: /Shared/pv-prediction/Phase1_DataCollection/01_read_tydom_from_clickhouse
    cluster_id: {{ cluster_id }}
    timeout_seconds: 600
    max_retries: 2
    
  - task_key: phase1_openmeteo
    notebook_task:
      notebook_path: /Shared/pv-prediction/Phase1_DataCollection/02_collect_openmeteo_historical
    cluster_id: {{ cluster_id }}
    timeout_seconds: 1200
    depends_on: [{ task_key: phase1_read_clickhouse }]
    
  - task_key: phase1_merge
    notebook_task:
      notebook_path: /Shared/pv-prediction/Phase1_DataCollection/03_merge_and_aggregate
    cluster_id: {{ cluster_id }}
    timeout_seconds: 300
    depends_on: [{ task_key: phase1_openmeteo }]
    
  - task_key: phase1_quality
    notebook_task:
      notebook_path: /Shared/pv-prediction/Phase1_DataCollection/04_data_quality_checks
    cluster_id: {{ cluster_id }}
    timeout_seconds: 300
    depends_on: [{ task_key: phase1_merge }]
    
  # ===== PHASE 3: Inference @ 24:00 =====
  - task_key: phase3_prepare
    notebook_task:
      notebook_path: /Shared/pv-prediction/Phase3_Inference/01_prepare_inference_data
    cluster_id: {{ cluster_id }}
    timeout_seconds: 300
    depends_on: [{ task_key: phase1_quality }]
    
  - task_key: phase3_predict
    notebook_task:
      notebook_path: /Shared/pv-prediction/Phase3_Inference/02_load_model_predict
    cluster_id: {{ cluster_id }}
    timeout_seconds: 300
    depends_on: [{ task_key: phase3_prepare }]
    
  - task_key: phase3_save
    notebook_task:
      notebook_path: /Shared/pv-prediction/Phase3_Inference/03_save_predictions
    cluster_id: {{ cluster_id }}
    timeout_seconds: 300
    depends_on: [{ task_key: phase3_predict }]
    
  # ===== PHASE 4: Error Tracking =====
  - task_key: phase4_compare
    notebook_task:
      notebook_path: /Shared/pv-prediction/Phase4_ErrorTracking/01_compare_predictions_actual
    cluster_id: {{ cluster_id }}
    timeout_seconds: 300
    depends_on: [{ task_key: phase3_save }]
    
  - task_key: phase4_log
    notebook_task:
      notebook_path: /Shared/pv-prediction/Phase4_ErrorTracking/03_log_errors
    cluster_id: {{ cluster_id }}
    timeout_seconds: 300
    depends_on: [{ task_key: phase4_compare }]

# Notifications
on_failure:
  - email_addresses: [ml-team@company.com, data-eng@company.com]

timeout_seconds: 7200  # 2 hours max
max_concurrent_runs: 1
```

### Workflow 2: Weekly Retraining

```yaml
name: pv-prediction-weekly-retrain
trigger:
  schedule:
    quartz_cron_expression: "0 2 ? * MON"  # Monday 02:00 UTC
    timezone_id: UTC

tasks:
  - task_key: feature_eng
    notebook_task:
      notebook_path: /Shared/pv-prediction/Phase2_Training/01_feature_engineering
    cluster_id: {{ cluster_id }}
    timeout_seconds: 600
    
  - task_key: train
    notebook_task:
      notebook_path: /Shared/pv-prediction/Phase2_Training/02_train_linear_model
    cluster_id: {{ cluster_id }}
    timeout_seconds: 1800
    depends_on: [{ task_key: feature_eng }]
    
  - task_key: evaluate
    notebook_task:
      notebook_path: /Shared/pv-prediction/Phase2_Training/03_evaluate_model
    cluster_id: {{ cluster_id }}
    timeout_seconds: 600
    depends_on: [{ task_key: train }]
    
  - task_key: register
    notebook_task:
      notebook_path: /Shared/pv-prediction/Phase2_Training/04_register_model_mlflow
    cluster_id: {{ cluster_id }}
    timeout_seconds: 300
    depends_on: [{ task_key: evaluate }]

on_failure:
  - email_addresses: [ml-team@company.com]
```

---

## 📊 6. SQL Dashboards

### Dashboard 1: Data Quality Monitor

```sql
-- Databricks SQL: Data Quality Dashboard

SELECT
    DATE(ingested_at) as collection_date,
    COUNT(*) as total_records,
    COUNT(DISTINCT device_id) as device_count,
    MIN(timestamp) as earliest_record,
    MAX(timestamp) as latest_record,
    COUNT(CASE WHEN quality_flag != 'OK' THEN 1 END) as quality_issues,
    ROUND(100.0 * COUNT(*) / 24 / COUNT(DISTINCT device_id), 1) as coverage_percent
FROM pv_prediction.raw.tydom_production_hourly
WHERE DATE(ingested_at) >= DATE_SUB(CURRENT_DATE(), 30)
GROUP BY DATE(ingested_at)
ORDER BY collection_date DESC
LIMIT 50;
```

### Dashboard 2: Model Performance

```sql
-- Databricks SQL: Model Performance

SELECT
    DATE(prediction_date) as date,
    COUNT(*) as predictions,
    ROUND(AVG(ABS(error_wh)), 0) as avg_error_wh,
    ROUND(MAX(ABS(error_wh)), 0) as max_error_wh,
    ROUND(AVG(error_percent), 2) as avg_error_pct,
    SUM(CASE WHEN ABS(error_percent) < 10 THEN 1 ELSE 0 END) as accurate_count,
    ROUND(100.0 * SUM(CASE WHEN ABS(error_percent) < 10 THEN 1 ELSE 0 END) / COUNT(*), 1) as accuracy_pct
FROM pv_prediction.models.predictions_history
WHERE DATE(prediction_date) >= DATE_SUB(CURRENT_DATE(), 90)
GROUP BY DATE(prediction_date)
ORDER BY date DESC;
```

---

## 🚨 7. Alerts & Monitoring

```python
# Databricks SQL > Alerts > Create Alert

Alert 1: Data Ingestion Health
Query: SELECT COUNT(*) as record_count FROM pv_prediction.raw.tydom_production_hourly WHERE DATE(timestamp) = CURRENT_DATE()
Trigger: if record_count < 50
Notification: Email to data-eng@company.com

Alert 2: Model Accuracy Degradation
Query: SELECT AVG(ABS(error_percent)) as avg_error FROM pv_prediction.models.predictions_history WHERE DATE(prediction_date) >= DATE_SUB(CURRENT_DATE(), 7)
Trigger: if avg_error > 15
Notification: Slack + Email + Trigger manual retraining

Alert 3: Pipeline Failure
Source: Databricks Job notifications
Trigger: if job status = FAILED
Notification: Escalation to ops-team@company.com
```

---

## 🔒 8. Secrets Management

```bash
# CLI: Gérer credentials

# Créer scope
databricks secrets create-scope --scope pv_prediction_secrets

# Ajouter credentials
databricks secrets put --scope pv_prediction_secrets --key clickhouse_host
databricks secrets put --scope pv_prediction_secrets --key clickhouse_password
databricks secrets put --scope pv_prediction_secrets --key api_keys

# Utiliser dans notebooks
dbutils.secrets.get(scope="pv_prediction_secrets", key="clickhouse_host")

# JAMAIS hardcoder credentials !
```

---

## 📝 Résumé : Phase-par-Phase vs Enterprise

| Aspect | Simple | Enterprise |
|--------|--------|-----------|
| Code source | Local notebooks | Git + Databricks Repos |
| Gestion données | Tables Delta simples | Unity Catalog (governance) |
| Compute | 1 cluster | Multi-cluster + pools |
| Secrets | Hardcoded ❌ | dbutils.secrets ✅ |
| Models | Pickle files | MLflow Registry ✅ |
| Orchestration | 1 workflow | Multi-workflows |
| Monitoring | Logs manuels | Dashboards SQL ✅ |
| Alerts | Aucun | Databricks Alerts ✅ |
| Team collaboration | Difficile | Pull requests ✅ |
| Cost optimization | Basique | Auto-scaling, pools |
| Production-ready | 50% | 100% |

---

## 🎯 Quelle approche choisir ?

### ✅ Approche Enterprise (intégrée) si :
- Vous avez une **équipe de 3+ personnes**
- Vous besoin de **production-grade reliability**
- Vous gérez **multi-sites** (plusieurs box domotiques)
- Vous voulez **monitoring** automatisé
- Vous avez **budget cloud** dédié

### ✅ Approche Simple (Phase-par-Phase) si :
- Vous commencez (POC)
- Vous êtes **1-2 personnes**
- Vous prioritisez **rapid prototyping**
- Budget limité
- Pas (encore) de requirements enterprise

---

## 🚀 Migration Checklist (Enterprise)

```markdown
### PHASE 1: Foundation Setup (Week 1)
- [ ] Créer Databricks workspace
- [ ] Configurer Unity Catalog + 3 schemas
- [ ] Créer cluster prod + SQL warehouse
- [ ] Configurer Git Repos
- [ ] Setup secrets scope

### PHASE 2: Code Migration (Week 2-3)
- [ ] Importer code depuis Git
- [ ] Adapter modules src/ pour Databricks
- [ ] Créer notebooks Phase1-4
- [ ] Tester chaque notebook manuellement

### PHASE 3: Data Integration (Week 2-3)
- [ ] ClickHouse setup (Tydom) OK
- [ ] ClickHouse connector ready
- [ ] Première sync ClickHouse → Databricks
- [ ] Valider Delta Lake tables

### PHASE 4: MLflow Setup (Week 3)
- [ ] MLflow Registry activated
- [ ] Model versioning en place
- [ ] Experiment tracking OK

### PHASE 5: Orchestration (Week 4)
- [ ] Daily workflow créé et testé
- [ ] Weekly retrain workflow créé
- [ ] Schedules activés
- [ ] Notifications configurées

### PHASE 6: Monitoring (Week 4)
- [ ] Dashboards créés
- [ ] Alerts configurées
- [ ] Email notifications testées
- [ ] Slack integration (optional)

### PHASE 7: Documentation & Team Training (Week 5)
- [ ] README complet
- [ ] Team training session
- [ ] Runbooks pour escalation
- [ ] Go-live !
```

C'est l'approche **enterprise-grade**. Vous voulez que je crée les notebooks détaillés pour cette architecture ? 🚀
