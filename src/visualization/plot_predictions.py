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

