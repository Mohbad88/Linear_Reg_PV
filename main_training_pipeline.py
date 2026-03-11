from src.data.load_dataset import load_dataset
from src.features.clearsky_features import add_clearsky_to_df_model
from src.features.kc_features import add_kc_to_df
from src.data.cleaning import clean_dataset
from src.features.time_features import add_time_features
from src.models.train_linear_model import train_model

df = load_dataset("data/raw/df_model_Pierre_ozoir.pkl")

df = add_clearsky_to_df_model(df)

df = add_kc_to_df(df)

df = clean_dataset(df)

df = add_time_features(df)

print("Pipeline finished successfully")