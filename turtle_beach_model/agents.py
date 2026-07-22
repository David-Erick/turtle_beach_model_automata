from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class Turtle:
    turtle_id: int
    nest_id: str
    x_m: float
    y_m: float
    start_x_m: float
    start_y_m: float
    energy: float
    kappa_sea: float
    kappa_artificial: float
    kappa_dune: float
    kappa_slope: float
    persistence: float
    temperature: float
    heading: np.ndarray = field(default_factory=lambda: np.array([1.0, 0.0]))
    time_s: float = 0.0
    path_length_m: float = 0.0
    landward_steps: int = 0
    moving_steps: int = 0
    max_landward_displacement_m: float = 0.0
    outcome: str = "active"
    first_window_heading_deg: float | None = None
    first_window_recorded: bool = False
    history: list[tuple[float, float, float]] = field(default_factory=list)

    @property
    def active(self) -> bool:
        return self.outcome == "active"
