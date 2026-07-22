from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml


class ConfigError(ValueError):
    """Erro de configuracao do modelo."""


def load_config(path: str | Path) -> dict[str, Any]:
    path = Path(path).resolve()
    with path.open("r", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    if not isinstance(cfg, dict):
        raise ConfigError("O arquivo YAML deve conter um objeto na raiz.")
    cfg["_config_path"] = str(path)
    cfg["_base_dir"] = str(path.parent)
    validate_config(cfg)
    return cfg


def resolve_path(cfg: dict[str, Any], value: str | Path) -> Path:
    p = Path(value)
    if p.is_absolute():
        return p
    return (Path(cfg["_base_dir"]) / p).resolve()


def validate_config(cfg: dict[str, Any]) -> None:
    required = ["site", "grid", "inputs", "behavior", "processes", "simulation"]
    missing = [k for k in required if k not in cfg]
    if missing:
        raise ConfigError(f"Secoes ausentes no YAML: {missing}")

    cell = float(cfg["grid"].get("cell_size_m", 0))
    dt = float(cfg["grid"].get("dt_s", 0))
    if cell <= 0 or dt <= 0:
        raise ConfigError("grid.cell_size_m e grid.dt_s devem ser positivos.")

    max_time = float(cfg["simulation"].get("max_time_s", 0))
    if max_time <= 0:
        raise ConfigError("simulation.max_time_s deve ser positivo.")

    tau = float(cfg["behavior"].get("temperature", 0))
    if tau <= 0:
        raise ConfigError("behavior.temperature deve ser positivo.")


def clone_with_updates(cfg: dict[str, Any], updates: dict[str, float]) -> dict[str, Any]:
    """Copia a configuracao e aplica parametros comportamentais escalares."""
    out = deepcopy(cfg)
    for key, value in updates.items():
        if key in out.get("behavior", {}):
            out["behavior"][key] = float(value)
        elif key in out.get("processes", {}):
            out["processes"][key] = float(value)
        else:
            raise ConfigError(f"Parametro desconhecido para atualizacao: {key}")
    return out
