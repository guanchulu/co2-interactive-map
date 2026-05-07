"""Technology learning multipliers for future scenarios."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class LearningRow:
    year: int
    selector_type: str
    selector: str
    capex_multiplier: float
    fixed_opex_multiplier: float
    variable_opex_multiplier: float


def load_learning_rows(path: str | Path) -> list[LearningRow]:
    rows: list[LearningRow] = []
    with Path(path).open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            rows.append(
                LearningRow(
                    year=int(row["year"]),
                    selector_type=row["selector_type"],
                    selector=row["selector"],
                    capex_multiplier=float(row["capex_multiplier"]),
                    fixed_opex_multiplier=float(row.get("fixed_opex_multiplier") or 1.0),
                    variable_opex_multiplier=float(row.get("variable_opex_multiplier") or 1.0),
                )
            )
    return rows


def learning_multipliers(
    rows: list[LearningRow],
    year: int,
    pathway: str,
    technology_family: str,
) -> tuple[float, float, float]:
    capex = 1.0
    fixed = 1.0
    variable = 1.0
    candidates = [
        row
        for row in rows
        if row.year == year
        and (
            (row.selector_type == "pathway" and row.selector == pathway)
            or (row.selector_type == "technology_family" and row.selector == technology_family)
            or (row.selector_type == "all" and row.selector == "all")
        )
    ]
    # Apply broad rows first and pathway-specific rows last.
    priority = {"all": 0, "technology_family": 1, "pathway": 2}
    for row in sorted(candidates, key=lambda item: priority.get(item.selector_type, 0)):
        capex *= row.capex_multiplier
        fixed *= row.fixed_opex_multiplier
        variable *= row.variable_opex_multiplier
    return capex, fixed, variable

