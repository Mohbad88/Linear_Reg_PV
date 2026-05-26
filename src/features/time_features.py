import numpy as np

def add_time_features(df):

    df["month"] = df.index.month

    df["month_sin"] = np.sin(2*np.pi*df["month"]/12)
    df["month_cos"] = np.cos(2*np.pi*df["month"]/12)

    df["day_of_year"] = df.index.dayofyear

    df["day_of_year_sin"] = np.sin(2*np.pi*df["day_of_year"]/365)
    df["day_of_year_cos"] = np.cos(2*np.pi*df["day_of_year"]/365)

    return df