from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def aggregate_metrics(df: pd.DataFrame) -> dict[str, float]:
    if df.empty:
        raise ValueError("Nao ha dados para resumir.")
    sea = float(df["arrival_sea"].mean())
    dis = float(df["disoriented"].mean())
    pred = float((df["outcome"] == "predated").mean())
    exh = float((df["outcome"] == "exhausted").mean())
    cens = float((df["outcome"] == "censored").mean())
    sea_df = df[df["outcome"] == "sea"]
    return {
        "n": float(len(df)),
        "sea_arrival_rate": sea,
        "disorientation_rate": dis,
        "predation_rate": pred,
        "exhaustion_rate": exh,
        "censored_rate": cens,
        "median_time_to_sea_s": float(sea_df["time_s"].median()) if not sea_df.empty else float("nan"),
        "median_path_length_m": float(df["path_length_m"].median()),
        "median_efficiency": float(df["efficiency"].median()),
        "mean_abs_initial_heading_deg": float(df["abs_initial_heading_deg"].mean()),
        "median_max_landward_m": float(df["max_landward_displacement_m"].median()),
    }


def scenario_summary(turtles: pd.DataFrame) -> pd.DataFrame:
    group_cols = [c for c in ["scenario", "replicate"] if c in turtles.columns]
    rows: list[dict[str, Any]] = []
    for keys, group in turtles.groupby(group_cols, dropna=False, sort=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
        row = dict(zip(group_cols, keys))
        row.update(aggregate_metrics(group))
        rows.append(row)
    return pd.DataFrame(rows)


def summarize_replicates(run_metrics: pd.DataFrame) -> pd.DataFrame:
    rows = []
    metric_cols = [c for c in run_metrics.columns if c not in {"scenario", "replicate"}]
    for scenario, group in run_metrics.groupby("scenario", sort=False):
        row: dict[str, Any] = {"scenario": scenario, "n_replicates": int(len(group))}
        for col in metric_cols:
            vals = pd.to_numeric(group[col], errors="coerce").dropna().to_numpy(float)
            if len(vals) == 0:
                row[f"{col}_mean"] = np.nan
                row[f"{col}_sd"] = np.nan
                row[f"{col}_ci95_low"] = np.nan
                row[f"{col}_ci95_high"] = np.nan
                continue
            mean = float(np.mean(vals))
            sd = float(np.std(vals, ddof=1)) if len(vals) > 1 else 0.0
            se = sd / np.sqrt(len(vals)) if len(vals) > 1 else 0.0
            row[f"{col}_mean"] = mean
            row[f"{col}_sd"] = sd
            row[f"{col}_ci95_low"] = mean - 1.96 * se
            row[f"{col}_ci95_high"] = mean + 1.96 * se
        rows.append(row)
    return pd.DataFrame(rows)
