from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .environment import BeachEnvironment


def summarize_observed_coordinates(
    cfg: dict[str, Any],
    coordinates_csv: str | Path,
    output_csv: str | Path,
) -> pd.DataFrame:
    """Converte coordenadas digitalizadas de video em resumos usados na calibracao.

    Colunas minimas: turtle_id, time_s, x_m, y_m. A coluna outcome e opcional;
    quando ausente, o desfecho e inferido da posicao final e marcado como censored
    se o individuo nao alcancou a linha d'agua.
    """
    env = BeachEnvironment(cfg)
    df = pd.read_csv(coordinates_csv)
    required = {"turtle_id", "time_s", "x_m", "y_m"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Coordenadas observadas sem colunas: {sorted(missing)}")
    if "nest_id" not in df:
        df["nest_id"] = "observed"
    if "outcome" not in df:
        df["outcome"] = ""

    initial_window = float(cfg["metrics"].get("initial_window_m", 5.0))
    angle_threshold = float(cfg["metrics"].get("disorientation_angle_deg", 30.0))
    efficiency_threshold = float(cfg["metrics"].get("disorientation_efficiency_threshold", 0.55))
    rows = []

    for turtle_id, group in df.groupby("turtle_id", sort=False):
        g = group.sort_values("time_s").reset_index(drop=True)
        x = g["x_m"].to_numpy(float)
        y = g["y_m"].to_numpy(float)
        t = g["time_s"].to_numpy(float)
        dx = np.diff(x)
        dy = np.diff(y)
        step_lengths = np.hypot(dx, dy)
        path_length = float(step_lengths.sum())
        start_x, start_y = float(x[0]), float(y[0])
        end_x, end_y = float(x[-1]), float(y[-1])
        direct = max(env.waterline_x(start_y) - start_x, 0.0)
        efficiency = direct / path_length if path_length > 0 else np.nan

        disp_x = x - start_x
        disp_y = y - start_y
        radial = np.hypot(disp_x, disp_y)
        candidates = np.where(radial >= initial_window)[0]
        idx = int(candidates[0]) if len(candidates) else len(g) - 1
        heading = float(np.degrees(np.arctan2(disp_y[idx], disp_x[idx]))) if radial[idx] > 0 else np.nan
        landward_steps = int((dx < 0).sum())
        moving_steps = int((step_lengths > 0).sum())
        landward_fraction = landward_steps / moving_steps if moving_steps else 0.0
        max_landward = float(max(start_x - float(x.min()), 0.0))

        recorded = str(g["outcome"].dropna().iloc[-1]).strip().lower() if len(g) else ""
        if recorded in {"sea", "predated", "exhausted", "landward_exit", "lateral_exit", "censored"}:
            outcome = recorded
        elif env.is_water(end_x, end_y):
            outcome = "sea"
        else:
            outcome = "censored"
        disoriented = bool(
            (np.isfinite(heading) and abs(heading) > angle_threshold)
            or (np.isfinite(efficiency) and efficiency < efficiency_threshold)
            or outcome in {"landward_exit", "lateral_exit"}
        )

        rows.append({
            "replicate": 0,
            "turtle_id": turtle_id,
            "nest_id": str(g["nest_id"].iloc[0]),
            "outcome": outcome,
            "arrival_sea": int(outcome == "sea"),
            "disoriented": int(disoriented),
            "time_s": float(t[-1] - t[0]),
            "path_length_m": path_length,
            "direct_distance_m": direct,
            "efficiency": efficiency,
            "initial_heading_deg": heading,
            "abs_initial_heading_deg": abs(heading) if np.isfinite(heading) else np.nan,
            "max_landward_displacement_m": max_landward,
            "landward_step_fraction": landward_fraction,
            "remaining_energy": np.nan,
            "start_x_m": start_x,
            "start_y_m": start_y,
            "end_x_m": end_x,
            "end_y_m": end_y,
        })

    out = pd.DataFrame(rows)
    path = Path(output_csv)
    path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(path, index=False)
    return out
