from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.optimize import differential_evolution

from .config import clone_with_updates
from .metrics import aggregate_metrics
from .simulation import run_simulation


DEFAULT_METRIC_WEIGHTS = {
    "sea_arrival_rate": 3.0,
    "disorientation_rate": 2.5,
    "median_time_to_sea_s": 1.0,
    "median_efficiency": 1.5,
    "mean_abs_initial_heading_deg": 1.5,
}


def _safe_distance(sim: float, obs: float, scale: float) -> float:
    if not np.isfinite(sim) or not np.isfinite(obs):
        return 2.0
    return ((sim - obs) / max(scale, 1e-9)) ** 2


def _metric_scales(obs: dict[str, float]) -> dict[str, float]:
    return {
        "sea_arrival_rate": 0.10,
        "disorientation_rate": 0.10,
        "median_time_to_sea_s": max(60.0, abs(obs.get("median_time_to_sea_s", 0.0)) * 0.20),
        "median_efficiency": 0.10,
        "mean_abs_initial_heading_deg": max(10.0, abs(obs.get("mean_abs_initial_heading_deg", 0.0)) * 0.25),
    }


def calibrate_behavior(
    cfg: dict[str, Any],
    observed_csv: str | Path,
    output_json: str | Path,
    quick: bool = False,
) -> dict[str, Any]:
    observed = pd.read_csv(observed_csv)
    required = {"arrival_sea", "disoriented", "outcome", "time_s", "path_length_m", "efficiency", "abs_initial_heading_deg", "max_landward_displacement_m"}
    missing = required - set(observed.columns)
    if missing:
        raise ValueError(f"Dados observados sem colunas necessarias: {sorted(missing)}")

    observed_metrics = aggregate_metrics(observed)
    cal_cfg = cfg.get("calibration", {})
    bounds_map = cal_cfg.get("bounds", {})
    param_names = list(bounds_map)
    if not param_names:
        raise ValueError("Defina calibration.bounds no YAML.")
    bounds = [tuple(map(float, bounds_map[name])) for name in param_names]
    weights = {**DEFAULT_METRIC_WEIGHTS, **cal_cfg.get("metric_weights", {})}
    scales = _metric_scales(observed_metrics)
    n_key = "quick_n_turtles_per_evaluation" if quick else "n_turtles_per_evaluation"
    seed_key = "quick_common_random_seeds" if quick else "common_random_seeds"
    n_sim = int(cal_cfg.get(n_key, cal_cfg.get("n_turtles_per_evaluation", min(len(observed), 50))))
    seeds = list(map(int, cal_cfg.get(seed_key, cal_cfg.get("common_random_seeds", [1201, 1202]))))

    def objective(vector: np.ndarray) -> float:
        updates = dict(zip(param_names, map(float, vector)))
        local_cfg = clone_with_updates(cfg, updates)
        frames = []
        for rep, seed in enumerate(seeds):
            s, _ = run_simulation(local_cfg, seed=seed, n_turtles=n_sim, scenario={"artificial_scale": 1.0}, replicate=rep, record_tracks=False)
            frames.append(s)
        sim_metrics = aggregate_metrics(pd.concat(frames, ignore_index=True))
        value = 0.0
        for metric, weight in weights.items():
            value += float(weight) * _safe_distance(sim_metrics.get(metric, np.nan), observed_metrics.get(metric, np.nan), scales[metric])
        return float(value)

    maxiter = int(cal_cfg.get("quick_maxiter" if quick else "maxiter", 4 if quick else 24))
    popsize = int(cal_cfg.get("quick_popsize" if quick else "popsize", 4 if quick else 8))
    seed = int(cal_cfg.get("optimizer_seed", 2026))
    result = differential_evolution(
        objective,
        bounds=bounds,
        seed=seed,
        maxiter=maxiter,
        popsize=popsize,
        polish=not quick,
        workers=1,
        updating="immediate",
        tol=float(cal_cfg.get("quick_tolerance" if quick else "tolerance", 0.15 if quick else 0.02)),
    )

    best = dict(zip(param_names, map(float, result.x)))
    best_cfg = clone_with_updates(cfg, best)
    eval_frames = []
    eval_key = "quick_evaluation_seeds" if quick else "evaluation_seeds"
    eval_seeds = list(map(int, cal_cfg.get(eval_key, cal_cfg.get("evaluation_seeds", [2201, 2202, 2203, 2204]))))
    for rep, seed_value in enumerate(eval_seeds):
        s, _ = run_simulation(best_cfg, seed=seed_value, n_turtles=n_sim, scenario={"artificial_scale": 1.0}, replicate=rep, record_tracks=False)
        eval_frames.append(s)
    simulated_metrics = aggregate_metrics(pd.concat(eval_frames, ignore_index=True))

    payload = {
        "status": "calibracao_demonstrativa" if "synthetic" in str(observed_csv).lower() else "calibracao_com_dados_fornecidos",
        "parameters": best,
        "objective": float(result.fun),
        "success": bool(result.success),
        "message": str(result.message),
        "n_function_evaluations": int(result.nfev),
        "observed_metrics": observed_metrics,
        "simulated_metrics": simulated_metrics,
        "parameter_bounds": {k: list(map(float, bounds_map[k])) for k in param_names},
        "observed_file": str(Path(observed_csv).resolve()),
        "notes": [
            "A calibracao ajusta resumos de trajetorias, nao lux absolutos.",
            "Dados sinteticos servem apenas para verificar o fluxo computacional e a recuperacao aproximada de parametros.",
            "Para inferencia ecologica, substitua o arquivo sintetico por trajetorias independentes da praia estudada."
        ],
    }
    output = Path(output_json)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload
