from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .environment import BeachEnvironment


SCENARIO_LABELS = {
    "baseline": "Referência",
    "lights_off": "Luzes desligadas",
    "shielded_70pct": "Blindagem 70%",
    "amber_proxy": "Espectro âmbar (proxy)",
    "bright_moon_proxy": "Lua mais intensa (proxy)",
    "combined_mitigation": "Mitigação combinada",
}


def plot_light_profile(env: BeachEnvironment, output: Path) -> None:
    df = env.light_site.sort_values("y_m")
    fig, ax = plt.subplots(figsize=(8.0, 4.6))
    ax.plot(df["y_m"], df["dune"], marker="o", label="Duna/terra")
    ax.plot(df["y_m"], df["ocean"], marker="o", label="Oceano")
    ax.plot(df["y_m"], df["north"], marker="o", label="Norte")
    ax.plot(df["y_m"], df["south"], marker="o", label="Sul")
    ax.invert_yaxis()
    ax.set_xlabel("Posição ao longo da costa (m)")
    ax.set_ylabel("Brilho SQM (mag/arcsec²; menor = mais claro)")
    ax.set_title("Levantamento luminoso direcional usado na calibração ambiental")
    ax.legend(ncol=2)
    fig.tight_layout()
    fig.savefig(output, dpi=180)
    plt.close(fig)


def plot_scenario_arrival(summary_csv: Path, output: Path) -> None:
    df = pd.read_csv(summary_csv)
    x = np.arange(len(df))
    y = df["sea_arrival_rate_mean"].to_numpy(float)
    low = df["sea_arrival_rate_ci95_low"].to_numpy(float)
    high = df["sea_arrival_rate_ci95_high"].to_numpy(float)
    yerr = np.vstack([y - low, high - y])
    fig, ax = plt.subplots(figsize=(8.2, 4.8))
    ax.bar(x, y, yerr=yerr, capsize=4)
    labels = [SCENARIO_LABELS.get(v, v) for v in df["scenario"]]
    ax.set_xticks(x, labels, rotation=25, ha="right")
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Proporção que alcançou o mar")
    ax.set_title("Comparação dos cenários de iluminação")
    fig.tight_layout()
    fig.savefig(output, dpi=180)
    plt.close(fig)


def plot_scenario_disorientation(summary_csv: Path, output: Path) -> None:
    df = pd.read_csv(summary_csv)
    x = np.arange(len(df))
    y = df["disorientation_rate_mean"].to_numpy(float)
    low = df["disorientation_rate_ci95_low"].to_numpy(float)
    high = df["disorientation_rate_ci95_high"].to_numpy(float)
    yerr = np.vstack([y - low, high - y])
    fig, ax = plt.subplots(figsize=(8.2, 4.8))
    ax.bar(x, y, yerr=yerr, capsize=4)
    labels = [SCENARIO_LABELS.get(v, v) for v in df["scenario"]]
    ax.set_xticks(x, labels, rotation=25, ha="right")
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Proporção operacionalmente desorientada")
    ax.set_title("Desorientação por cenário")
    fig.tight_layout()
    fig.savefig(output, dpi=180)
    plt.close(fig)


def plot_sample_tracks(env: BeachEnvironment, tracks_csv: Path, output: Path, scenario: str = "baseline") -> None:
    tracks = pd.read_csv(tracks_csv)
    tracks = tracks[tracks["scenario"] == scenario]
    if tracks.empty:
        return
    ids = tracks["turtle_id"].drop_duplicates().head(20)
    tracks = tracks[tracks["turtle_id"].isin(ids)]
    fig, ax = plt.subplots(figsize=(8.4, 5.1))
    ys = np.linspace(0, env.length_m, 250)
    water = np.array([env.waterline_x(y) for y in ys])
    ax.plot(water, ys, linewidth=2.0, label="Linha d'água")
    ax.plot(np.zeros_like(ys), ys, linewidth=2.0, label="Limite da duna")
    for _, group in tracks.groupby("turtle_id"):
        ax.plot(group["x_m"], group["y_m"], linewidth=1.0, alpha=0.75)
    ax.set_xlabel("Distância transversal (m; oceano à direita)")
    ax.set_ylabel("Posição ao longo da costa (m)")
    ax.set_title(f"Amostra de trajetórias — cenário {SCENARIO_LABELS.get(scenario, scenario)}")
    ax.legend()
    fig.tight_layout()
    fig.savefig(output, dpi=180)
    plt.close(fig)


def plot_calibration(calibration_json: Path, output: Path) -> None:
    payload = json.loads(calibration_json.read_text(encoding="utf-8"))
    obs = payload["observed_metrics"]
    sim = payload["simulated_metrics"]
    names = ["sea_arrival_rate", "disorientation_rate", "median_efficiency"]
    labels = ["Chegada ao mar", "Desorientação", "Eficiência mediana"]
    x = np.arange(len(names))
    width = 0.36
    fig, ax = plt.subplots(figsize=(7.5, 4.5))
    ax.bar(x - width / 2, [obs[n] for n in names], width, label="Observado")
    ax.bar(x + width / 2, [sim[n] for n in names], width, label="Simulado")
    ax.set_xticks(x, labels)
    ax.set_ylim(0, 1.05)
    ax.set_title("Ajuste da calibração comportamental")
    ax.legend()
    fig.tight_layout()
    fig.savefig(output, dpi=180)
    plt.close(fig)



def plot_sensitivity(correlations_csv: Path, output: Path, target: str = "sea_arrival_rate") -> None:
    df = pd.read_csv(correlations_csv)
    df = df[df["output"] == target].sort_values("spearman_rho")
    fig, ax = plt.subplots(figsize=(7.4, 4.5))
    ax.barh(df["parameter"], df["spearman_rho"])
    ax.axvline(0.0, linewidth=1.0)
    ax.set_xlabel("Correlacao de Spearman")
    ax.set_title(f"Sensibilidade global — {target}")
    fig.tight_layout()
    fig.savefig(output, dpi=180)
    plt.close(fig)

def make_all_plots(cfg: dict[str, Any], experiment_dir: str | Path, calibration_json: str | Path | None = None) -> list[Path]:
    out_dir = Path(experiment_dir) / "figures"
    out_dir.mkdir(parents=True, exist_ok=True)
    env = BeachEnvironment(cfg)
    outputs = [
        out_dir / "light_profile.png",
        out_dir / "scenario_sea_arrival.png",
        out_dir / "scenario_disorientation.png",
        out_dir / "sample_tracks_baseline.png",
    ]
    plot_light_profile(env, outputs[0])
    plot_scenario_arrival(Path(experiment_dir) / "scenario_summary.csv", outputs[1])
    plot_scenario_disorientation(Path(experiment_dir) / "scenario_summary.csv", outputs[2])
    plot_sample_tracks(env, Path(experiment_dir) / "sample_tracks.csv", outputs[3], "baseline")
    if calibration_json:
        cal_out = out_dir / "calibration_fit.png"
        plot_calibration(Path(calibration_json), cal_out)
        outputs.append(cal_out)
    return outputs
