# Download Status Summary

Downloaded and processed core model inputs: CO2 point sources, CEADs 2022 province-sector CO2 inventory, CEADs 2022 provincial energy inventory, CEADs 1997-2022 apparent provincial emissions, CEADs 1997-2019 290-city emissions, CEADs 2010 24-city sector inventories, China storage potential, OSM transport network, UNECE and NGA/WPI ports, provincial hourly load/transmission, MEE/NBS provincial power CO2 factors, CCER/CEA carbon market snapshot, China low-carbon policy intensity, IEA China green H2 assumptions, and CO2 pipeline quality requirements.

Resolved into model interfaces:

- NBS easyquery 403: use official Statistical Yearbook image tables as the reproducible source, normalize checked observations, and convert them to product-destination capacity with `scripts/build_product_destination_capacity.py`.
- CEADs inventories: manually downloaded the 2022 30-province emission workbook, 2022 provincial energy workbook, 1997-2022 apparent provincial emissions, 1997-2019 290-city emissions, and 2010 24-city 45-sector package. These are parsed with `scripts/parse_ceads_2022_inventory.py`, `scripts/parse_ceads_additional_downloads.py`, and `scripts/build_ceads_city_crosswalk.py`. The 2022 province-sector workbook calibrates `source_inventory_calibration_ceads_2022.csv`; the added files support historical trend, fuel-mix, city-sector validation, interactive city-history mapping, and non-DAC city cap constraints.
- NETL CO2_T_COM Excel download unstable: use the public McCoy/Rubin reduced-order pipeline model in `src/co2alloc/pipeline_cost.py`; keep the Excel workbook as a later validation target.

Known remaining gaps: unified public China hourly/15-min spot electricity prices; broader structured NBS product market time series; official historical boundary-change validation for CEADs split/sub-prefecture labels; full plant-level cement/lime/nonmetal-mineral asset reconciliation; validation of the reduced-order pipeline function against NETL Excel examples when the workbook is available.
