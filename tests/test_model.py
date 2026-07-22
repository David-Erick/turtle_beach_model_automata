from __future__ import annotations

import unittest
from copy import deepcopy
from pathlib import Path

import pandas as pd

from turtle_beach_model.config import load_config
from turtle_beach_model.environment import BeachEnvironment
from turtle_beach_model.simulation import run_simulation


ROOT = Path(__file__).resolve().parents[1]


class TurtleBeachModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.cfg = load_config(ROOT / "configs" / "delray_demo.yaml")

    def test_directional_light_field(self) -> None:
        env = BeachEnvironment(self.cfg)
        cue = env.cues_at(8.0, 400.0, {"artificial_scale": 1.0})
        self.assertGreater(cue.sea_x, 0.0)
        self.assertLess(cue.artificial_x, 0.0)
        off = env.cues_at(8.0, 400.0, {"artificial_scale": 0.0})
        self.assertAlmostEqual(off.artificial_strength, 0.0, places=12)

    def test_conservation_of_individuals(self) -> None:
        cfg = deepcopy(self.cfg)
        cfg["simulation"]["max_time_s"] = 300
        summary, _ = run_simulation(cfg, seed=101, n_turtles=8, scenario={"artificial_scale": 1.0}, record_tracks=False)
        self.assertEqual(len(summary), 8)
        self.assertTrue(summary["outcome"].isin({"sea", "predated", "exhausted", "censored", "landward_exit", "lateral_exit"}).all())

    def test_reproducibility(self) -> None:
        cfg = deepcopy(self.cfg)
        cfg["simulation"]["max_time_s"] = 300
        a, _ = run_simulation(cfg, seed=2026, n_turtles=6, scenario={"artificial_scale": 0.5}, record_tracks=False)
        b, _ = run_simulation(cfg, seed=2026, n_turtles=6, scenario={"artificial_scale": 0.5}, record_tracks=False)
        pd.testing.assert_frame_equal(a, b)

    def test_real_measurement_count(self) -> None:
        env = BeachEnvironment(self.cfg)
        self.assertEqual(len(env.light_site), 9)
        self.assertEqual(len(env.light_long), 45)


if __name__ == "__main__":
    unittest.main()
