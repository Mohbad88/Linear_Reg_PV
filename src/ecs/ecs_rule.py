
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
