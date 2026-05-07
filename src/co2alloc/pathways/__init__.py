"""Pathway model registry."""

from .electrolysis import (
    electrolysis_co_inventory,
    electrolysis_ethylene_inventory,
    electrolysis_formate_inventory,
)
from .methane import methane_inventory
from .methanol import methanol_inventory
from .mineralization import mineralization_inventory
from .photochemical import (
    photocatalytic_co_inventory,
    photoelectrochemical_formate_inventory,
)
from .rwgs import rwgs_inventory
from .saf import ft_saf_inventory, methanol_to_jet_saf_inventory
from .storage import storage_inventory

PATHWAY_BUILDERS = [
    storage_inventory,
    mineralization_inventory,
    methanol_inventory,
    rwgs_inventory,
    electrolysis_co_inventory,
    electrolysis_formate_inventory,
    electrolysis_ethylene_inventory,
    photocatalytic_co_inventory,
    photoelectrochemical_formate_inventory,
    methane_inventory,
    ft_saf_inventory,
    methanol_to_jet_saf_inventory,
]

__all__ = [
    "PATHWAY_BUILDERS",
    "electrolysis_co_inventory",
    "electrolysis_ethylene_inventory",
    "electrolysis_formate_inventory",
    "methane_inventory",
    "methanol_inventory",
    "mineralization_inventory",
    "photocatalytic_co_inventory",
    "photoelectrochemical_formate_inventory",
    "rwgs_inventory",
    "ft_saf_inventory",
    "methanol_to_jet_saf_inventory",
    "storage_inventory",
]
