# CO2 Allocation Model

Reduced-order process, techno-economic, and life-cycle model for comparing
captured CO2 destinations:

- geological storage
- mineralization
- CO2 hydrogenation to methanol
- reverse water-gas shift to CO
- electrochemical CO2-to-CO
- electrochemical CO2-to-formate
- electrochemical CO2-to-ethylene
- photocatalytic CO2-to-CO
- photoelectrochemical CO2-to-formate
- CO2 methanation to e-methane

The model is intentionally Python-native and parameterized. It is designed for
scenario scans and decision maps rather than detailed plant design.

## Quick start

```powershell
cd H:\chatgpt\co2_allocation_model
$env:PYTHONPATH = "src"
H:\chatgpt\tools\Python31313\python.exe -m co2alloc.cli baseline --out output\baseline.csv
H:\chatgpt\tools\Python31313\python.exe -m co2alloc.cli grid --out output\decision_grid.csv --ascii-out output\decision_map.txt --svg-out output\decision_map.svg
H:\chatgpt\tools\Python31313\python.exe -m co2alloc.cli sensitivity --out output\sensitivity.csv
H:\chatgpt\tools\Python31313\python.exe -m co2alloc.cli family --out output\family_best.csv
H:\chatgpt\tools\Python31313\python.exe -m co2alloc.cli spatial-candidates --out output\spatial_candidates.csv
H:\chatgpt\tools\Python31313\python.exe -m co2alloc.cli spatial-allocate --optimizer lp --out output\spatial_allocations.csv --summary-out output\spatial_summary.csv
H:\chatgpt\tools\Python31313\python.exe -m co2alloc.cli monte-carlo --runs 100 --out output\monte_carlo_summary.csv
```

Python 3.13.13 is installed locally at `H:\chatgpt\tools\Python31313`.
It was installed without changing the system PATH.
SciPy is installed in the same local Python environment for linear-programming
spatial allocation.

## Real-data China baseline

The `data/processed` folder now includes downloaded public datasets for China
point sources, provincial storage potential, provincial power CO2 factors,
hourly provincial load, ports, carbon price snapshots, policy intensity, and
green-hydrogen assumptions. Convert them into model-ready spatial inputs with:

```powershell
cd H:\chatgpt\co2_allocation_model
$env:PYTHONPATH = "src"
H:\chatgpt\tools\Python31313\python.exe -m co2alloc.cli build-real-inputs --source-year 2024 --top-sources 120 --out-dir data\real_inputs --manifest-out data\real_inputs\manifest.csv --storage-horizon-years 20
H:\chatgpt\tools\Python31313\python.exe -m co2alloc.cli spatial-allocate --sources data\real_inputs\spatial_sources_real.csv --destinations data\real_inputs\spatial_destinations_real.csv --transport-modes data\transport_modes.csv --hubs data\real_inputs\hubs_real.csv --hourly-profiles data\real_inputs\hourly_energy_profiles_real.csv --learning data\technology_scenarios.csv --year 2030 --max-distance 2500 --optimizer lp --minimum-source-fraction 0 --target-total-mtco2 550 --policy-source destination --out output\real_allocations_2024_top120_target550_fixed.csv --summary-out output\real_summary_2024_top120_target550_fixed.csv
H:\chatgpt\tools\Python31313\python.exe scripts\analyze_real_run.py
```

The current real-data baseline uses the top 120 Climate TRACE China point
sources in 2024, assumes 90% capture, constrains annual storage by both
injection rate and 20-year storage potential, and initializes carbon prices
from the captured CEA/CCER snapshot. Main outputs:

- `data\real_inputs\spatial_sources_real.csv`
- `data\real_inputs\spatial_destinations_real.csv`
- `data\real_inputs\hourly_energy_profiles_real.csv`
- `output\real_summary_2024_top120.csv`
- `output\real_allocations_2024_top120.csv`
- `docs\figures_real\real_allocation_network.svg`

The LP is normally run with a fixed system target. Without
`--target-total-mtco2` or `--target-source-fraction`, a positive-cost
minimization allocates only the requested lower-bound source fraction.

## Expanded China scenarios

The expanded run uses the top 300 Climate TRACE China sources, 23 province-level
storage destinations built from the processed storage-potential table, four
regional product-market destinations, 271,560 hourly province-profile rows, hub
routing, policy overrides, and 2030/2040/2050 learning.

```powershell
cd H:\chatgpt\co2_allocation_model
$env:PYTHONPATH = "src"
H:\chatgpt\tools\Python31313\python.exe scripts\run_expanded_real_scenarios.py
H:\chatgpt\tools\Python31313\python.exe scripts\analyze_expanded_real_scenarios.py
```

Profitability scans add product prices, policy eligibility, product-quality
upgrading, MRV/certification, financing, reliability, and city-screening
assumptions:

```powershell
H:\chatgpt\tools\Python31313\python.exe -m co2alloc.cli profit-scan --sources data\real_inputs_top300\spatial_sources_real.csv --destinations data\real_inputs_top300\spatial_destinations_real.csv --transport-modes data\transport_modes.csv --hubs data\real_inputs_top300\hubs_real.csv --hourly-profiles data\real_inputs_top300\hourly_energy_profiles_real.csv --learning data\technology_scenarios.csv --year 2030 --max-distance 3000 --target-market china --out output\profit_scan_top300_2030.csv
H:\chatgpt\tools\Python31313\python.exe -m co2alloc.cli profit-scan-city --sources data\real_inputs_top300\spatial_sources_real.csv --destinations data\real_inputs_top300\spatial_destinations_real.csv --transport-modes data\transport_modes.csv --hubs data\real_inputs_top300\hubs_real.csv --hourly-profiles data\real_inputs_top300\hourly_energy_profiles_real.csv --learning data\technology_scenarios.csv --year 2030 --max-distance 3000 --target-market china --out output\city_profit_recommendations_top300_2030.csv --detail-out output\city_profit_detail_top300_2030.csv
```

City attribution currently uses a screening city-centre table. For a
publication-grade city map, replace it with an audited prefecture-boundary
spatial join.

The blocked-data workarounds are now normalized into explicit interfaces:

- NBS product-market rows are stored as `year, region, product, quantity, unit`
  observations and converted to destination capacities with a documented
  stoichiometric algorithm.
- CEADs province-sector inventories enter only through a calibration table with
  schema `year, province, source_type, emissions_mtco2`; if the real CEADs file
  is unavailable the fallback multiplier is 1.0 and is labelled as such.
- NETL CO2_T_COM Excel is not a runtime dependency. Pipeline transport uses a
  reduced-order McCoy/Rubin capital-cost regression with flow, distance,
  diameter, discount rate, capacity factor, and booster electricity.

To rebuild those normalized inputs:

```powershell
H:\chatgpt\tools\Python31313\python.exe scripts\build_product_destination_capacity.py
H:\chatgpt\tools\Python31313\python.exe scripts\build_source_inventory_calibration.py --sources data\real_inputs_top300\spatial_sources_real.csv --year 2024 --out data\processed\co2_sources\source_inventory_calibration_fallback.csv
H:\chatgpt\tools\Python31313\python.exe -m co2alloc.cli build-real-inputs --source-year 2024 --top-sources 300 --out-dir data\real_inputs_top300 --manifest-out data\real_inputs_top300\manifest.csv --storage-horizon-years 20 --source-calibration data\processed\co2_sources\source_inventory_calibration_fallback.csv
```

To include direct air capture screening hubs, append the compatible extra source
table:

```powershell
H:\chatgpt\tools\Python31313\python.exe -m co2alloc.cli build-real-inputs --source-year 2024 --top-sources 300 --out-dir data\real_inputs_top300_with_dac --manifest-out data\real_inputs_top300_with_dac\manifest.csv --storage-horizon-years 20 --source-calibration data\processed\co2_sources\source_inventory_calibration_fallback.csv --extra-sources data\dac_sources.csv
H:\chatgpt\tools\Python31313\python.exe -m co2alloc.cli profit-scan-city --sources data\real_inputs_top300_with_dac\spatial_sources_real.csv --destinations data\real_inputs_top300_with_dac\spatial_destinations_real.csv --transport-modes data\transport_modes.csv --hubs data\real_inputs_top300_with_dac\hubs_real.csv --hourly-profiles data\real_inputs_top300_with_dac\hourly_energy_profiles_real.csv --learning data\technology_scenarios.csv --year 2030 --max-distance 1500 --target-market china --out output\city_profit_recommendations_top300_with_dac_2030.csv --detail-out output\city_profit_detail_top300_with_dac_2030.csv
```

Electricity profiles are standardized to hourly resolution. If a provincial
market source provides 15-minute or 5-minute prices, aggregate it before running
the spatial model:

```powershell
H:\chatgpt\tools\Python31313\python.exe scripts\normalize_hourly_electricity_profiles.py --input raw_prices.csv --output hourly_prices.csv --input-interval-minutes 15
```

Main outputs:

- `data\real_inputs_top300\build_summary.csv`
- `output\expanded_scenario_summary.csv`
- `output\expanded_scenario_family_mix.csv`
- `output\expanded_system_summary.csv`
- `output\expanded_transport_mix.csv`
- `output\expanded_top_routes.csv`
- `docs\figures_real\expanded_system_performance.svg`
- `docs\figures_real\expanded_family_mix.svg`
- `docs\figures_real\expanded_current_2030_network.svg`

For policy sensitivities, use `--policy-source cli`; otherwise destination CSV
policy fields are authoritative. Spatial transport is counted in the spatial
layer only, so routed pipeline/rail/ship cost and emissions are not double
counted inside pathway inventories.

## Model boundary

All pathway inventories are normalized to one tonne of captured CO2 entering
the pathway. Results track:

- CO2 captured
- CO2 utilized
- CO2 durably stored
- CO2 released at end of life
- induced process emissions
- displaced conventional product emissions
- net CO2 avoided
- levelized net cost
- technology family, including thermochemical, electrochemical, and photochemical conversion
- geography: source location, destination location, transport mode, distance, source purity, purification penalty
- CO2 source impurities and pressure matching against destination specifications
- CO2 capture cost, capture process emissions, and capture electricity demand
- pipeline scale economies and optional hub aggregation
- hourly electricity price and grid-carbon profiles
- local electrolytic hydrogen production
- water, land, permit-risk, and TRL-risk constraints
- policy: avoided-emissions credit, residual-emissions carbon tax, durable-removal credit
- 2030/2040/2050 technology learning multipliers
- Monte Carlo uncertainty sampling over source availability, capture cost and emissions, CO2 purity, pressure, destination capacity, electricity, grid carbon intensity, hydrogen, policy, purification, impurity removal, pressure boosting, transport, electrolyzer performance, water, land, permit risk, and hub performance
- DAC screening sources loaded through `data\dac_sources.csv` or another
  `--extra-sources` table

Detailed data-interface and algorithm notes are in
`docs\unified_data_interfaces.md`.
The high-accuracy upgrade plan is in `docs\model_accuracy_upgrade_plan.md`.

## City boundary join and standard profitability matrix

Build formal prefecture-level city attribution, then run the standard
profitability matrix:

```powershell
H:\chatgpt\tools\Python31313\python.exe scripts\download_prefecture_boundaries.py
H:\chatgpt\tools\Python31313\python.exe scripts\join_prefecture_boundaries.py --points data\real_inputs_top300_with_dac\spatial_sources_real.csv --out data\processed\admin\source_prefecture_join_top300_with_dac.csv --id-column source_id --type-label source
H:\chatgpt\tools\Python31313\python.exe scripts\join_prefecture_boundaries.py --points data\real_inputs_top300_with_dac\spatial_destinations_real.csv --out data\processed\admin\destination_prefecture_join_top300_with_dac.csv --id-column destination_id --type-label destination
H:\chatgpt\tools\Python31313\python.exe scripts\join_prefecture_boundaries.py --points data\real_inputs_top300_with_dac\hubs_real.csv --out data\processed\admin\hub_prefecture_join_top300_with_dac.csv --id-column hub_id --type-label hub
H:\chatgpt\tools\Python31313\python.exe scripts\run_standard_profitability_matrix.py
H:\chatgpt\tools\Python31313\python.exe scripts\analyze_standard_profitability_matrix.py
```

The matrix writes scenario details, pathway summaries, city recommendations,
and break-even threshold tables under `output\standard_profitability_matrix`.
The result note is `docs\standard_profitability_matrix_results.md`.

## Important limitation

This is a screening model. It is not a substitute for detailed Aspen, HYSYS, or
pilot-validated process design. It is meant to identify defensible decision
boundaries and sensitivity targets for a Joule-level TEA-LCA article.
Some product-market capacity rows remain proxy or scenario ceilings rather than
direct market-demand observations. The model records this in each row's `basis`,
`algorithm`, and `notes` fields so the assumptions can be replaced without
changing the allocator.
