# Guide Complet: Organiser Votre Projet sur Databricks

> Comment transformer votre architecture locale en infrastructure cloud Databricks complète

## 🗺️ Vue d'ensemble: Transformation de votre projet

```
AVANT (Local/Azure ML)                APRÈS (Databricks Cloud)
─────────────────────────────────────────────────────────────

Fichiers CSV locaux        →    Unity Catalog (Delta Lake)
├─ df_daily_cleaned.csv   →    ├─ pv_prediction.raw.tydom_hourly
├─ model.pkl              →    ├─ pv_prediction.raw.openmeteo_hourly
└─ inference_results.json →    └─ pv_prediction.processed.daily_cleaned

Scripts Python             →    Repos + Notebooks
├─ main_training_pipeline →    ├─ /Repos/your-org/pv-prediction/src/
├─ inference.py           →    ├─ /Shared/pv-prediction/notebooks/
└─ log_prediction_errors  →    └─ Modules réutilisables

Tâches cron               →    Databricks Workflows
├─ Phase 3 @ 24:00       →    ├─ Daily pipeline (01:00 UTC)
└─ Phase 2 manuel        →    └─ Weekly retrain (02:00 UTC Monday)

Stockage modèle           →    MLflow Model Registry
├─ outputs/model.pkl     →    ├─ pv_linear_regression v1 (Prod)
└─ metadata.json         →    ├─ pv_linear_regression v2 (Staging)
                          →    └─ pv_linear_regression v3 (Dev)

Pas de monitoring        →    Databricks Dashboards + Alerts
                          →    ├─ Data Quality Dashboard
                          →    ├─ Model Performance Dashboard
                          →    └─ Email/Slack Alerts
```

---

## 📋 Feuille de route complète (4 semaines)

### **SEMAINE 1: Foundation Setup**

#### Jour 1-2: Créer Infrastructure Databricks de base

**1. Databricks Workspace**
```
Databricks UI → Create Workspace
├─ Region: EU-WEST-1 (proche de vous)
├─ Pricing tier: Premium (pour Unity Catalog)
└─ ✅ Workspace créé
```

**2. Unity Catalog**
```sql
-- Databricks SQL

-- Créer Metastore (une fois)
CREATE METASTORE pv_prediction_metastore
LOCATION 's3://your-bucket/metastore'
OWNER data_platform_team;

-- Assigner à workspace
ALTER WORKSPACE SET metastore_id=xxx;

-- Créer Catalog
CREATE CATALOG IF NOT EXISTS pv_prediction
COMMENT 'PV Production Forecasting - Complete MLOps Pipeline'
OWNER data_platform_team@company.com;

-- Créer Schemas
CREATE SCHEMA IF NOT EXISTS pv_prediction.raw
COMMENT 'Raw data: Tydom (ClickHouse) + Open-Meteo API';

CREATE SCHEMA IF NOT EXISTS pv_prediction.processed
COMMENT 'Cleaned, aggregated, feature-engineered';

CREATE SCHEMA IF NOT EXISTS pv_prediction.models
COMMENT 'ML models, predictions, metrics';

CREATE SCHEMA IF NOT EXISTS pv_prediction.monitoring
COMMENT 'Monitoring, logs, alerts';
```

#### Jour 2-3: Créer Clusters

**1. Production Cluster**
```
Databricks UI > Compute > Create Cluster

Name: pv-prediction-prod
Runtime: 14.3 LTS
Mode: All-purpose
Worker: i3.xlarge (4 nodes, min 2, max 8)
Driver: i3.xlarge
Auto-terminate: 30 minutes
Init scripts:
  - pip install clickhouse-driver==0.2.8
  - pip install pvlib==0.10.2
  - pip install requests==2.31.0

Tags:
  environment: production
  team: ml
  cost-center: analytics
```

**2. SQL Warehouse (optional but recommended)**
```
Databricks UI > SQL > SQL Warehouses > Create

Name: pv-prediction-sql
Size: 4 cores
Auto-stop: 15 minutes
Enable Photon: true
```

#### Jour 3-4: Configurer Secrets

```bash
# CLI: Créer scope de secrets
databricks secrets create-scope --scope pv_prediction_secrets

# Ajouter credentials
databricks secrets put --scope pv_prediction_secrets \
  --key clickhouse_host --string-value "192.168.x.x"

databricks secrets put --scope pv_prediction_secrets \
  --key clickhouse_port --string-value "9000"

databricks secrets put --scope pv_prediction_secrets \
  --key clickhouse_user --string-value "default"

databricks secrets put --scope pv_prediction_secrets \
  --key clickhouse_password --string-value "***"

# Vérifier
databricks secrets list --scope pv_prediction_secrets
```

#### Jour 4-5: Connecter Git (Repos)

```
Databricks UI > Workspace > Repos > Clone

Provider: GitHub
Repository URL: https://github.com/your-org/pv-prediction
Branch: main
Folder name: /Repos/your-org/pv-prediction

✅ Vous avez /Repos/your-org/pv-prediction/ synchronisé avec Git
```

---

### **SEMAINE 2: Code Migration**

#### Jour 6-7: Adapter votre code en modules réutilisables

**Votre structure actuelle:**
```
src/
├── data/
│   ├── fetch_api_data.py     ← À adapter
│   ├── load_dataset.py
│   ├── aggregation.py
│   └── cleaning.py
├── features/
│   ├── clearsky_features.py
│   ├── kc_features.py
│   └── time_features.py
└── models/
    ├── train_linear_model.py
    ├── evaluate_model.py
    ├── split.py
    └── predict.py
```

**Adapter pour Databricks:**

```python
# /Repos/your-org/pv-prediction/src/config.py

%python
from datetime import datetime

# Configuration centralisée
SITE_CONFIG = {
    "latitude": 48.7667,
    "longitude": 2.6667,
    "altitude": 0,
    "timezone": "UTC"
}

CLICKHOUSE_CONFIG = {
    "host": "clickhouse.company.com",  # ou IP locale
    "port": 9000,
    "user": "default",
    "database": "pv_data",
    # password: get from dbutils.secrets
}

DATABRICKS_CONFIG = {
    "catalog": "pv_prediction",
    "schemas": {
        "raw": "raw",
        "processed": "processed",
        "models": "models",
        "monitoring": "monitoring"
    },
    "cluster_id": "pv-prediction-prod"
}

MODEL_CONFIG = {
    "name": "pv_linear_regression",
    "version": "1.0",
    "type": "LinearRegression",
    "features": [
        "hour", "month", "dayofyear",
        "temperature_2m", "cloudcover", "windspeed_10m",
        "shortwave_radiation", "direct_radiation", "diffuse_radiation",
        "cs_ghi", "cs_dni", "cs_dhi",
        "kc", "kc_mean", "kc_std",
        "rad_mean_3h", "rad_std_3h", "rad_diff_1h",
        "day_cos", "day_sin", "month_cos", "month_sin",
        "dayofyear", "dayofyear_cos", "dayofyear_sin"
    ]
}

EXECUTION = {
    "environment": "databricks",
    "timestamp": datetime.now(),
    "log_level": "INFO"
}
```

```python
# /Repos/your-org/pv-prediction/src/data/clickhouse_connector.py

%python
from clickhouse_driver import Client
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)

class ClickHouseConnector:
    """Connecteur ClickHouse pour Databricks"""
    
    def __init__(self, host: str, port: int, user: str, password: str, db: str):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.db = db
        self.client = None
    
    def connect(self):
        """Établir connexion ClickHouse"""
        try:
            self.client = Client(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database=self.db,
                connect_timeout=10
            )
            logger.info(f"✅ Connected to ClickHouse @ {self.host}:{self.port}")
        except Exception as e:
            logger.error(f"❌ Connection failed: {str(e)}")
            raise
    
    def query(self, sql: str) -> List[tuple]:
        """Exécuter requête SQL"""
        if self.client is None:
            self.connect()
        
        try:
            result = self.client.execute(sql)
            logger.info(f"✅ Query executed: {len(result)} rows")
            return result
        except Exception as e:
            logger.error(f"❌ Query failed: {str(e)}")
            raise
    
    def close(self):
        """Fermer connexion"""
        if self.client:
            self.client.disconnect()
            logger.info("Connection closed")

def load_tydom_production(config: dict, days_back: int = 7) -> List[Dict]:
    """
    Charger données Tydom production depuis ClickHouse
    
    Returns: List[Dict] avec colonnes hour, latitude, longitude, production_wh, etc.
    """
    
    ch = ClickHouseConnector(
        host=config["host"],
        port=config["port"],
        user=config["user"],
        password=config["password"],
        db=config["database"]
    )
    
    date_from = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    
    sql = f"""
    SELECT
        hour,
        latitude,
        longitude,
        user_id,
        device_id,
        production_wh_sum as production_wh,
        production_wh_mean,
        temperature_ext_mean as temperature,
        count_records
    FROM tydom_daily_production
    WHERE hour >= '{date_from}'
    ORDER BY hour DESC
    """
    
    result = ch.query(sql)
    ch.close()
    
    # Convert to list of dicts
    columns = ["hour", "latitude", "longitude", "user_id", "device_id", 
               "production_wh", "production_wh_mean", "temperature", "count"]
    records = [dict(zip(columns, row)) for row in result]
    
    return records
```

#### Jour 8-10: Créer Notebooks pour chaque Phase

**Phase 1: Data Collection**

```python
# /Repos/your-org/pv-prediction/notebooks/Phase1_DataCollection/01_read_tydom

%python
import sys
sys.path.insert(0, "/Repos/your-org/pv-prediction")

from src.config import CLICKHOUSE_CONFIG, DATABRICKS_CONFIG
from src.data.clickhouse_connector import load_tydom_production
import pandas as pd

# Get password from secrets
ch_config = CLICKHOUSE_CONFIG.copy()
ch_config["password"] = dbutils.secrets.get(
    scope="pv_prediction_secrets",
    key="clickhouse_password"
)

# Load data
print("📡 Loading Tydom data from ClickHouse...")
records = load_tydom_production(ch_config, days_back=7)
print(f"✅ Retrieved {len(records)} records")

# Convert to Spark
df = spark.createDataFrame(pd.DataFrame(records))

# Save to Delta Lake
table_name = f"{DATABRICKS_CONFIG['catalog']}.{DATABRICKS_CONFIG['schemas']['raw']}.tydom_production_daily"
df.write.format("delta").mode("append").saveAsTable(table_name)

print(f"💾 Saved to {table_name}")
```

```python
# /Repos/your-org/pv-prediction/notebooks/Phase1_DataCollection/02_collect_openmeteo

%python
import sys
sys.path.insert(0, "/Repos/your-org/pv-prediction")

from src.config import SITE_CONFIG, DATABRICKS_CONFIG
import requests
import pandas as pd
from datetime import datetime, timedelta

# Fetch Open-Meteo
url = "https://archive-api.open-meteo.com/v1/archive"

today = datetime.now().strftime("%Y-%m-%d")
seven_days_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

params = {
    "latitude": SITE_CONFIG["latitude"],
    "longitude": SITE_CONFIG["longitude"],
    "start_date": seven_days_ago,
    "end_date": today,
    "hourly": "shortwave_radiation,direct_radiation,diffuse_radiation,temperature_2m,cloudcover,windspeed_10m",
    "timezone": "UTC"
}

print(f"📡 Fetching weather from Open-Meteo...")
response = requests.get(url, params=params, timeout=60)
response.raise_for_status()
data = response.json()

# Parse
df_weather = pd.DataFrame({
    'timestamp': pd.to_datetime(data['hourly']['time']),
    'latitude': SITE_CONFIG["latitude"],
    'longitude': SITE_CONFIG["longitude"],
    'shortwave_radiation': data['hourly']['shortwave_radiation'],
    'direct_radiation': data['hourly']['direct_radiation'],
    'diffuse_radiation': data['hourly']['diffuse_radiation'],
    'temperature_2m': data['hourly']['temperature_2m'],
    'cloudcover': data['hourly']['cloudcover'],
    'windspeed_10m': data['hourly']['windspeed_10m']
})

print(f"✅ Retrieved {len(df_weather)} hourly records")

# Save
df_spark = spark.createDataFrame(df_weather)
table_name = f"{DATABRICKS_CONFIG['catalog']}.{DATABRICKS_CONFIG['schemas']['raw']}.openmeteo_hourly"
df_spark.write.format("delta").mode("append").saveAsTable(table_name)

print(f"💾 Saved to {table_name}")
```

```python
# /Repos/your-org/pv-prediction/notebooks/Phase1_DataCollection/03_merge_and_aggregate

%python
import sys
sys.path.insert(0, "/Repos/your-org/pv-prediction")

from src.config import DATABRICKS_CONFIG
from pyspark.sql.functions import *

catalog = DATABRICKS_CONFIG["catalog"]
raw = DATABRICKS_CONFIG["schemas"]["raw"]
processed = DATABRICKS_CONFIG["schemas"]["processed"]

# 1. Load both tables
df_tydom = spark.table(f"{catalog}.{raw}.tydom_production_daily")
df_weather = spark.table(f"{catalog}.{raw}.openmeteo_hourly")

# 2. Merge hourly data
df_merged = df_tydom.join(
    df_weather,
    on=[
        "latitude", "longitude",
        trunc(col("timestamp"), "hour") == trunc(col("hour"), "hour")
    ],
    how="inner"
)

# 3. Aggregate hourly → daily
df_daily = df_merged.withColumn(
    "date", to_date(col("hour"))
).groupBy("date", "latitude", "longitude") \
    .agg(
        sum(col("production_wh")).alias("production_wh_daily"),
        avg(col("shortwave_radiation")).alias("shortwave_radiation_mean"),
        avg(col("temperature_2m")).alias("temperature_2m_mean"),
        avg(col("cloudcover")).alias("cloudcover_mean"),
        count(col("*")).alias("record_count")
    )

# 4. Save
table_name = f"{catalog}.{processed}.daily_cleaned"
df_daily.write.format("delta").mode("overwrite").saveAsTable(table_name)

print(f"💾 {df_daily.count()} daily records saved to {table_name}")
```

**Phase 2: Training**

```python
# /Repos/your-org/pv-prediction/notebooks/Phase2_Training/01_train_model

%python
import sys
sys.path.insert(0, "/Repos/your-org/pv-prediction")

from src.config import DATABRICKS_CONFIG, MODEL_CONFIG
from pyspark.ml import Pipeline
from pyspark.ml.feature import StandardScaler, VectorAssembler
from pyspark.ml.regression import LinearRegression
from pyspark.sql.functions import col, year, month, dayofyear
import mlflow

# Load data
catalog = DATABRICKS_CONFIG["catalog"]
processed = DATABRICKS_CONFIG["schemas"]["processed"]

df = spark.table(f"{catalog}.{processed}.daily_cleaned")

# Feature engineering (simplified)
feature_cols = MODEL_CONFIG["features"]

# For demo, keep only available columns
available_cols = df.columns
feature_cols = [c for c in feature_cols if c in available_cols]

print(f"📊 Using {len(feature_cols)} features: {feature_cols}")

# Prepare data
df_train = df.select(feature_cols + ["production_wh_daily"]) \
    .filter(col("production_wh_daily").isNotNull())

# Split (80/20)
train, test = df_train.randomSplit([0.8, 0.2], seed=42)

# Assemble features
assembler = VectorAssembler(inputCols=feature_cols, outputCol="features")
df_train_assembled = assembler.transform(train)

# Train
with mlflow.start_run(run_name="linear_regression_v1"):
    
    mlflow.log_params({
        "model_type": "LinearRegression",
        "features": len(feature_cols),
        "train_samples": train.count()
    })
    
    model = LinearRegression(
        featuresCol="features",
        labelCol="production_wh_daily",
        maxIter=100
    )
    
    trained_model = model.fit(df_train_assembled)
    
    # Evaluate
    df_test_assembled = assembler.transform(test)
    predictions = trained_model.transform(df_test_assembled)
    
    from pyspark.ml.evaluation import RegressionEvaluator
    evaluator = RegressionEvaluator(labelCol="production_wh_daily", predictionCol="prediction")
    
    r2 = evaluator.evaluate(predictions, {evaluator.metricName: "r2"})
    mae = evaluator.evaluate(predictions, {evaluator.metricName: "mae"})
    
    mlflow.log_metrics({
        "r2_score": r2,
        "mae": mae
    })
    
    # Save model
    mlflow.spark.log_model(trained_model, "model")
    
    print(f"✅ Model trained: R² = {r2:.3f}, MAE = {mae:.1f}")

# Register in MLflow
mlflow.register_model(
    f"runs:/{mlflow.active_run().info.run_id}/model",
    "pv_linear_regression"
)

print("✅ Model registered to MLflow")
```

**Phase 3: Inference**

```python
# /Repos/your-org/pv-prediction/notebooks/Phase3_Inference/01_predict

%python
import sys
sys.path.insert(0, "/Repos/your-org/pv-prediction")

from src.config import DATABRICKS_CONFIG, SITE_CONFIG
from datetime import datetime, timedelta
import requests
import mlflow.spark
import pandas as pd

# Get tomorrow's forecast
tomorrow = datetime.now() + timedelta(days=1)

url = "https://api.open-meteo.com/v1/forecast"
params = {
    "latitude": SITE_CONFIG["latitude"],
    "longitude": SITE_CONFIG["longitude"],
    "start_date": tomorrow.strftime("%Y-%m-%d"),
    "end_date": tomorrow.strftime("%Y-%m-%d"),
    "hourly": "shortwave_radiation,temperature_2m,cloudcover",
    "timezone": "UTC"
}

response = requests.get(url, params=params)
forecast_data = response.json()

# Load model from MLflow
model = mlflow.spark.load_model("models:/pv_linear_regression/production")

# Prepare features (simplified)
df_forecast = pd.DataFrame({
    "hour": pd.to_datetime(forecast_data["hourly"]["time"]),
    "temperature_2m": forecast_data["hourly"]["temperature_2m"],
    "shortwave_radiation": forecast_data["hourly"]["shortwave_radiation"],
    "cloudcover": forecast_data["hourly"]["cloudcover"]
})

# Predict (aggregate to daily)
# ... (simplified, needs full feature engineering)

print(f"✅ Prediction for {tomorrow.strftime('%Y-%m-%d')}: {prediction:.1f} Wh")
```

---

### **SEMAINE 3: Orchestration & Workflows**

#### Jour 11-12: Créer Databricks Workflows

**Main Workflow: Daily Pipeline**

```yaml
# Databricks UI > Workflows > Create Job

name: pv-prediction-daily-pipeline
description: Collecte données + Inférence + Suivi erreurs
trigger:
  pause_status: UNPAUSED
  schedule:
    quartz_cron_expression: "0 1 * * * ?"
    timezone_id: UTC

tasks:
  - task_key: phase1_tydom
    notebook_task:
      notebook_path: /Repos/your-org/pv-prediction/notebooks/Phase1_DataCollection/01_read_tydom
    cluster_id: pv-prediction-prod
    timeout_seconds: 600
    max_retries: 2
    
  - task_key: phase1_weather
    notebook_task:
      notebook_path: /Repos/your-org/pv-prediction/notebooks/Phase1_DataCollection/02_collect_openmeteo
    cluster_id: pv-prediction-prod
    timeout_seconds: 1200
    depends_on:
      - task_key: phase1_tydom
    
  - task_key: phase1_merge
    notebook_task:
      notebook_path: /Repos/your-org/pv-prediction/notebooks/Phase1_DataCollection/03_merge_and_aggregate
    cluster_id: pv-prediction-prod
    timeout_seconds: 300
    depends_on:
      - task_key: phase1_weather
    
  - task_key: phase3_inference
    notebook_task:
      notebook_path: /Repos/your-org/pv-prediction/notebooks/Phase3_Inference/01_predict
    cluster_id: pv-prediction-prod
    timeout_seconds: 300
    depends_on:
      - task_key: phase1_merge

on_failure:
  - email_addresses: [ml-team@company.com]

max_concurrent_runs: 1
timeout_seconds: 7200
```

**Secondary Workflow: Weekly Retraining**

```yaml
name: pv-prediction-weekly-retrain
trigger:
  pause_status: UNPAUSED
  schedule:
    quartz_cron_expression: "0 2 ? * MON"  # Monday 02:00 UTC
    timezone_id: UTC

tasks:
  - task_key: train_model
    notebook_task:
      notebook_path: /Repos/your-org/pv-prediction/notebooks/Phase2_Training/01_train_model
    cluster_id: pv-prediction-prod
    timeout_seconds: 1800
    max_retries: 1

on_failure:
  - email_addresses: [ml-team@company.com]
```

---

### **SEMAINE 4: Monitoring & Production**

#### Jour 13-14: Dashboards & Alerts

**Data Quality Dashboard**

```sql
-- Databricks SQL > Dashboards > Create

SELECT
    DATE(timestamp) as collection_date,
    COUNT(*) as total_records,
    COUNT(DISTINCT latitude) as locations,
    ROUND(100.0 * COUNT(*) / 24, 1) as hourly_coverage_pct
FROM pv_prediction.raw.tydom_production_daily
WHERE DATE(timestamp) >= DATE_SUB(CURRENT_DATE(), 30)
GROUP BY DATE(timestamp)
ORDER BY collection_date DESC;
```

**Model Performance Dashboard**

```sql
SELECT
    DATE(prediction_date) as date,
    COUNT(*) as predictions,
    ROUND(AVG(ABS(error_wh)), 0) as avg_error_wh,
    ROUND(AVG(error_percent), 2) as avg_error_pct
FROM pv_prediction.models.predictions_history
WHERE DATE(prediction_date) >= DATE_SUB(CURRENT_DATE(), 90)
GROUP BY DATE(prediction_date)
ORDER BY date DESC;
```

#### Jour 15: Alerts

**Alert 1: Data Ingestion**

```
Query: SELECT COUNT(*) FROM pv_prediction.raw.tydom_production_daily WHERE DATE(timestamp) = CURRENT_DATE()
Trigger: If result < 100
Action: Email to data-eng@company.com
```

**Alert 2: Model Drift**

```
Query: SELECT AVG(ABS(error_percent)) FROM pv_prediction.models.predictions_history WHERE DATE(prediction_date) >= DATE_SUB(CURRENT_DATE(), 7)
Trigger: If result > 15%
Action: Email + Slack notification
```

#### Jour 16: Documentation & Team Training

- [ ] Documentation complète README
- [ ] Runbooks pour troubleshooting
- [ ] Team training session
- [ ] 🚀 Go-live !

---

## 📊 Votre Architecture Complète dans Databricks

```
┌─────────────────────────────────────────────────────────────────────┐
│                    DATABRICKS WORKSPACE COMPLET                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  /Repos/your-org/pv-prediction/  (Git-synced)                      │
│  ├── src/                                                            │
│  │   ├── config.py (CENTRALISÉ)                                    │
│  │   ├── data/                                                      │
│  │   │   ├── clickhouse_connector.py                               │
│  │   │   ├── loader.py                                             │
│  │   │   └── cleaner.py                                            │
│  │   ├── features/                                                  │
│  │   │   ├── clearsky_features.py                                  │
│  │   │   ├── kc_features.py                                        │
│  │   │   └── time_features.py                                      │
│  │   └── models/                                                    │
│  │       ├── training.py                                           │
│  │       └── evaluation.py                                         │
│  │                                                                  │
│  └── notebooks/                                                     │
│      ├── Phase1_DataCollection/                                    │
│      │   ├── 01_read_tydom_from_clickhouse                        │
│      │   ├── 02_collect_openmeteo                                 │
│      │   └── 03_merge_and_aggregate                               │
│      │                                                              │
│      ├── Phase2_Training/                                          │
│      │   ├── 01_train_model                                        │
│      │   ├── 02_evaluate_model                                    │
│      │   └── 03_register_mlflow                                   │
│      │                                                              │
│      ├── Phase3_Inference/                                         │
│      │   └── 01_predict_tomorrow                                  │
│      │                                                              │
│      └── Phase4_ErrorTracking/                                     │
│          └── 01_compare_predictions_actual                         │
│                                                                      │
│  Unity Catalog: pv_prediction                                       │
│  ├── raw (Tydom desde CH + Open-Meteo API)                         │
│  │   ├── tydom_production_daily                                    │
│  │   └── openmeteo_hourly                                          │
│  │                                                                  │
│  ├── processed (Cleaned + features)                                │
│  │   └── daily_cleaned (28 columns)                               │
│  │                                                                  │
│  └── models (Predictions + MLflow)                                 │
│      ├── predictions_history                                       │
│      ├── error_logs                                                │
│      └── mlflow registry                                           │
│         └── pv_linear_regression v1,v2,v3                         │
│                                                                      │
│  Compute Resources                                                  │
│  ├── pv-prediction-prod (4-8 workers)                              │
│  ├── pv-prediction-sql (SQL Warehouse)                             │
│  └── Instance Pools (cost optimization)                            │
│                                                                      │
│  Workflows (Orchestration)                                         │
│  ├── pv-prediction-daily-pipeline (01:00 UTC)                     │
│  └── pv-prediction-weekly-retrain (Monday 02:00)                  │
│                                                                      │
│  Dashboards + Alerts                                               │
│  ├── Data Quality Monitor                                          │
│  ├── Model Performance Dashboard                                   │
│  ├── Alert: Data Ingestion                                         │
│  └── Alert: Model Drift                                            │
│                                                                      │
│  Secrets                                                            │
│  └── pv_prediction_secrets                                         │
│      ├── clickhouse_host                                           │
│      ├── clickhouse_password                                       │
│      └── api_keys                                                  │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## ✅ Checklist Complète (Étape par Étape)

### **SEMAINE 1: Setup**
- [ ] Créer Databricks workspace
- [ ] Configurer Unity Catalog + 3 schemas
- [ ] Créer cluster prod + SQL warehouse
- [ ] Configurer secrets scope
- [ ] Connecter Git Repos

### **SEMAINE 2: Code Migration**
- [ ] Créer src/config.py (configuration centralisée)
- [ ] Créer src/data/clickhouse_connector.py
- [ ] Adapter src/features/*.py
- [ ] Créer notebooks Phase1, Phase2, Phase3, Phase4
- [ ] Tester chaque notebook manuellement

### **SEMAINE 3: Orchestration**
- [ ] Créer Databricks Workflow: daily-pipeline
- [ ] Créer Databricks Workflow: weekly-retrain
- [ ] Configurer schedules
- [ ] Tester end-to-end

### **SEMAINE 4: Monitoring**
- [ ] Créer 2 dashboards SQL
- [ ] Configurer 2 alerts (data quality + model drift)
- [ ] Email notifications testées
- [ ] Documentation équipe
- [ ] 🚀 Production ready !

---

## 🔍 Comparaison: Avant vs Après

| Aspect | AVANT (Local) | APRÈS (Databricks) |
|--------|------------|------------------|
| **Code** | Scripts séparés | Modules + Repos |
| **Données** | CSV locaux | Delta Lake (Unity Catalog) |
| **Compute** | Machine locale | Clusters auto-scaling |
| **Models** | Pickle files | MLflow Registry |
| **Orchestration** | Cron jobs manuels | Databricks Workflows |
| **Monitoring** | Logs manuels | Dashboards SQL |
| **Collaboration** | Difficile | Git + Team workspace |
| **Scalabilité** | Limitée | Illimitée (cloud) |
| **Production-ready** | 50% | 100% |

---

## 🎯 Bénéfices de cette organisation

✅ **Scalabilité** : De 1 box Tydom à 1000 sans changement d'architecture
✅ **Maintenance** : Bug fix au même endroit (pas duplication)
✅ **Collaboration** : Team peut travailler en parallèle (Git branches)
✅ **Reliability** : Alerts + monitoring automatisés
✅ **Auditability** : Traçabilité complète (Git + MLflow)
✅ **Cost** : Auto-scaling = payer seulement ce qu'on utilise

---

## 🚀 Prochaines actions

**Immédiatement:**
1. Créer workspace Databricks
2. Configurer Unity Catalog
3. Connecter Git Repos

**Cette semaine:**
4. Adapter vos modules src/
5. Créer notebooks Phase1-4
6. Tester localement

**Semaine prochaine:**
7. Créer Workflows
8. Configurer Dashboards
9. Production go-live

Vous êtes prêt ? 🚀

Vous avez des questions sur une étape spécifique ?
