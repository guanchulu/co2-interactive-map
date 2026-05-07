$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$env:PYTHONPATH = "src"
$python = "H:\chatgpt\tools\Python31313\python.exe"
& $python -m co2alloc.cli baseline --out output\baseline.csv
& $python -m co2alloc.cli grid --out output\decision_grid.csv --ascii-out output\decision_map.txt --svg-out output\decision_map.svg
& $python -m co2alloc.cli sensitivity --out output\sensitivity.csv
& $python -m co2alloc.cli family --out output\family_best.csv
& $python -m co2alloc.cli spatial-candidates --out output\spatial_candidates.csv
& $python -m co2alloc.cli spatial-allocate --optimizer lp --out output\spatial_allocations.csv --summary-out output\spatial_summary.csv
& $python -m co2alloc.cli monte-carlo --runs 100 --out output\monte_carlo_summary.csv
