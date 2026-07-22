from __future__ import annotations

from typing import Any

import numpy as np

from .agents import Turtle
from .environment import BeachEnvironment


def energy_cost(turtle: Turtle, move_distance_m: float, env: BeachEnvironment, processes_cfg: dict[str, Any]) -> float:
    basal = float(processes_cfg.get("basal_energy_per_s", 0.0004)) * env.dt_s
    movement = float(processes_cfg.get("movement_energy_per_m", 0.006)) * move_distance_m
    slope_factor = 1.0 + float(processes_cfg.get("slope_energy_multiplier", 0.5)) * abs(np.sin(np.deg2rad(env.slope_deg(turtle.y_m))))
    return basal + movement * slope_factor


def predation_probability(
    turtle: Turtle,
    env: BeachEnvironment,
    processes_cfg: dict[str, Any],
    scenario: dict[str, float] | None = None,
    artificial_strength: float | None = None,
) -> float:
    scenario = scenario or {}
    base_hazard = float(processes_cfg.get("predation_hazard_per_s", 0.0))
    base_hazard *= float(scenario.get("predation_scale", 1.0))
    if base_hazard <= 0:
        return 0.0

    if artificial_strength is None:
        artificial_strength = env.cues_at(turtle.x_m, turtle.y_m, scenario).artificial_strength
    time_ref = max(float(processes_cfg.get("predation_time_reference_s", 300.0)), 1e-9)
    time_multiplier = 1.0 + float(processes_cfg.get("predation_time_effect", 0.35)) * turtle.time_s / time_ref
    light_multiplier = 1.0 + float(processes_cfg.get("predation_light_effect", 0.10)) * float(artificial_strength)
    land_multiplier = 1.0 + float(processes_cfg.get("predation_landward_effect", 0.25)) * max(
        0.0, 1.0 - turtle.x_m / max(env.waterline_x(turtle.y_m), 1e-9)
    )
    hazard = base_hazard * time_multiplier * light_multiplier * land_multiplier
    return float(1.0 - np.exp(-hazard * env.dt_s))
