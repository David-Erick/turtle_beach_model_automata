from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import qmc

from .config import clone_with_updates
from .metrics import aggregate_metrics
from .simulation import run_simulation


def run_global_sensitivity(
    cfg: dict[str, Any],
    output_dir: str | Path,
    n_samples: int = 32,
    n_turtles: int = 20,
    seed: int = 8123,
) -> dict[str, Path]:
    bounds_map = cfg.get("calibration", {}).get("bounds", {})
    if not bounds_map:
        raise ValueError("A analise de sensibilidade usa calibration.bounds do YAML.")
    names = list(bounds_map)
    lower = np.array([float(bounds_map[n][0]) for n in names])
    upper = np.array([float(bounds_map[n][1]) for n in names])
    sampler = qmc.LatinHypercube(d=len(names), seed=seed)
    unit = sampler.random(n=n_samples)
    samples = qmc.scale(unit, lower, upper)

    rows = []
    for i, vector in enumerate(samples):
        params = dict(zip(names, map(float, vector)))
        local = clone_with_updates(cfg, params)
        summary, _ = run_simulation(
            local,
            seed=seed + 1000 + i,
            n_turtles=n_turtles,
            scenario={"artificial_scale": 1.0},
            replicate=i,
            record_tracks=False,
        )
        row = {"sample": i, **params, **aggregate_metrics(summary)}
        rows.append(row)

    samples_df = pd.DataFrame(rows)
    outputs = [
        "sea_arrival_rate",
        "disorientation_rate",
        "median_time_to_sea_s",
        "median_efficiency",
        "mean_abs_initial_heading_deg",
    ]
    corr = samples_df[names + outputs].corr(method="spearman").loc[names, outputs]
    corr_long = corr.reset_index(names="parameter").melt(id_vars="parameter", var_name="output", value_name="spearman_rho")

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    sample_path = out / "sensitivity_samples.csv"
    corr_path = out / "sensitivity_spearman.csv"
    samples_df.to_csv(sample_path, index=False)
    corr_long.to_csv(corr_path, index=False)
    return {"samples": sample_path, "correlations": corr_path}
