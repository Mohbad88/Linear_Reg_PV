import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns


def plot_one_test_day_bar_plots(day, y_test, y_pred):
    """Affiche un bar plot comparant la production réelle, la prédiction et l'erreur pour un jour donné.

    Parameters
    ----------
    day : str or pd.Timestamp
        Format ``YYYY-MM-DD`` ou équivalent.
    y_test : pd.Series
        Valeurs réelles indexées par date.
    y_pred : array-like or pd.Series
        Prédictions correspondantes.
    """
    day = pd.Timestamp(day)

    # Convert y_pred to a Series with the same index as y_test for easy lookup
    y_pred_s = pd.Series(np.asarray(y_pred), index=y_test.index)

    if day not in y_test.index:
        print(f"Warning: {day.date()} is not in the test period. Please choose a day between {y_test.index.min().date()} and {y_test.index.max().date()}")
        return

    real_val = y_test.loc[day]
    pred_val = y_pred_s.loc[day]
    error_val = pred_val - real_val

    data = pd.DataFrame({
        'Metric': ['Production Réelle', 'Prédiction', 'Erreur'],
        'Value': [real_val, pred_val, error_val]
    })

    plt.figure(figsize=(8, 5))
    plt.bar(data['Metric'], data['Value'], color=['skyblue', 'lightcoral', 'lightgreen'])
    plt.axhline(0, color='grey', linewidth=0.8)
    plt.ylabel('Énergie PV (Wh/jour)')
    plt.title(f'Comparaison Production PV, Prédiction et Erreur pour le {day.date()}')
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    plt.show()

    print(f"Jour      : {day.date()}")
    print(f"Réel      : {real_val:,.2f} Wh/jour")
    print(f"Prédit    : {pred_val:,.2f} Wh/jour")
    print(f"Erreur    : {error_val:,.2f} Wh/jour")
    print(f"Erreur %  : {error_val/real_val*100:,.2f} %")


def plot_real_vs_pred(y_test, y_pred):
    """Scatter plot of actual vs predicted values with 45-degree reference line."""
    plt.figure(figsize=(8, 8))
    plt.scatter(y_test, y_pred, alpha=0.6)
    min_val = min(y_test.min(), pd.Series(y_pred).min())
    max_val = max(y_test.max(), pd.Series(y_pred).max())
    plt.plot([min_val, max_val], [min_val, max_val], 'r--', label='Perfect Prediction')
    plt.title('Réel vs Prédit (période de test)')
    plt.xlabel('Réel (Wh/jour)')
    plt.ylabel('Prédit (Wh/jour)')
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.show()


def plot_coefficients(features, coeffs):
    """Bar chart of model coefficients/feature importances."""
    df = pd.DataFrame({'Variable': features, 'Coefficient': coeffs})
    df = df.sort_values('Coefficient', ascending=False)
    plt.figure(figsize=(10, 6))
    sns.barplot(x='Coefficient', y='Variable', data=df, palette='viridis', dodge=False)
    plt.title('Importance des caractéristiques (coefficients)')
    plt.xlabel('Coefficient')
    plt.ylabel('Variable')
    plt.grid(axis='x', linestyle='--', alpha=0.7)
    plt.tight_layout()
    plt.show()


def plot_correlation_matrix(df, features):
    """Heatmap of correlations between explanatory variables."""
    corr_matrix = df[features].corr()
    plt.figure(figsize=(8, 6))
    sns.heatmap(corr_matrix, annot=True, cmap='coolwarm', fmt='.2f')
    plt.title('Matrice de corrélation des variables explicatives')
    plt.show()


def check_ecs_rule_one_day(day_n, y_test, y_pred, threshold_kwh=5.0, plot=True):
    """Evaluate ECS charging rule for a single day (see notebook).

    Returns a dict summarising the decision; also prints and plots if
    ``plot`` is True.
    """
    thr_wh = threshold_kwh * 1000.0
    day_n = pd.Timestamp(day_n).normalize()

    # align predictions
    if isinstance(y_pred, pd.Series):
        y_pred_s = y_pred.copy()
        if not y_pred_s.index.equals(y_test.index):
            y_pred_s = y_pred_s.reindex(y_test.index)
    else:
        y_pred_s = pd.Series(np.asarray(y_pred), index=y_test.index)

    day_np1 = day_n + pd.Timedelta(days=1)
    missing = []
    if day_n not in y_test.index:
        missing.append(str(day_n.date()))
    if day_np1 not in y_test.index:
        missing.append(str(day_np1.date()))
    if missing:
        print(f"Jour(s) absent(s) dans y_test : {', '.join(missing)}")
        print(f"Plage test: {y_test.index.min().date()} → {y_test.index.max().date()}")
        return None

    real_n = float(y_test.loc[day_n])
    real_np1 = float(y_test.loc[day_np1])
    pred_np1 = float(y_pred_s.loc[day_np1])

    c1 = real_n > thr_wh
    c2 = real_np1 < thr_wh
    c3 = pred_np1 > thr_wh
    ecs_error = bool(c1 and c2 and c3)
    decision = "ERREUR de charge ECS (sur n+1)" if ecs_error else "OK (pas d’erreur de charge ECS)"

    print("----- Vérification règle ECS -----")
    print(f"Seuil             : {threshold_kwh:.1f} kWh ({thr_wh:,.0f} Wh)")
    print(f"Jour n            : {day_n.date()} | Réel(n)   = {real_n:,.0f} Wh | Condition real(n)>seuil : {c1}")
    print(f"Jour n+1          : {day_np1.date()} | Réel(n+1) = {real_np1:,.0f} Wh | Condition real(n+1)<seuil : {c2}")
    print(f"Prédit(n+1)       : {pred_np1:,.0f} Wh | Condition pred(n+1)>seuil : {c3}")
    print(f"Décision          : {decision}")

    if plot:
        labels = ["Réel(n)", "Réel(n+1)", "Prédit(n+1)", "Seuil"]
        values = [real_n, real_np1, pred_np1, thr_wh]
        plt.figure(figsize=(8, 5))
        plt.bar(labels, values)
        plt.axhline(thr_wh, linestyle="--", linewidth=1.2)
        plt.title(f"Règle ECS — n={day_n.date()} / n+1={day_np1.date()}  |  {decision}")
        plt.ylabel("Énergie (Wh/jour)")
        plt.grid(axis="y", linestyle="--", alpha=0.5)
        plt.show()

    return {
        "day_n": day_n,
        "day_np1": day_np1,
        "threshold_wh": thr_wh,
        "real_n": real_n,
        "real_np1": real_np1,
        "pred_np1": pred_np1,
        "cond_real_n_gt_thr": c1,
        "cond_real_np1_lt_thr": c2,
        "cond_pred_np1_gt_thr": c3,
        "ecs_charge_error": ecs_error,
        "decision": decision,
    }


def backtest_ecs_rule_all_days(y_test, y_pred, seuil_kwh=7.0):
    """Run ECS rule over entire test period and return summary DataFrame."""
    thr_wh = seuil_kwh * 1000.0
    y_test_s = y_test.copy()
    y_test_s.index = pd.to_datetime(y_test_s.index).normalize()
    if isinstance(y_pred, pd.Series):
        y_pred_s = y_pred.copy()
        y_pred_s.index = pd.to_datetime(y_pred_s.index).normalize()
        y_pred_s = y_pred_s.reindex(y_test_s.index)
    else:
        y_pred_s = pd.Series(np.asarray(y_pred), index=y_test_s.index)
    Prod_reel_n = y_test_s
    Prod_reel_np1 = y_test_s.shift(-1)
    Prod_pred_np1 = y_pred_s.shift(-1)
    valid_mask = Prod_reel_np1.notna() & Prod_pred_np1.notna()
    Prod_reel_n = Prod_reel_n[valid_mask]
    Prod_reel_np1 = Prod_reel_np1[valid_mask]
    Prod_pred_np1 = Prod_pred_np1[valid_mask]
    c1 = Prod_reel_n > thr_wh
    c2 = Prod_reel_np1 < thr_wh
    c3 = Prod_pred_np1 > thr_wh
    ecs_error = (c1 & c2 & c3)
    decision = np.where(
        ecs_error,
        "ERREUR de charge ECS (sur n+1)",
        "OK (pas d’erreur de charge ECS)",
    )
    df_res = pd.DataFrame({
        "Seuil_wh": thr_wh,
        "Prod_Reel_n": Prod_reel_n,
        "Prod_Reel_np1": Prod_reel_np1,
        "Prod_Pred_np1": Prod_pred_np1,
        "cond_real_n_gt_thr": c1,
        "cond_real_np1_lt_thr": c2,
        "cond_pred_np1_gt_thr": c3,
        "ecs_charge_error": ecs_error,
        "decision": decision,
    }, index=Prod_reel_n.index)
    return df_res
