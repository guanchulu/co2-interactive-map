"""Shared constants for stoichiometry and unit conversion."""

FARADAY_C_PER_MOL = 96485.33212
J_PER_KWH = 3.6e6
KG_PER_TONNE = 1000.0

MW_KG_PER_KMOL = {
    "CO2": 44.0095,
    "H2": 2.01588,
    "H2O": 18.01528,
    "CO": 28.0101,
    "METHANOL": 32.04186,
    "CH4": 16.04246,
    "FORMIC_ACID": 46.02538,
    "ETHYLENE": 28.05316,
    "CACO3": 100.0869,
}


def kg_to_kmol(kg: float, species: str) -> float:
    return kg / MW_KG_PER_KMOL[species]


def kmol_to_kg(kmol: float, species: str) -> float:
    return kmol * MW_KG_PER_KMOL[species]


def capital_recovery_factor(discount_rate: float, lifetime_years: int) -> float:
    if lifetime_years <= 0:
        raise ValueError("lifetime_years must be positive")
    if discount_rate == 0:
        return 1.0 / lifetime_years
    r = discount_rate
    n = lifetime_years
    return r * (1 + r) ** n / ((1 + r) ** n - 1)
