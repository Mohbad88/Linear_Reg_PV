from main_training_pipeline import run_pipeline
from src.visualization.plot_predictions import plot_one_test_day_bar_plots

# entraîne et renvoie les objets utiles
res = run_pipeline(
    data_source="weather_api_local_production",
    split_date="2020-07-31",
)

y_test = res['y_test']
y_pred = res['y_pred']

# tester un jour (au format YYYY‑MM‑DD) appartenant à la période de test
plot_one_test_day_bar_plots("2020-08-02", y_test, y_pred)
plot_one_test_day_bar_plots("2021-01-30", y_test, y_pred)