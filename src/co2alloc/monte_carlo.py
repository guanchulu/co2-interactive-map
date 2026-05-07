"""Monte Carlo utilities for the spatial allocation model."""

from __future__ import annotations

import csv
import random
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class UncertaintyParameter:
    parameter: str
    distribution: str
    low: float
    mode: float
    high: float


def load_uncertainty_parameters(path: str | Path) -> list[UncertaintyParameter]:
    rows: list[UncertaintyParameter] = []
    with Path(path).open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            rows.append(
                UncertaintyParameter(
                    parameter=row["parameter"],
                    distribution=row["distribution"],
                    low=float(row["low"]),
                    mode=float(row["mode"]),
                    high=float(row["high"]),
                )
            )
    return rows


def sample_parameters(
    params: list[UncertaintyParameter],
    rng: random.Random,
) -> dict[str, float]:
    values: dict[str, float] = {}
    for param in params:
        if param.distribution == "triangular":
            value = rng.triangular(param.low, param.high, param.mode)
        elif param.distribution == "uniform":
            value = rng.uniform(param.low, param.high)
        elif param.distribution == "fixed":
            value = param.mode
        else:
            raise ValueError(f"Unknown distribution: {param.distribution}")
        values[param.parameter] = value
    return values

