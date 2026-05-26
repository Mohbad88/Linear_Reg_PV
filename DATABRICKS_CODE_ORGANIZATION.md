# Comment Organiser le Code sous Databricks

## 📌 Trois approches d'organisation du code

### 1️⃣ Approche Notebook-Centrée (Simplest)

Tout le code dans des **notebooks individuels**, sans modules externes.

```
/Shared/pv-prediction/
├── Phase1_DataCollection/
│   ├── 01_read_tydom_from_clickhouse    ← Tout le code ici
│   ├── 02_collect_openmeteo_historical  ← Tout le code ici
│   └── 03_merge_and_aggregate           ← Tout le code ici
│
├── Phase2_Training/
│   ├── 01_feature_engineering           ← Tout le code ici
│   └── 02_train_linear_model            ← Tout le code ici
│
└── Phase3_Inference/
    └── 01_predict_tomorrow               ← Tout le code ici
```

**Avantages:**
- ✅ Simple, pas de dépendances externes
- ✅ Chaque notebook = entité indépendante
- ✅ Facile pour les débutants

**Inconvénients:**
- ❌ Code dupliqué
- ❌ Difficile à tester
- ❌ Pas scalable

**Exemple Notebook Classique:**

```python
# Databricks Notebook: /Shared/pv-prediction/Phase1_DataCollection/01_read_tydom_from_clickhouse

# ==========================================
# CELL 1: Configuration
# ==========================================

%python
from clickhouse_driver import Client
from datetime import datetime, timedelta
import pandas as pd

# Configuration
CLICKHOUSE_HOST = dbutils.secrets.get(scope="pv_prediction_secrets", key="clickhouse_host")
CLICKHOUSE_PASSWORD = dbutils.secrets.get(scope="pv_prediction_secrets", key="clickhouse_password")

# ==========================================
# CELL 2: Fonction lecture ClickHouse
# ==========================================

%python
def fetch_tydom_from_clickhouse(days_back=7):
    """Récupérer données Tydom depuis ClickHouse"""
    
    client = Client(
        host=CLICKHOUSE_HOST,
        port=9000,
        user="default",
        password=CLICKHOUSE_PASSWORD,
        database="pv_data"
    )
    
    date_from = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    
    query = f"""
    SELECT
        hour,
        latitude,
        longitude,
        user_id,
        production_wh_sum as production_wh
    FROM pv_data.tydom_daily_production
    WHERE hour >= '{date_from}'
    ORDER BY hour DESC
    """
    
    result = client.execute(query)
    client.disconnect()
    
    return result

# ==========================================
# CELL 3: Charger dans Databricks
# ==========================================

%python
# Récupérer données
records = fetch_tydom_from_clickhouse()

# Convertir en DataFrame
df_pandas = pd.DataFrame(records, columns=["hour", "latitude", "longitude", "user_id", "production_wh"])
df = spark.createDataFrame(df_pandas)

# Écrire dans Delta Lake
df.write \
    .format("delta") \
    .mode("append") \
    .saveAsTable("pv_prediction.raw.tydom_production_daily")

print(f"✅ {len(records)} records loaded to Databricks")
```

---

### 2️⃣ Approche Modules Partagés (Recommended)

Code réutilisable dans des **modules Python**, importés par les notebooks.

```
Databricks Workspace:
│
/Shared/pv-prediction/
├── Utilities/                      ← Modules Python
│   ├── config.py
│   ├── data_utils.py              ← Fonctions réutilisables
│   ├── feature_utils.py
│   ├── model_utils.py
│   └── clickhouse_connector.py
│
├── Phase1_DataCollection/
│   ├── 01_read_tydom_from_clickhouse
│   ├── 02_collect_openmeteo_historical
│   └── 03_merge_and_aggregate
│
├── Phase2_Training/
│   ├── 01_feature_engineering
│   └── 02_train_linear_model
│
└── Phase3_Inference/
    └── 01_predict_tomorrow
```

**Comment créer un module Python dans Databricks:**

**Option A: Utiliser `/Workspace/` comme répertoire de modules**

```python
# Databricks Notebook: /Shared/pv-prediction/Utilities/clickhouse_connector

%python
from clickhouse_driver import Client
from datetime import datetime, timedelta

class ClickHouseConnector:
    """Classe pour gérer connexion ClickHouse"""
    
    def __init__(self, host, port, user, password, db):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.db = db
    
    def connect(self):
        """Établir connexion"""
        self.client = Client(
            host=self.host,
            port=self.port,
            user=self.user,
            password=self.password,
            database=self.db
        )
        return self.client
    
    def query(self, sql, as_pandas=False):
        """Exécuter requête"""
        if not hasattr(self, 'client') or self.client is None:
            self.connect()
        
        result = self.client.execute(sql)
        
        if as_pandas:
            # Convertir en pandas (nécessite en-têtes)
            import pandas as pd
            return pd.DataFrame(result)
        
        return result
    
    def disconnect(self):
        """Fermer connexion"""
        if hasattr(self, 'client'):
            self.client.disconnect()

# Test
# ch = ClickHouseConnector(
#     host="clickhouse.company.com",
#     port=9000,
#     user="default",
#     password="xxx",
#     db="pv_data"
# )
# result = ch.query("SELECT COUNT(*) FROM tydom_daily_production")
# print(result)
```

Puis l'utiliser dans un autre notebook:

```python
# Databricks Notebook: /Shared/pv-prediction/Phase1_DataCollection/01_read_tydom

%python
import sys
sys.path.insert(0, "/Workspace/Shared/pv-prediction/Utilities")

from clickhouse_connector import ClickHouseConnector

# Créer connecteur
ch = ClickHouseConnector(
    host=dbutils.secrets.get(scope="pv_prediction_secrets", key="clickhouse_host"),
    port=9000,
    user="default",
    password=dbutils.secrets.get(scope="pv_prediction_secrets", key="clickhouse_password"),
    db="pv_data"
)

# Utiliser
records = ch.query("SELECT * FROM tydom_daily_production LIMIT 100")
ch.disconnect()

print(f"✅ Retrieved {len(records)} records")
```

**Option B: Utiliser `/Repos/` (Git-based, recommandé)**

Si vous avez connecté votre Databricks à GitHub:

```
/Repos/your-org/pv-prediction/
├── src/                      ← Code Python versionné
│   ├── __init__.py
│   ├── config.py
│   ├── data/
│   │   ├── __init__.py
│   │   ├── clickhouse_connector.py
│   │   ├── aggregation.py
│   │   └── cleaning.py
│   ├── features/
│   │   ├── __init__.py
│   │   ├── clearsky_features.py
│   │   ├── kc_features.py
│   │   └── time_features.py
│   └── models/
│       ├── __init__.py
│       ├── train.py
│       ├── evaluate.py
│       └── predict.py
│
└── notebooks/
    ├── Phase1_DataCollection/
    ├── Phase2_Training/
    ├── Phase3_Inference/
    └── Phase4_ErrorTracking/
```

Import dans notebooks:

```python
# Databricks Notebook: /Repos/your-org/pv-prediction/notebooks/Phase1/01_read_tydom

%python
import sys
sys.path.insert(0, "/Repos/your-org/pv-prediction")

from src.data.clickhouse_connector import ClickHouseConnector
from src.data.aggregation import aggregate_daily
from src.features.clearsky_features import add_clearsky_to_df

# Utiliser
ch = ClickHouseConnector(...)
records = ch.query("SELECT * FROM tydom_daily_production")
```

**Avantages:**
- ✅ Code versionnée dans Git
- ✅ Pas de duplication
- ✅ Facile de tester avec pytest
- ✅ Réutilisable entre notebooks

---

### 3️⃣ Approche Packages Installés (Advanced)

Créer un **package Python** publié sur **PyPI ou Artifactory**, puis l'installer dans le cluster.

```
Votre repo Git externe:
github.com/your-org/pv-prediction-sdk
├── setup.py
├── pv_prediction_sdk/
│   ├── __init__.py
│   ├── config.py
│   ├── data/
│   │   ├── clickhouse.py
│   │   ├── aggregation.py
│   │   └── cleaning.py
│   ├── features/
│   │   ├── clearsky.py
│   │   ├── kc.py
│   │   └── temporal.py
│   └── models/
│       ├── train.py
│       └── evaluate.py
└── tests/
```

Installation dans Databricks:

```python
# CLI
pip install pv-prediction-sdk

# Ou dans cluster init script:
pip install git+https://github.com/your-org/pv-prediction-sdk.git@main
```

Usage:

```python
# Databricks Notebook
from pv_prediction_sdk.data import ClickHouseConnector
from pv_prediction_sdk.features import add_clearsky_to_df
from pv_prediction_sdk.models import train_linear_regression

# Utiliser directement
ch = ClickHouseConnector(...)
df = spark.table("pv_prediction.raw.tydom_production_hourly").toPandas()
df = add_clearsky_to_df(df)
model = train_linear_regression(df)
```

---

## 🎯 Recommandation : Structure hybride

**La meilleure approche combine:**

1. **Git Repos** pour le code principal
2. **Modules réutilisables** en `/Repos/src/`
3. **Notebooks** comme orchestration
4. **Secrets** pour credentials

```python
# Structure idéale

# ===== REPOS (Git-based) =====
/Repos/your-org/pv-prediction/
├── src/
│   ├── __init__.py
│   ├── config.py
│   ├── data/
│   │   ├── clickhouse.py      # Classe ClickHouseConnector
│   │   ├── loader.py           # load_from_clickhouse()
│   │   ├── cleaner.py          # clean_data()
│   │   └── aggregator.py       # aggregate_daily()
│   │
│   ├── features/
│   │   ├── engineering.py      # engineer_features()
│   │   ├── clearsky.py         # add_clearsky()
│   │   └── temporal.py         # add_time_features()
│   │
│   └── models/
│       ├── training.py         # train_model()
│       ├── evaluation.py       # evaluate_model()
│       └── inference.py        # predict()
│
└── notebooks/
    ├── Phase1_DataCollection/
    │   ├── 01_read_tydom_from_clickhouse
    │   ├── 02_collect_openmeteo_historical
    │   └── 03_merge_and_aggregate
    │
    ├── Phase2_Training/
    │   ├── 01_feature_engineering
    │   └── 02_train_linear_model
    │
    ├── Phase3_Inference/
    │   └── 01_predict_tomorrow
    │
    └── Phase4_ErrorTracking/
        └── 01_compare_predictions_actual
```

Chaque notebook utilise les modules :

```python
# Databricks Notebook: Phase1/01_read_tydom_from_clickhouse

%python
import sys
sys.path.insert(0, "/Repos/your-org/pv-prediction")

from src.config import CLICKHOUSE_CONFIG, DATABRICKS_CONFIG
from src.data.clickhouse import ClickHouseConnector
from src.data.loader import load_from_clickhouse
from src.data.aggregator import aggregate_daily

# Configuration
ch_config = CLICKHOUSE_CONFIG

# Charger données
records = load_from_clickhouse(ch_config, days_back=7)

# Convertir et écrire
df = spark.createDataFrame(records)
df.write.format("delta").mode("append").saveAsTable("pv_prediction.raw.tydom_production_hourly")

print(f"✅ {len(records)} records loaded")
```

---

## 📂 Exemple complet: Structure recommandée

### 1. Config centralisée

```python
# /Repos/your-org/pv-prediction/src/config.py

%python
from datetime import datetime

# Configuration centrale
SITE = {
    "latitude": 48.7667,
    "longitude": 2.6667,
    "altitude": 0,
    "timezone": "UTC"
}

CLICKHOUSE_CONFIG = {
    "host": "clickhouse.company.com",
    "port": 9000,
    "user": "default",
    "db": "pv_data"
    # Password from dbutils.secrets
}

DATABRICKS_CONFIG = {
    "catalog": "pv_prediction",
    "schemas": {
        "raw": "raw",
        "processed": "processed",
        "models": "models"
    },
    "cluster_id": "pv-prediction-prod"
}

MODEL_CONFIG = {
    "name": "pv_linear_regression",
    "version": "1.0",
    "type": "LinearRegression",
    "features": [
        "hour", "month", "dayofyear",
        "temperature_2m", "cloudcover",
        "ghi", "cs_ghi", "kc",
        # ... 28 total
    ]
}

EXECUTION = {
    "environment": "databricks",
    "timestamp": datetime.now(),
    "log_level": "INFO"
}
```

### 2. Module de données

```python
# /Repos/your-org/pv-prediction/src/data/clickhouse.py

%python
from clickhouse_driver import Client
from datetime import datetime, timedelta
from typing import List, Dict

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
        """Connexion"""
        self.client = Client(
            host=self.host,
            port=self.port,
            user=self.user,
            password=self.password,
            database=self.db
        )
        print(f"✅ Connected to ClickHouse @ {self.host}")
    
    def query(self, sql: str) -> List[tuple]:
        """Exécuter requête"""
        if self.client is None:
            self.connect()
        return self.client.execute(sql)
    
    def close(self):
        """Fermer connexion"""
        if self.client:
            self.client.disconnect()

def load_from_clickhouse(config: dict, days_back: int = 7) -> List[Dict]:
    """
    Charger données Tydom depuis ClickHouse
    
    Args:
        config: dict avec host, port, user, password, db
        days_back: nombre de jours à récupérer
    
    Returns:
        List[Dict] avec colonnes (hour, latitude, longitude, production_wh, ...)
    """
    
    ch = ClickHouseConnector(
        host=config["host"],
        port=config["port"],
        user=config["user"],
        password=config["password"],  # From secrets
        db=config["db"]
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
        temperature_ext_mean as temperature
    FROM tydom_daily_production
    WHERE hour >= '{date_from}'
    ORDER BY hour DESC
    """
    
    result = ch.query(sql)
    ch.close()
    
    # Convertir en list of dicts
    columns = ["hour", "latitude", "longitude", "user_id", "device_id", "production_wh", "temperature"]
    records = [dict(zip(columns, row)) for row in result]
    
    return records
```

### 3. Notebook utilisant les modules

```python
# Databricks Notebook: /Repos/your-org/pv-prediction/notebooks/Phase1/01_read_tydom

# ==================== CELL 1: Setup ====================
%python
import sys
sys.path.insert(0, "/Repos/your-org/pv-prediction")

from src.config import CLICKHOUSE_CONFIG, DATABRICKS_CONFIG, SITE
from src.data.clickhouse import load_from_clickhouse

# ==================== CELL 2: Configuration ====================
%python
# Get credentials from Databricks secrets
ch_config = CLICKHOUSE_CONFIG.copy()
ch_config["password"] = dbutils.secrets.get(
    scope="pv_prediction_secrets",
    key="clickhouse_password"
)

catalog = DATABRICKS_CONFIG["catalog"]
schema = DATABRICKS_CONFIG["schemas"]["raw"]
table_name = f"{catalog}.{schema}.tydom_production_daily"

# ==================== CELL 3: Load Data ====================
%python
print("📡 Loading data from ClickHouse...")
records = load_from_clickhouse(ch_config, days_back=7)
print(f"✅ Retrieved {len(records)} records")

# ==================== CELL 4: Save to Databricks ====================
%python
# Convert to Spark DataFrame
df_pandas = pd.DataFrame(records)
df = spark.createDataFrame(df_pandas)

# Write to Delta Lake
df.write \
    .format("delta") \
    .mode("append") \
    .option("mergeSchema", "true") \
    .saveAsTable(table_name)

print(f"💾 Saved to {table_name}")

# ==================== CELL 5: Validation ====================
%python
validation_df = spark.sql(f"""
    SELECT
        COUNT(*) as total_records,
        COUNT(DISTINCT DATE(hour)) as days,
        MIN(hour) as earliest,
        MAX(hour) as latest
    FROM {table_name}
""")

validation_df.display()
```

---

## 🎓 Meilleure Pratiques

### ✅ DO (À faire)

```python
# ✅ Utiliser secrets pour credentials
password = dbutils.secrets.get(scope="my_scope", key="my_key")

# ✅ Importer depuis modules
import sys
sys.path.insert(0, "/Repos/your-org/project")
from src.data import load_data

# ✅ Utiliser fonction paramétrée
def load_data(config: dict, date: str) -> pd.DataFrame:
    # Implementation
    pass

# ✅ Logger les étapes
print("✅ Step completed")
print(f"📊 {row_count} records processed")

# ✅ Utiliser %python pour code clair
%python
import pandas as pd
df = spark.table("table_name").toPandas()

# ✅ Documenter les notebooks
# Databricks Notebook: /path/to/notebook
# Description: What this does
# Dependencies: What modules it uses
```

### ❌ DON'T (À éviter)

```python
# ❌ JAMAIS hardcoder credentials
password = "my_secret_password"

# ❌ Ne pas dupliquer code
# (créer fonction réutilisable)

# ❌ Ne pas faire tout dans un notebook géant
# (créer modules, diviser en étapes)

# ❌ Ne pas mélanger Python et Scala
# (choisir une langue)

# ❌ Ne pas laisser de debug code
# print("DEBUG: test")  # À nettoyer
```

---

## 📝 Template Notebook Standard

```python
# Databricks Notebook: /Shared/pv-prediction/Phase1_DataCollection/02_collect_openmeteo

# ============================================================
# PHASE 1 - COLLECT OPEN-METEO WEATHER DATA
# ============================================================
# Purpose: Fetch historical and forecast weather from Open-Meteo API
# Schedule: Daily @ 01:00 UTC
# Dependencies: requests, pandas, pyspark
# Output: pv_prediction.raw.openmeteo_hourly table
# ============================================================

# %python
# ============================================================
# CELL 1: IMPORTS & CONFIG
# ============================================================

import sys
sys.path.insert(0, "/Repos/your-org/pv-prediction")

import requests
import pandas as pd
from datetime import datetime, timedelta

from src.config import SITE, DATABRICKS_CONFIG
from src.data.aggregator import aggregate_daily

# ============================================================
# CELL 2: FETCH OPEN-METEO DATA
# ============================================================

def fetch_open_meteo(lat: float, lon: float, start_date: str, end_date: str):
    """
    Fetch hourly weather data from Open-Meteo API
    
    Args:
        lat, lon: Location coordinates
        start_date: "YYYY-MM-DD"
        end_date: "YYYY-MM-DD"
    
    Returns:
        DataFrame with columns: timestamp, [weather_vars]
    """
    
    url = "https://archive-api.open-meteo.com/v1/archive"
    
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start_date,
        "end_date": end_date,
        "hourly": "shortwave_radiation,direct_radiation,diffuse_radiation,temperature_2m,cloudcover,windspeed_10m",
        "timezone": "UTC"
    }
    
    print(f"📡 Fetching {start_date} to {end_date} for ({lat}, {lon})")
    response = requests.get(url, params=params, timeout=60)
    response.raise_for_status()
    
    data = response.json()
    
    # Parse response
    df = pd.DataFrame({
        'timestamp': pd.to_datetime(data['hourly']['time']),
        'latitude': lat,
        'longitude': lon,
        'shortwave_radiation': data['hourly']['shortwave_radiation'],
        'direct_radiation': data['hourly']['direct_radiation'],
        'diffuse_radiation': data['hourly']['diffuse_radiation'],
        'temperature_2m': data['hourly']['temperature_2m'],
        'cloudcover': data['hourly']['cloudcover'],
        'windspeed_10m': data['hourly']['windspeed_10m']
    })
    
    print(f"✅ Retrieved {len(df)} hourly records")
    return df

# ============================================================
# CELL 3: LOAD & SAVE
# ============================================================

# Date range
today = datetime.now().strftime("%Y-%m-%d")
start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

# Fetch data
df_weather = fetch_open_meteo(
    lat=SITE["latitude"],
    lon=SITE["longitude"],
    start_date=start_date,
    end_date=today
)

# Convert to Spark & save
df_spark = spark.createDataFrame(df_weather)

table_name = f"{DATABRICKS_CONFIG['catalog']}.{DATABRICKS_CONFIG['schemas']['raw']}.openmeteo_hourly"

df_spark.write \
    .format("delta") \
    .mode("append") \
    .option("mergeSchema", "true") \
    .saveAsTable(table_name)

print(f"💾 Saved to {table_name}")

# ============================================================
# CELL 4: VALIDATION
# ============================================================

validation = spark.sql(f"""
    SELECT
        COUNT(*) as record_count,
        MIN(timestamp) as earliest,
        MAX(timestamp) as latest,
        ROUND(AVG(temperature_2m), 2) as avg_temp,
        ROUND(AVG(shortwave_radiation), 2) as avg_radiation
    FROM {table_name}
    WHERE DATE(timestamp) >= '{start_date}'
""")

validation.display()
print("✅ Phase 1 - Open-Meteo collection completed")
```

---

## 🚀 Résumé: Quelle approche choisir ?

| Approche | Code | Modules | Complexité | Performance |
|----------|------|---------|-----------|-------------|
| **Notebook-only** | Dans notebook | Aucun | 🟢 Simple | 🟢 OK |
| **Modules (Workspace)** | `/Workspace/` | sys.path | 🟡 Moyen | 🟢 OK |
| **Modules (Repos)** | `/Repos/` + Git | sys.path | 🟡 Moyen | 🟡 Bon |
| **Package PyPI** | Externe | pip install | 🔴 Complexe | 🟢 Optimal |

### **Recommandation pour vous:**

👉 **Commencez avec `Approche 2 (Modules + Repos)`**

- Code versionné dans Git
- Modules réutilisables
- Notebooks propres et lisibles
- Facile à collaborer

---

## 📋 Pas à pas: Mettre en place cette structure

```markdown
### ÉTAPE 1: Créer Repos Databricks
- [ ] Databricks > Workspace > Repos > Clone
- [ ] Connecter à GitHub (votre-org/pv-prediction)
- [ ] Vous avez maintenant /Repos/your-org/pv-prediction/

### ÉTAPE 2: Créer structure src/
- [ ] Créer dossiers src/, src/data/, src/features/, src/models/
- [ ] Créer __init__.py dans chaque dossier
- [ ] Créer config.py (configuration centralisée)

### ÉTAPE 3: Copier vos modules
- [ ] De votre repo local, adapter src/data/fetch_api_data.py
- [ ] Adapter src/features/clearsky_features.py
- [ ] Adapter src/models/train_linear_model.py
- [ ] Push to GitHub

### ÉTAPE 4: Créer notebooks
- [ ] Créer /Repos/.../notebooks/Phase1/, Phase2/, etc.
- [ ] Dans chaque notebook, importer depuis src/
- [ ] Tester chaque notebook (Run Now)

### ÉTAPE 5: Orchestration
- [ ] Créer Databricks Workflow
- [ ] Linking notebooks avec dépendances
- [ ] Schedule Daily @ 01:00 UTC
- [ ] Tester end-to-end

### ÉTAPE 6: Production
- [ ] Ajouter secrets (ClickHouse password)
- [ ] Configurer alertes
- [ ] Documentation équipe
- [ ] Go live !
```

Vous voulez que je crée les fichiers src/ pour votre projet ? 🚀
