"""Core data containers used by process, TEA, LCA, and decision modules."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from math import isfinite

from .constants import KG_PER_TONNE


@dataclass(slots=True)
class PathwayInventory:
    pathway: str
    category: str
    technology_family: str = "unspecified"
    co2_feed_kg: float = KG_PER_TONNE
    product_name: str = "none"
    product_kg: float = 0.0
    co2_utilized_kg: float = 0.0
    co2_stored_kg: float = 0.0
    co2_released_end_of_life_kg: float = 0.0
    direct_co2_emissions_kg: float = 0.0
    h2_kg: float = 0.0
    electricity_kwh: float = 0.0
    heat_gj: float = 0.0
    cooling_gj: float = 0.0
    water_kg: float = 0.0
    solar_input_kwh: float = 0.0
    land_m2: float = 0.0
    transport_tkm: float = 0.0
    capex_usd_per_tpa_co2: float = 0.0
    fixed_opex_usd_per_tco2: float = 0.0
    variable_opex_usd_per_tco2: float = 0.0
    product_price_usd_per_kg: float = 0.0
    displaced_emissions_kgco2e_per_kg_product: float = 0.0
    market_capacity_mtco2_per_year: float = 0.0
    carbon_residence_years: float = 0.0
    notes: str = ""

    @property
    def co2_feed_tonnes(self) -> float:
        return self.co2_feed_kg / KG_PER_TONNE

    @property
    def product_revenue_usd(self) -> float:
        return self.product_kg * self.product_price_usd_per_kg

    @property
    def displaced_emissions_kgco2e(self) -> float:
        return self.product_kg * self.displaced_emissions_kgco2e_per_kg_product

    def validate(self) -> None:
        if self.co2_feed_kg <= 0:
            raise ValueError(f"{self.pathway}: co2_feed_kg must be positive")
        for key, value in asdict(self).items():
            if isinstance(value, float) and not isfinite(value):
                raise ValueError(f"{self.pathway}: {key} is not finite")
            if isinstance(value, (float, int)) and key not in {"notes"} and value < 0:
                raise ValueError(f"{self.pathway}: {key} is negative")
        carbon_out = (
            self.co2_stored_kg
            + self.co2_released_end_of_life_kg
            + self.direct_co2_emissions_kg
        )
        if carbon_out > self.co2_feed_kg * 1.15:
            raise ValueError(
                f"{self.pathway}: CO2 out exceeds feed by more than tolerance"
            )


@dataclass(slots=True)
class LcaSummary:
    pathway: str
    induced_emissions_kgco2e: float
    displaced_emissions_kgco2e: float
    net_lifecycle_emissions_kgco2e: float
    net_avoided_kgco2e: float
    durable_retained_kgco2: float
    removal_credit_kgco2: float


@dataclass(slots=True)
class EconomicSummary:
    pathway: str
    gross_cost_usd_per_tco2: float
    product_revenue_usd_per_tco2: float
    carbon_credit_usd_per_tco2: float
    durable_removal_credit_usd_per_tco2: float
    carbon_tax_usd_per_tco2: float
    net_cost_usd_per_tco2: float
    abatement_cost_usd_per_tco2_avoided: float
    removal_cost_usd_per_tco2_retained: float


@dataclass(slots=True)
class Evaluation:
    inventory: PathwayInventory
    lca: LcaSummary
    economics: EconomicSummary

    def flat_record(self) -> dict[str, float | str]:
        record: dict[str, float | str] = {
            "pathway": self.inventory.pathway,
            "category": self.inventory.category,
            "technology_family": self.inventory.technology_family,
            "product": self.inventory.product_name,
            "product_kg_per_tco2": self.inventory.product_kg,
            "h2_kg_per_tco2": self.inventory.h2_kg,
            "electricity_kwh_per_tco2": self.inventory.electricity_kwh,
            "heat_gj_per_tco2": self.inventory.heat_gj,
            "solar_input_kwh_per_tco2": self.inventory.solar_input_kwh,
            "land_m2_per_tpa_co2": self.inventory.land_m2,
            "co2_utilized_kg_per_tco2": self.inventory.co2_utilized_kg,
            "co2_stored_kg_per_tco2": self.inventory.co2_stored_kg,
            "co2_eol_kg_per_tco2": self.inventory.co2_released_end_of_life_kg,
            "direct_co2_kg_per_tco2": self.inventory.direct_co2_emissions_kg,
            "market_capacity_mtco2_per_year": self.inventory.market_capacity_mtco2_per_year,
            "carbon_residence_years": self.inventory.carbon_residence_years,
            "induced_emissions_kgco2e_per_tco2": self.lca.induced_emissions_kgco2e,
            "displaced_emissions_kgco2e_per_tco2": self.lca.displaced_emissions_kgco2e,
            "net_avoided_kgco2e_per_tco2": self.lca.net_avoided_kgco2e,
            "durable_retained_kgco2_per_tco2": self.lca.durable_retained_kgco2,
            "gross_cost_usd_per_tco2": self.economics.gross_cost_usd_per_tco2,
            "product_revenue_usd_per_tco2": self.economics.product_revenue_usd_per_tco2,
            "carbon_credit_usd_per_tco2": self.economics.carbon_credit_usd_per_tco2,
            "durable_removal_credit_usd_per_tco2": self.economics.durable_removal_credit_usd_per_tco2,
            "carbon_tax_usd_per_tco2": self.economics.carbon_tax_usd_per_tco2,
            "net_cost_usd_per_tco2": self.economics.net_cost_usd_per_tco2,
            "abatement_cost_usd_per_tco2_avoided": self.economics.abatement_cost_usd_per_tco2_avoided,
            "removal_cost_usd_per_tco2_retained": self.economics.removal_cost_usd_per_tco2_retained,
            "notes": self.inventory.notes,
        }
        return record
