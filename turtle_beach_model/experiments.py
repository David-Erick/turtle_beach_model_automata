from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from .config import clone_with_updates
from .metrics import scenario_summary, summarize_replicates
from .simulation import run_simulation


def run_experiments(
    cfg: dict[str, Any],
    output_dir: str | Path,
    calibration_json: str | Path | None = None,
    n_replicates: int | None = None,
    n_turtles: int | None = None,
) -> dict[str, Path]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    work_cfg = cfg
    if calibration_json:
        payload = json.loads(Path(calibration_json).read_text(encoding="utf-8"))
        work_cfg = clone_with_updates(cfg, payload["parameters"])

    scenarios = cfg.get("experiments", {}).get("scenarios", {})
    if not scenarios:
        raise ValueError("Nenhum cenario definido em experiments.scenarios.")
    reps = int(n_replicates if n_replicates is not None else cfg["experiments"].get("n_replicates", 30))
    turtles_per_run = int(n_turtles if n_turtles is not None else cfg["simulation"]["n_turtles"])
    base_seed = int(cfg["experiments"].get("base_seed", 41000))

    turtle_frames = []
    track_frames = []
    for s_idx, (name, params) in enumerate(scenarios.items()):
        for rep in range(reps):
            seed = base_seed + s_idx * 10000 + rep
            save_tracks = rep < int(cfg["experiments"].get("track_replicates_to_save", 1))
            summary, tracks = run_simulation(work_cfg, seed, turtles_per_run, params, rep, record_tracks=save_tracks)
            summary.insert(0, "scenario", name)
            tracks.insert(0, "scenario", name)
            turtle_frames.append(summary)
            # Salva trajetorias apenas para as primeiras repeticoes para conter o tamanho.
            if rep < int(cfg["experiments"].get("track_replicates_to_save", 1)):
                track_frames.append(tracks)

    turtles = pd.concat(turtle_frames, ignore_index=True)
    tracks = pd.concat(track_frames, ignore_index=True) if track_frames else pd.DataFrame()
    runs = scenario_summary(turtles)
    overall = summarize_replicates(runs)

    paths = {
        "turtles": output / "turtle_results.csv",
        "tracks": output / "sample_tracks.csv",
        "run_metrics": output / "run_metrics.csv",
        "scenario_summary": output / "scenario_summary.csv",
    }
    turtles.to_csv(paths["turtles"], index=False)
    tracks.to_csv(paths["tracks"], index=False)
    runs.to_csv(paths["run_metrics"], index=False)
    overall.to_csv(paths["scenario_summary"], index=False)
    return paths
