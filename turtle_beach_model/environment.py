from __future__ import annotations

from dataclasses import dataclass
from math import atan2, exp, hypot, sin, tanh
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .config import resolve_path


DIRECTION_VECTORS = {
    "dune": np.array([-1.0, 0.0]),
    "ocean": np.array([1.0, 0.0]),
    "north": np.array([0.0, 1.0]),
    "south": np.array([0.0, -1.0]),
}


def _local_y_from_latlon(df: pd.DataFrame) -> np.ndarray:
    """Projeta coordenadas em um eixo local aproximado ao longo da costa."""
    lat = np.deg2rad(df["latitude"].to_numpy(float))
    lon = np.deg2rad(df["longitude"].to_numpy(float))
    lat0 = float(np.mean(lat))
    r = 6_371_000.0
    east = r * (lon - lon.min()) * np.cos(lat0)
    north = r * (lat - lat.min())
    # Eixo principal por PCA, orientado do sul para o norte.
    pts = np.column_stack([east, north])
    pts -= pts.mean(axis=0)
    _, _, vh = np.linalg.svd(pts, full_matrices=False)
    axis = vh[0]
    proj = pts @ axis
    if np.corrcoef(proj, df["latitude"].to_numpy(float))[0, 1] < 0:
        proj = -proj
    return proj - proj.min()


def sqm_mag_to_relative_radiance(mag_arcsec2: np.ndarray, reference_mag: float) -> np.ndarray:
    """Converte magnitude/arcsec2 em radiancia relativa (escala sem unidade)."""
    return np.power(10.0, -0.4 * (np.asarray(mag_arcsec2, dtype=float) - reference_mag))


@dataclass(frozen=True)
class CueField:
    sea_x: float
    sea_y: float
    artificial_x: float
    artificial_y: float
    dune_x: float
    dune_y: float
    slope_x: float
    slope_y: float
    sea_strength: float
    artificial_strength: float
    dune_strength: float


class BeachEnvironment:
    """Ambiente fisicamente escalado com perfil de praia e campo luminoso direcional."""

    def __init__(self, cfg: dict[str, Any]):
        self.cfg = cfg
        self.cell_size_m = float(cfg["grid"]["cell_size_m"])
        self.dt_s = float(cfg["grid"]["dt_s"])
        self.eye_height_m = float(cfg["environment"].get("eye_height_m", 0.035))

        self.profile = self._load_profile()
        self.length_m = float(self.profile["y_m"].max())
        self.max_waterline_x_m = float(self.profile["waterline_x_m"].max())
        self.nx = int(np.ceil(self.max_waterline_x_m / self.cell_size_m)) + 2
        self.ny = int(np.ceil(self.length_m / self.cell_size_m)) + 1
        self._y_grid = np.arange(self.ny, dtype=float) * self.cell_size_m
        self._waterline_grid = np.interp(self._y_grid, self.profile["y_m"], self.profile["waterline_x_m"])
        self._dune_height_grid = np.interp(self._y_grid, self.profile["y_m"], self.profile["dune_height_m"])
        self._slope_grid = np.interp(self._y_grid, self.profile["y_m"], self.profile["slope_deg"])

        self.light_long = self._load_light_measurements()
        self.light_site = self._build_light_site_table(self.light_long)
        self._sea_grid = np.interp(self._y_grid, self.light_site["y_m"], self.light_site["sea_strength"])
        self._art_x_grid = np.interp(self._y_grid, self.light_site["y_m"], self.light_site["art_x"])
        self._art_y_grid = np.interp(self._y_grid, self.light_site["y_m"], self.light_site["art_y"])
        self.nests = self._load_nests()
        self.obstacles = self._load_obstacles()
        self._blocked_cells = self._build_blocked_cells()

    def _load_profile(self) -> pd.DataFrame:
        p = resolve_path(self.cfg, self.cfg["inputs"]["beach_profile_csv"])
        df = pd.read_csv(p)
        required = {"y_m", "waterline_x_m", "dune_height_m", "slope_deg"}
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f"Perfil de praia sem colunas: {sorted(missing)}")
        df = df.sort_values("y_m").drop_duplicates("y_m")
        if (df["waterline_x_m"] <= 0).any():
            raise ValueError("waterline_x_m deve ser positivo.")
        return df.reset_index(drop=True)

    def _load_light_measurements(self) -> pd.DataFrame:
        p = resolve_path(self.cfg, self.cfg["inputs"]["light_measurements_csv"])
        df = pd.read_csv(p)
        required = {"site_id", "direction", "mag_arcsec2"}
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f"Medicoes luminosas sem colunas: {sorted(missing)}")
        df["direction"] = df["direction"].str.lower().str.strip()
        invalid = set(df["direction"]) - set(DIRECTION_VECTORS) - {"zenith"}
        if invalid:
            raise ValueError(f"Direcoes luminosas invalidas: {sorted(invalid)}")
        if "y_m" not in df.columns or df["y_m"].isna().all():
            if not {"latitude", "longitude"}.issubset(df.columns):
                raise ValueError("Forneca y_m ou latitude/longitude nas medicoes de luz.")
            sites = df[["site_id", "latitude", "longitude"]].drop_duplicates("site_id").copy()
            sites["y_m"] = _local_y_from_latlon(sites)
            df = df.drop(columns=["y_m"], errors="ignore").merge(sites[["site_id", "y_m"]], on="site_id")
        return df.sort_values(["y_m", "direction"]).reset_index(drop=True)

    def _build_light_site_table(self, long_df: pd.DataFrame) -> pd.DataFrame:
        pivot = long_df.pivot_table(index=["site_id", "y_m"], columns="direction", values="mag_arcsec2", aggfunc="mean").reset_index()
        for name in ["dune", "ocean", "north", "south"]:
            if name not in pivot:
                raise ValueError(f"Falta a direcao {name!r} no levantamento luminoso.")

        ref_mag = float(self.cfg["environment"].get("sqm_reference_mag", 20.0))
        for name in ["dune", "ocean", "north", "south", "zenith"]:
            if name in pivot:
                pivot[f"rad_{name}"] = sqm_mag_to_relative_radiance(pivot[name].to_numpy(), ref_mag)

        # O horizonte oceanico e usado como referencia natural local. O excesso nas
        # demais direcoes compoe o vetor artificial. Isso e uma decomposicao operacional,
        # nao uma separacao espectral perfeita entre luz natural e artificial.
        ocean = pivot["rad_ocean"].to_numpy(float)
        baseline = np.maximum(ocean, np.finfo(float).eps)
        dune_excess = np.maximum(pivot["rad_dune"].to_numpy(float) - baseline, 0.0)
        north_excess = np.maximum(pivot["rad_north"].to_numpy(float) - baseline, 0.0)
        south_excess = np.maximum(pivot["rad_south"].to_numpy(float) - baseline, 0.0)

        natural_norm = float(np.median(ocean))
        pivot["sea_strength"] = ocean / natural_norm
        pivot["art_x"] = -dune_excess / natural_norm
        pivot["art_y"] = (north_excess - south_excess) / natural_norm
        pivot["art_strength"] = np.hypot(pivot["art_x"], pivot["art_y"])
        return pivot.sort_values("y_m").reset_index(drop=True)

    def _load_nests(self) -> pd.DataFrame:
        p = resolve_path(self.cfg, self.cfg["inputs"]["nests_csv"])
        df = pd.read_csv(p)
        required = {"nest_id", "x_m", "y_m"}
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f"Arquivo de ninhos sem colunas: {sorted(missing)}")
        if "weight" not in df:
            df["weight"] = 1.0
        df["weight"] = df["weight"].astype(float)
        if (df["weight"] < 0).any() or df["weight"].sum() <= 0:
            raise ValueError("Pesos dos ninhos devem ser nao negativos e somar valor positivo.")
        return df.reset_index(drop=True)

    def _load_obstacles(self) -> pd.DataFrame:
        value = self.cfg["inputs"].get("obstacles_csv")
        if not value:
            return pd.DataFrame(columns=["x_m", "y_m", "radius_m"])
        p = resolve_path(self.cfg, value)
        if not p.exists():
            return pd.DataFrame(columns=["x_m", "y_m", "radius_m"])
        df = pd.read_csv(p)
        if df.empty:
            return pd.DataFrame(columns=["x_m", "y_m", "radius_m"])
        required = {"x_m", "y_m", "radius_m"}
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f"Obstaculos sem colunas: {sorted(missing)}")
        return df

    def _y_index(self, y_m: float) -> int:
        idx = int(round(float(y_m) / self.cell_size_m))
        if idx < 0:
            return 0
        if idx >= self.ny:
            return self.ny - 1
        return idx

    def interp_profile(self, y_m: float, column: str) -> float:
        idx = self._y_index(y_m)
        if column == "waterline_x_m":
            return float(self._waterline_grid[idx])
        if column == "dune_height_m":
            return float(self._dune_height_grid[idx])
        if column == "slope_deg":
            return float(self._slope_grid[idx])
        y = float(np.clip(y_m, 0.0, self.length_m))
        return float(np.interp(y, self.profile["y_m"], self.profile[column]))

    def waterline_x(self, y_m: float) -> float:
        return float(self._waterline_grid[self._y_index(y_m)])

    def dune_height(self, y_m: float) -> float:
        return float(self._dune_height_grid[self._y_index(y_m)])

    def slope_deg(self, y_m: float) -> float:
        return float(self._slope_grid[self._y_index(y_m)])

    def is_water(self, x_m: float, y_m: float) -> bool:
        if not (0.0 <= y_m <= self.length_m):
            return False
        return x_m >= self.waterline_x(y_m)

    def _build_blocked_cells(self) -> set[tuple[int, int]]:
        blocked: set[tuple[int, int]] = set()
        if self.obstacles.empty:
            return blocked
        for row in self.obstacles.itertuples(index=False):
            cx = int(round(float(row.x_m) / self.cell_size_m))
            cy = int(round(float(row.y_m) / self.cell_size_m))
            rr = int(np.ceil(float(row.radius_m) / self.cell_size_m))
            for ix in range(cx - rr, cx + rr + 1):
                for iy in range(cy - rr, cy + rr + 1):
                    if ((ix - cx) * self.cell_size_m) ** 2 + ((iy - cy) * self.cell_size_m) ** 2 <= float(row.radius_m) ** 2:
                        blocked.add((ix, iy))
        return blocked

    def is_obstacle(self, x_m: float, y_m: float) -> bool:
        ix = int(round(float(x_m) / self.cell_size_m))
        iy = int(round(float(y_m) / self.cell_size_m))
        return (ix, iy) in self._blocked_cells

    def _interp_light(self, y_m: float, column: str) -> float:
        idx = self._y_index(y_m)
        if column == "sea_strength":
            return float(self._sea_grid[idx])
        if column == "art_x":
            return float(self._art_x_grid[idx])
        if column == "art_y":
            return float(self._art_y_grid[idx])
        y = float(np.clip(y_m, 0.0, self.length_m))
        return float(np.interp(y, self.light_site["y_m"], self.light_site[column]))

    def cues_at(self, x_m: float, y_m: float, scenario: dict[str, float] | None = None) -> CueField:
        scenario = scenario or {}
        sea_scale = float(scenario.get("sea_scale", 1.0))
        artificial_scale = float(scenario.get("artificial_scale", 1.0))
        spectral_weight = float(scenario.get("spectral_weight", 1.0))
        shielding = float(scenario.get("shielding", 0.0))
        dune_extra_height = float(scenario.get("dune_extra_height_m", 0.0))

        idx = self._y_index(y_m)
        sea_strength = float(self._sea_grid[idx]) * sea_scale

        art_x = float(self._art_x_grid[idx])
        art_y = float(self._art_y_grid[idx])
        decay_m = float(self.cfg["environment"].get("artificial_cross_shore_decay_m", 120.0))
        attenuation = exp(-max(x_m, 0.0) / max(decay_m, 1e-6))

        # Aproximacao de oclusao pela duna: quanto maior o angulo aparente da duna,
        # menor a visibilidade de fontes terrestres baixas.
        dune_h = float(self._dune_height_grid[idx]) + dune_extra_height
        apparent_angle = atan2(max(dune_h - self.eye_height_m, 0.0), max(x_m, 0.25))
        occlusion_strength = float(self.cfg["environment"].get("dune_occlusion_strength", 1.4))
        natural_occlusion = exp(-occlusion_strength * apparent_angle)
        visibility = attenuation * natural_occlusion * max(0.0, 1.0 - shielding)

        artificial_x = art_x * artificial_scale * spectral_weight * visibility
        artificial_y = art_y * artificial_scale * spectral_weight * visibility
        artificial_strength = hypot(artificial_x, artificial_y)

        dune_strength = tanh(apparent_angle * 2.0)
        slope_strength = sin(np.deg2rad(float(self._slope_grid[idx])))

        return CueField(
            sea_x=sea_strength, sea_y=0.0,
            artificial_x=artificial_x, artificial_y=artificial_y,
            dune_x=dune_strength, dune_y=0.0,
            slope_x=slope_strength, slope_y=0.0,
            sea_strength=sea_strength,
            artificial_strength=artificial_strength,
            dune_strength=dune_strength,
        )

    def sample_nest(self, rng: np.random.Generator) -> tuple[str, float, float]:
        probs = self.nests["weight"].to_numpy(float)
        probs = probs / probs.sum()
        idx = int(rng.choice(len(self.nests), p=probs))
        row = self.nests.iloc[idx]
        jitter = float(self.cfg["simulation"].get("nest_jitter_m", 0.25))
        x = float(row["x_m"] + rng.normal(0.0, jitter))
        y = float(row["y_m"] + rng.normal(0.0, jitter))
        x = round(max(x, 0.05) / self.cell_size_m) * self.cell_size_m
        y = round(float(np.clip(y, 0.0, self.length_m)) / self.cell_size_m) * self.cell_size_m
        return str(row["nest_id"]), x, y

    def diagnostics(self) -> dict[str, float | int]:
        return {
            "length_m": self.length_m,
            "max_waterline_x_m": self.max_waterline_x_m,
            "grid_nx": self.nx,
            "grid_ny": self.ny,
            "n_light_sites": int(self.light_site.shape[0]),
            "n_nests": int(self.nests.shape[0]),
            "artificial_strength_min": float(self.light_site["art_strength"].min()),
            "artificial_strength_max": float(self.light_site["art_strength"].max()),
        }
