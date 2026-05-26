import pvlib

def add_clearsky_to_df_model(df, lat=48.7667, lon=2.6667, altitude=0, tz="UTC"):

    loc = pvlib.location.Location(lat, lon, altitude=altitude, tz=tz)

    cs = loc.get_clearsky(df.index)

    df["cs_ghi"] = cs["ghi"]
    df["cs_dni"] = cs["dni"]
    df["cs_dhi"] = cs["dhi"]

    return df