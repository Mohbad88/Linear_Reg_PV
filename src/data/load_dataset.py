import pandas as pd
import os

def load_dataset(path):
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pkl":
        df = pd.read_pickle(path)
    elif ext == ".csv":
        df = pd.read_csv(path, index_col=0, parse_dates=True)
    elif ext == ".parquet":
        df = pd.read_parquet(path)
    else:
        raise ValueError(f"Format non supporté: {ext}")

    print("Dataset loaded successfully:", df.shape)

    return df