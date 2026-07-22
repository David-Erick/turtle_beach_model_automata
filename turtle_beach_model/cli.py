from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from .calibration import calibrate_behavior
from .config import clone_with_updates, load_config
from .environment import BeachEnvironment
from .experiments import run_experiments
from .observations import summarize_observed_coordinates
from .plots import make_all_plots, plot_sensitivity
from .simulation import run_simulation
from .sensitivity import run_global_sensitivity
from .validation import validate_behavior, validate_light_interpolation


def cmd_validate(args: argparse.Namespace) -> None:
    cfg = load_config(args.config)
    env = BeachEnvironment(cfg)
    print(json.dumps(env.diagnostics(), ensure_ascii=False, indent=2))


def cmd_synthetic(args: argparse.Namespace) -> None:
    cfg = load_config(args.config)
    truth = cfg.get("synthetic_truth", {})
    truth_cfg = clone_with_updates(cfg, truth) if truth else cfg
    frames = []
    for rep in range(args.replicates):
        s, _ = run_simulation(truth_cfg, args.seed + rep, args.n_turtles, {"artificial_scale": 1.0}, rep, record_tracks=False)
        frames.append(s)
    out = pd.concat(frames, ignore_index=True)
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(path, index=False)
    print(f"Dados sinteticos gravados em: {path}")
    print(out["outcome"].value_counts(normalize=True).to_string())




def cmd_validate_light(args: argparse.Namespace) -> None:
    cfg = load_config(args.config)
    payload = validate_light_interpolation(cfg, args.output)
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def cmd_validate_behavior(args: argparse.Namespace) -> None:
    cfg = load_config(args.config)
    payload = validate_behavior(cfg, args.observed, args.calibration, args.output, args.replicates)
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def cmd_sensitivity(args: argparse.Namespace) -> None:
    cfg = load_config(args.config)
    paths = run_global_sensitivity(cfg, args.output_dir, args.samples, args.n_turtles, args.seed)
    figure = Path(args.output_dir) / "sensitivity_sea_arrival.png"
    plot_sensitivity(paths["correlations"], figure)
    print(f"samples: {paths['samples']}")
    print(f"correlations: {paths['correlations']}")
    print(f"figure: {figure}")

def cmd_summarize_observed(args: argparse.Namespace) -> None:
    cfg = load_config(args.config)
    out = summarize_observed_coordinates(cfg, args.coordinates, args.output)
    print(f"Resumos observados gravados em: {Path(args.output).resolve()}")
    print(out["outcome"].value_counts(dropna=False).to_string())

def cmd_calibrate(args: argparse.Namespace) -> None:
    cfg = load_config(args.config)
    result = calibrate_behavior(cfg, args.observed, args.output, args.quick)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_experiment(args: argparse.Namespace) -> None:
    cfg = load_config(args.config)
    paths = run_experiments(cfg, args.output_dir, args.calibration, args.replicates, args.n_turtles)
    for name, path in paths.items():
        print(f"{name}: {path}")


def cmd_plot(args: argparse.Namespace) -> None:
    cfg = load_config(args.config)
    paths = make_all_plots(cfg, args.experiment_dir, args.calibration)
    for path in paths:
        print(path)


def cmd_demo(args: argparse.Namespace) -> None:
    cfg = load_config(args.config)
    root = Path(args.output_dir)
    root.mkdir(parents=True, exist_ok=True)
    synthetic = root / "synthetic_observed_tracks.csv"
    synthetic_validation = root / "synthetic_validation_tracks.csv"
    calibration = root / "calibration.json"
    behavior_validation = root / "behavior_validation.json"
    light_validation = root / "light_validation.json"
    experiment_dir = root / "experiments"
    sensitivity_dir = root / "sensitivity"

    # Geracao de observacoes sinteticas para provar que o pipeline executa.
    # Estes arquivos NAO substituem trajetorias reais da praia.
    truth = cfg.get("synthetic_truth", {})
    truth_cfg = clone_with_updates(cfg, truth) if truth else cfg
    frames = []
    for rep in range(args.synthetic_replicates):
        summary, _ = run_simulation(truth_cfg, args.seed + rep, args.synthetic_turtles, {"artificial_scale": 1.0}, rep, record_tracks=False)
        frames.append(summary)
    pd.concat(frames, ignore_index=True).to_csv(synthetic, index=False)

    validation_frames = []
    for rep in range(args.validation_data_replicates):
        summary, _ = run_simulation(truth_cfg, args.seed + 1000 + rep, args.validation_turtles, {"artificial_scale": 1.0}, rep, record_tracks=False)
        validation_frames.append(summary)
    pd.concat(validation_frames, ignore_index=True).to_csv(synthetic_validation, index=False)

    calibrate_behavior(cfg, synthetic, calibration, quick=args.quick)
    validate_light_interpolation(cfg, light_validation)
    validation_cfg = dict(cfg)
    validation_cfg["validation"] = dict(cfg.get("validation", {}))
    validation_cfg["validation"]["n_turtles_per_replicate"] = args.validation_turtles
    validate_behavior(validation_cfg, synthetic_validation, calibration, behavior_validation, args.validation_replicates)
    run_experiments(cfg, experiment_dir, calibration, args.replicates, args.n_turtles)
    make_all_plots(cfg, experiment_dir, calibration)
    sensitivity_paths = run_global_sensitivity(cfg, sensitivity_dir, args.sensitivity_samples, args.sensitivity_turtles, args.seed + 2000)
    plot_sensitivity(sensitivity_paths["correlations"], sensitivity_dir / "sensitivity_sea_arrival.png")
    print(f"Fluxo demonstrativo concluido em: {root.resolve()}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Modelo de orientacao de filhotes em praia")
    sub = p.add_subparsers(dest="command", required=True)

    v = sub.add_parser("validate-data", help="Valida entradas e mostra diagnosticos")
    v.add_argument("--config", required=True)
    v.set_defaults(func=cmd_validate)


    vl = sub.add_parser("validate-light", help="Faz validacao cruzada da interpolacao luminosa")
    vl.add_argument("--config", required=True)
    vl.add_argument("--output", required=True)
    vl.set_defaults(func=cmd_validate_light)

    vb = sub.add_parser("validate-calibration", help="Compara a calibracao com dados comportamentais independentes")
    vb.add_argument("--config", required=True)
    vb.add_argument("--observed", required=True)
    vb.add_argument("--calibration", required=True)
    vb.add_argument("--output", required=True)
    vb.add_argument("--replicates", type=int)
    vb.set_defaults(func=cmd_validate_behavior)

    sn = sub.add_parser("sensitivity", help="Executa amostragem por hipercubo latino e correlacoes de Spearman")
    sn.add_argument("--config", required=True)
    sn.add_argument("--output-dir", required=True)
    sn.add_argument("--samples", type=int, default=32)
    sn.add_argument("--n-turtles", type=int, default=20)
    sn.add_argument("--seed", type=int, default=8123)
    sn.set_defaults(func=cmd_sensitivity)

    s = sub.add_parser("synthetic-data", help="Gera trajetorias-resumo sinteticas para teste")
    s.add_argument("--config", required=True)
    s.add_argument("--output", required=True)
    s.add_argument("--replicates", type=int, default=3)
    s.add_argument("--n-turtles", type=int, default=30)
    s.add_argument("--seed", type=int, default=9000)
    s.set_defaults(func=cmd_synthetic)


    o = sub.add_parser("summarize-observed", help="Converte coordenadas de video em resumos de calibracao")
    o.add_argument("--config", required=True)
    o.add_argument("--coordinates", required=True)
    o.add_argument("--output", required=True)
    o.set_defaults(func=cmd_summarize_observed)

    c = sub.add_parser("calibrate", help="Calibra parametros comportamentais")
    c.add_argument("--config", required=True)
    c.add_argument("--observed", required=True)
    c.add_argument("--output", required=True)
    c.add_argument("--quick", action="store_true")
    c.set_defaults(func=cmd_calibrate)

    e = sub.add_parser("experiment", help="Executa os cenarios de Monte Carlo")
    e.add_argument("--config", required=True)
    e.add_argument("--output-dir", required=True)
    e.add_argument("--calibration")
    e.add_argument("--replicates", type=int)
    e.add_argument("--n-turtles", type=int)
    e.set_defaults(func=cmd_experiment)

    g = sub.add_parser("plot", help="Gera figuras a partir dos resultados")
    g.add_argument("--config", required=True)
    g.add_argument("--experiment-dir", required=True)
    g.add_argument("--calibration")
    g.set_defaults(func=cmd_plot)

    d = sub.add_parser("demo", help="Executa dados sinteticos, calibracao, cenarios e figuras")
    d.add_argument("--config", required=True)
    d.add_argument("--output-dir", required=True)
    d.add_argument("--quick", action="store_true")
    d.add_argument("--synthetic-replicates", type=int, default=3)
    d.add_argument("--synthetic-turtles", type=int, default=25)
    d.add_argument("--replicates", type=int, default=8)
    d.add_argument("--n-turtles", type=int, default=30)
    d.add_argument("--seed", type=int, default=9000)
    d.add_argument("--validation-data-replicates", type=int, default=2)
    d.add_argument("--validation-replicates", type=int, default=4)
    d.add_argument("--validation-turtles", type=int, default=20)
    d.add_argument("--sensitivity-samples", type=int, default=16)
    d.add_argument("--sensitivity-turtles", type=int, default=15)
    d.set_defaults(func=cmd_demo)
    return p


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
