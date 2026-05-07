"""Reduced-order CO2 pipeline transport cost model.

The implementation follows the public McCoy/Rubin pipeline-capital regression
used by NETL CO2_T_COM as a transparent runtime alternative to the macro-enabled
Excel workbook. It keeps all monetary outputs on a per-tonne-CO2 basis for the
spatial allocator.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .constants import capital_recovery_factor


STANDARD_NPS_IN = (4, 6, 8, 10, 12, 16, 20, 24, 30, 36, 42, 48)
SECONDS_PER_YEAR = 365.0 * 24.0 * 3600.0


@dataclass(frozen=True, slots=True)
class PipelineCostResult:
    distance_km: float
    flow_mtpa: float
    nps_in: int
    capital_cost_usd: float
    annualized_capex_usd_per_tco2: float
    fixed_om_usd_per_tco2: float
    booster_energy_kwh_per_tco2: float
    booster_energy_cost_usd_per_tco2: float
    levelized_cost_usd_per_tco2: float


MCCOY_RUBIN_COEFFICIENTS = {
    # log10(C_2004_usd) = a0 + a6 log10(length_km) + a7 log10(NPS_in).
    # Region dummy variables are kept out of the default China screening case;
    # use region_capex_multiplier for terrain/ROW or local cost adjustments.
    "materials": (3.112, 0.901, 1.590),
    "labor": (4.487, 0.820, 0.940),
    "row": (3.950, 1.049, 0.403),
    "misc": (4.390, 0.783, 0.791),
}


def nominal_pipe_size_in(
    flow_mtpa: float,
    capacity_factor: float = 0.85,
    density_kg_per_m3: float = 900.0,
    design_velocity_m_per_s: float = 1.5,
) -> int:
    if flow_mtpa <= 0:
        raise ValueError("flow_mtpa must be positive")
    mass_flow_kg_s = flow_mtpa * 1e9 / SECONDS_PER_YEAR / max(capacity_factor, 1e-9)
    volumetric_flow_m3_s = mass_flow_kg_s / density_kg_per_m3
    diameter_m = math.sqrt(4.0 * volumetric_flow_m3_s / (math.pi * design_velocity_m_per_s))
    required_in = diameter_m / 0.0254
    for nps in STANDARD_NPS_IN:
        if nps >= required_in:
            return nps
    return STANDARD_NPS_IN[-1]


def mccoy_rubin_capex_usd(
    distance_km: float,
    nps_in: int,
    escalation_2004_to_target: float = 1.80,
    region_capex_multiplier: float = 1.0,
) -> float:
    if distance_km <= 0:
        return 0.0
    if nps_in <= 0:
        raise ValueError("nps_in must be positive")
    length = max(distance_km, 1e-9)
    diameter = max(float(nps_in), 1e-9)
    capex_2004 = 0.0
    for a0, a6, a7 in MCCOY_RUBIN_COEFFICIENTS.values():
        capex_2004 += 10.0 ** (a0 + a6 * math.log10(length) + a7 * math.log10(diameter))
    return capex_2004 * escalation_2004_to_target * region_capex_multiplier


def booster_energy_kwh_per_tco2(
    distance_km: float,
    kwh_per_tco2_per_100km: float = 2.5,
) -> float:
    return max(distance_km, 0.0) / 100.0 * kwh_per_tco2_per_100km


def pipeline_transport_cost(
    distance_km: float,
    flow_mtpa: float,
    electricity_price_usd_per_mwh: float,
    discount_rate: float,
    lifetime_years: int,
    capacity_factor: float = 0.85,
    fixed_om_fraction_of_capex_per_year: float = 0.035,
    escalation_2004_to_target: float = 1.80,
    region_capex_multiplier: float = 1.0,
) -> PipelineCostResult:
    if flow_mtpa <= 0:
        raise ValueError("flow_mtpa must be positive")
    annual_tonnes = flow_mtpa * 1e6
    nps = nominal_pipe_size_in(flow_mtpa, capacity_factor=capacity_factor)
    capex = mccoy_rubin_capex_usd(
        distance_km,
        nps,
        escalation_2004_to_target=escalation_2004_to_target,
        region_capex_multiplier=region_capex_multiplier,
    )
    crf = capital_recovery_factor(discount_rate, lifetime_years)
    annualized_capex = capex * crf / annual_tonnes
    fixed_om = capex * fixed_om_fraction_of_capex_per_year / annual_tonnes
    booster_kwh = booster_energy_kwh_per_tco2(distance_km)
    booster_cost = booster_kwh / 1000.0 * electricity_price_usd_per_mwh
    levelized = annualized_capex + fixed_om + booster_cost
    return PipelineCostResult(
        distance_km=distance_km,
        flow_mtpa=flow_mtpa,
        nps_in=nps,
        capital_cost_usd=capex,
        annualized_capex_usd_per_tco2=annualized_capex,
        fixed_om_usd_per_tco2=fixed_om,
        booster_energy_kwh_per_tco2=booster_kwh,
        booster_energy_cost_usd_per_tco2=booster_cost,
        levelized_cost_usd_per_tco2=levelized,
    )


def pipeline_transport_emissions_kgco2e_per_tco2(
    distance_km: float,
    electricity_emissions_kgco2e_per_mwh: float,
) -> float:
    return booster_energy_kwh_per_tco2(distance_km) / 1000.0 * electricity_emissions_kgco2e_per_mwh
