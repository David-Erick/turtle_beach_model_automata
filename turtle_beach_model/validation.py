from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .config import clone_with_updates
from .environment import BeachEnvironment
from .metrics import aggregate_metrics
from .simulation import run_simulation


def validate_light_interpolation(cfg: dict[str, Any], output_json: str | Path) -> dict[str, Any]:
    """Validacao cruzada leave-one-site-out do perfil luminoso ao longo da costa."""
    env = BeachEnvironment(cfg)
    df = env.light_site.sort_values("y_m").reset_index(drop=True)
    directions = [d for d in ["dune", "ocean", "north", "south", "zenith"] if d in df.columns]
    residual_rows = []
    for i in range(len(df)):
        train = df.drop(index=i).sort_values("y_m")
        y0 = float(df.loc[i, "y_m"])
        for direction in directions:
            pred = float(np.interp(y0, train["y_m"], train[direction]))
            obs = float(df.loc[i, direction])
            residual_rows.append({
                "site_id": str(df.loc[i, "site_id"]),
                "direction": direction,
                "observed_mag_arcsec2": obs,
                "predicted_mag_arcsec2": pred,
                "residual": pred - obs,
            })
    residuals = pd.DataFrame(residual_rows)
    by_direction = {}
    for direction, group in residuals.groupby("direction"):
        err = group["residual"].to_numpy(float)
        by_direction[direction] = {
            "rmse_mag_arcsec2": float(np.sqrt(np.mean(err**2))),
            "mae_mag_arcsec2": float(np.mean(np.abs(err))),
            "bias_mag_arcsec2": float(np.mean(err)),
        }
    all_err = residuals["residual"].to_numpy(float)
    payload = {
        "method": "leave_one_site_out_linear_interpolation",
        "n_sites": int(len(df)),
        "overall_rmse_mag_arcsec2": float(np.sqrt(np.mean(all_err**2))),
        "overall_mae_mag_arcsec2": float(np.mean(np.abs(all_err))),
        "by_direction": by_direction,
        "caveat": "O erro avalia somente a interpolacao ao longo dos nove pontos; nao valida a separacao entre componentes natural e artificial.",
    }
    path = Path(output_json)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    residuals.to_csv(path.with_name(path.stem + "_residuals.csv"), index=False)
    return payload


def validate_behavior(
    cfg: dict[str, Any],
    observed_csv: str | Path,
    calibration_json: str | Path,
    output_json: str | Path,
    n_replicates: int | None = None,
) -> dict[str, Any]:
    observed = pd.read_csv(observed_csv)
    obs_metrics = aggregate_metrics(observed)
    calibration = json.loads(Path(calibration_json).read_text(encoding="utf-8"))
    work_cfg = clone_with_updates(cfg, calibration["parameters"])
    vcfg = cfg.get("validation", {})
    reps = int(n_replicates if n_replicates is not None else vcfg.get("n_replicates", 10))
    n_turtles = int(vcfg.get("n_turtles_per_replicate", max(10, len(observed))))
    seed0 = int(vcfg.get("base_seed", 73000))
    frames = []
    for rep in range(reps):
        summary, _ = run_simulation(
            work_cfg,
            seed=seed0 + rep,
            n_turtles=n_turtles,
            scenario={"artificial_scale": 1.0},
            replicate=rep,
            record_tracks=False,
        )
        frames.append(summary)
    simulated = pd.concat(frames, ignore_index=True)
    sim_metrics = aggregate_metrics(simulated)
    metrics = [
        "sea_arrival_rate",
        "disorientation_rate",
        "median_time_to_sea_s",
        "median_efficiency",
        "mean_abs_initial_heading_deg",
    ]
    comparison = {}
    for key in metrics:
        obs = float(obs_metrics[key])
        sim = float(sim_metrics[key])
        comparison[key] = {
            "observed": obs,
            "simulated": sim,
            "difference": sim - obs,
            "relative_error": (sim - obs) / obs if np.isfinite(obs) and abs(obs) > 1e-12 else None,
        }
    payload = {
        "status": "validacao_em_dados_independentes" if "synthetic" not in str(observed_csv).lower() else "validacao_demonstrativa_sintetica",
        "observed_file": str(Path(observed_csv).resolve()),
        "calibration_file": str(Path(calibration_json).resolve()),
        "n_replicates": reps,
        "n_turtles_per_replicate": n_turtles,
        "observed_metrics": obs_metrics,
        "simulated_metrics": sim_metrics,
        "comparison": comparison,
        "interpretation": "Erros pequenos apoiam validade preditiva apenas para o dominio, periodo e protocolo representados pelo conjunto de validacao.",
    }
    path = Path(output_json)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload
