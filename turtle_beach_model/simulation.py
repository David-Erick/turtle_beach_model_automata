from __future__ import annotations

from dataclasses import asdict
from typing import Any

import numpy as np
import pandas as pd

from .agents import Turtle
from .environment import BeachEnvironment
from .movement import choose_move
from .processes import energy_cost, predation_probability


def _sample_positive(rng: np.random.Generator, mean: float, cv: float, lower: float = 1e-6) -> float:
    if cv <= 0:
        return max(float(mean), lower)
    sigma2 = np.log1p(cv * cv)
    sigma = np.sqrt(sigma2)
    mu = np.log(max(mean, lower)) - 0.5 * sigma2
    return max(float(rng.lognormal(mu, sigma)), lower)


def _make_turtle(i: int, env: BeachEnvironment, cfg: dict[str, Any], rng: np.random.Generator) -> Turtle:
    b = cfg["behavior"]
    nest_id, x, y = env.sample_nest(rng)
    cv = float(b.get("individual_cv", 0.12))
    persistence = float(np.clip(rng.normal(float(b["persistence"]), max(cv * 0.25, 1e-6)), 0.0, 5.0))
    energy = max(float(rng.normal(float(cfg["processes"].get("initial_energy_mean", 1.0)), float(cfg["processes"].get("initial_energy_sd", 0.08)))), 0.05)
    turtle = Turtle(
        turtle_id=i,
        nest_id=nest_id,
        x_m=x,
        y_m=y,
        start_x_m=x,
        start_y_m=y,
        energy=energy,
        kappa_sea=_sample_positive(rng, float(b["kappa_sea"]), cv),
        kappa_artificial=_sample_positive(rng, float(b["kappa_artificial"]), cv),
        kappa_dune=_sample_positive(rng, float(b["kappa_dune"]), cv),
        kappa_slope=_sample_positive(rng, float(b.get("kappa_slope", 0.0)), cv),
        persistence=persistence,
        temperature=_sample_positive(rng, float(b["temperature"]), cv),
    )
    turtle.history.append((0.0, x, y))
    return turtle


def _initial_heading_deg(turtle: Turtle, initial_window_m: float) -> float:
    if turtle.first_window_heading_deg is not None:
        return float(turtle.first_window_heading_deg)
    disp = np.array([turtle.x_m - turtle.start_x_m, turtle.y_m - turtle.start_y_m])
    if np.linalg.norm(disp) > 0:
        return float(np.degrees(np.arctan2(disp[1], disp[0])))
    return float("nan")


def _summarize_turtle(t: Turtle, env: BeachEnvironment, cfg: dict[str, Any]) -> dict[str, Any]:
    direct = max(env.waterline_x(t.start_y_m) - t.start_x_m, 0.0)
    efficiency = direct / t.path_length_m if t.path_length_m > 0 else np.nan
    initial_window = float(cfg["metrics"].get("initial_window_m", 5.0))
    heading = _initial_heading_deg(t, initial_window)
    landward_fraction = t.landward_steps / t.moving_steps if t.moving_steps > 0 else 0.0
    angle_threshold = float(cfg["metrics"].get("disorientation_angle_deg", 30.0))
    efficiency_threshold = float(cfg["metrics"].get("disorientation_efficiency_threshold", 0.55))
    disoriented = bool(
        (np.isfinite(heading) and abs(heading) > angle_threshold)
        or (np.isfinite(efficiency) and efficiency < efficiency_threshold)
        or t.outcome in {"landward_exit", "lateral_exit"}
    )
    return {
        "turtle_id": t.turtle_id,
        "nest_id": t.nest_id,
        "outcome": t.outcome,
        "arrival_sea": int(t.outcome == "sea"),
        "disoriented": int(disoriented),
        "time_s": t.time_s,
        "path_length_m": t.path_length_m,
        "direct_distance_m": direct,
        "efficiency": efficiency,
        "initial_heading_deg": heading,
        "abs_initial_heading_deg": abs(heading) if np.isfinite(heading) else np.nan,
        "max_landward_displacement_m": t.max_landward_displacement_m,
        "landward_step_fraction": landward_fraction,
        "remaining_energy": t.energy,
        "start_x_m": t.start_x_m,
        "start_y_m": t.start_y_m,
        "end_x_m": t.x_m,
        "end_y_m": t.y_m,
    }


def run_simulation(
    cfg: dict[str, Any],
    seed: int,
    n_turtles: int | None = None,
    scenario: dict[str, float] | None = None,
    replicate: int = 0,
    record_tracks: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    env = BeachEnvironment(cfg)
    rng = np.random.default_rng(int(seed))
    n = int(n_turtles if n_turtles is not None else cfg["simulation"]["n_turtles"])
    turtles = [_make_turtle(i, env, cfg, rng) for i in range(n)]
    max_steps = int(np.ceil(float(cfg["simulation"]["max_time_s"]) / env.dt_s))
    track_stride = max(int(cfg["simulation"].get("track_stride", 1)), 1)
    bcfg = cfg["behavior"]
    pcfg = cfg["processes"]

    track_rows: list[dict[str, Any]] = []
    if record_tracks:
        for t in turtles:
            track_rows.append({"replicate": replicate, "turtle_id": t.turtle_id, "step": 0, "time_s": 0.0, "x_m": t.x_m, "y_m": t.y_m, "outcome": t.outcome})

    for step in range(1, max_steps + 1):
        active = [t for t in turtles if t.active]
        if not active:
            break
        for t in active:
            old_x, old_y = t.x_m, t.y_m
            move = choose_move(t, env, rng, bcfg, scenario)
            t.x_m, t.y_m = move.x_m, move.y_m
            t.time_s += env.dt_s
            t.path_length_m += move.distance_m
            t.energy -= energy_cost(t, move.distance_m, env, pcfg)

            if move.distance_m > 0:
                t.moving_steps += 1
                if move.vector[0] < 0:
                    t.landward_steps += 1
                t.heading = move.vector
            t.max_landward_displacement_m = max(t.max_landward_displacement_m, t.start_x_m - t.x_m)
            initial_window = float(cfg["metrics"].get("initial_window_m", 5.0))
            if t.first_window_heading_deg is None:
                disp = np.array([t.x_m - t.start_x_m, t.y_m - t.start_y_m])
                if np.linalg.norm(disp) >= initial_window:
                    t.first_window_heading_deg = float(np.degrees(np.arctan2(disp[1], disp[0])))
            if record_tracks:
                t.history.append((t.time_s, t.x_m, t.y_m))

            if t.x_m < 0:
                t.outcome = "landward_exit"
            elif t.y_m < 0 or t.y_m > env.length_m:
                t.outcome = "lateral_exit"
            elif env.is_water(t.x_m, t.y_m):
                t.outcome = "sea"
            elif t.energy <= 0:
                t.outcome = "exhausted"
            else:
                p_pred = predation_probability(t, env, pcfg, scenario, move.artificial_strength)
                if rng.random() < p_pred:
                    t.outcome = "predated"

            if record_tracks and (step % track_stride == 0 or not t.active):
                track_rows.append({"replicate": replicate, "turtle_id": t.turtle_id, "step": step, "time_s": t.time_s, "x_m": t.x_m, "y_m": t.y_m, "outcome": t.outcome})

    for t in turtles:
        if t.active:
            t.outcome = "censored"
            if record_tracks:
                track_rows.append({"replicate": replicate, "turtle_id": t.turtle_id, "step": max_steps, "time_s": t.time_s, "x_m": t.x_m, "y_m": t.y_m, "outcome": t.outcome})

    summary = pd.DataFrame([_summarize_turtle(t, env, cfg) for t in turtles])
    summary.insert(0, "replicate", replicate)
    tracks = pd.DataFrame(track_rows)
    return summary, tracks
