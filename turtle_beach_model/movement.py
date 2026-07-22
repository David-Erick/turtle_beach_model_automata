from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from typing import Any

import numpy as np

from .agents import Turtle
from .environment import BeachEnvironment, CueField


SQRT2_INV = 1.0 / sqrt(2.0)
MOVE_TEMPLATES = (
    (-1, -1, -SQRT2_INV, -SQRT2_INV, sqrt(2.0)),
    (-1, 0, -1.0, 0.0, 1.0),
    (-1, 1, -SQRT2_INV, SQRT2_INV, sqrt(2.0)),
    (0, -1, 0.0, -1.0, 1.0),
    (0, 0, 0.0, 0.0, 0.0),
    (0, 1, 0.0, 1.0, 1.0),
    (1, -1, SQRT2_INV, -SQRT2_INV, sqrt(2.0)),
    (1, 0, 1.0, 0.0, 1.0),
    (1, 1, SQRT2_INV, SQRT2_INV, sqrt(2.0)),
)


@dataclass(frozen=True)
class MoveChoice:
    x_m: float
    y_m: float
    vector: np.ndarray
    distance_m: float
    utility: float
    artificial_strength: float


def _stable_softmax(values: np.ndarray, temperature: float) -> np.ndarray:
    logits = np.asarray(values, dtype=float) / max(float(temperature), 1e-9)
    logits -= float(logits.max())
    expv = np.exp(np.clip(logits, -700, 700))
    total = float(expv.sum())
    if not np.isfinite(total) or total <= 0:
        return np.ones_like(expv) / len(expv)
    return expv / total


def choose_move(
    turtle: Turtle,
    env: BeachEnvironment,
    rng: np.random.Generator,
    behavior_cfg: dict[str, Any],
    scenario: dict[str, float] | None = None,
) -> MoveChoice:
    cell = env.cell_size_m
    cues: CueField = env.cues_at(turtle.x_m, turtle.y_m, scenario)
    choices: list[MoveChoice] = []
    utilities: list[float] = []
    boundary = str(env.cfg.get("environment", {}).get("lateral_boundary", "reflecting")).lower()
    hx, hy = float(turtle.heading[0]), float(turtle.heading[1])

    for dx, dy, ux, uy, distance_factor in MOVE_TEMPLATES:
        tx = turtle.x_m + dx * cell
        ty = turtle.y_m + dy * cell
        if boundary == "reflecting":
            if ty < 0:
                ty = -ty
            elif ty > env.length_m:
                ty = 2.0 * env.length_m - ty
        if env.is_obstacle(tx, ty):
            continue

        utility = 0.0
        utility += turtle.kappa_sea * (ux * cues.sea_x + uy * cues.sea_y)
        utility += turtle.kappa_artificial * (ux * cues.artificial_x + uy * cues.artificial_y)
        utility += turtle.kappa_dune * (ux * cues.dune_x + uy * cues.dune_y)
        utility += turtle.kappa_slope * (ux * cues.slope_x + uy * cues.slope_y)
        utility += turtle.persistence * (ux * hx + uy * hy)
        if distance_factor == 0.0:
            utility -= float(behavior_cfg.get("stay_penalty", 0.25))
        if dx < 0:
            utility -= float(behavior_cfg.get("landward_cost", 0.0))

        move = MoveChoice(
            tx,
            ty,
            np.array([ux, uy], dtype=float),
            distance_factor * cell,
            utility,
            cues.artificial_strength,
        )
        choices.append(move)
        utilities.append(utility)

    if not choices:
        return MoveChoice(turtle.x_m, turtle.y_m, np.zeros(2), 0.0, 0.0, cues.artificial_strength)

    probs = _stable_softmax(np.asarray(utilities, dtype=float), turtle.temperature)
    idx = int(rng.choice(len(choices), p=probs))
    return choices[idx]
