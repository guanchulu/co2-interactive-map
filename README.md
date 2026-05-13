# Interactive CO2 City Map

Run from repository root:

```powershell
H:\chatgpt\tools\Python31313\python.exe scripts\build_interactive_map_data.py
H:\chatgpt\tools\Python31313\python.exe -m http.server 8050 --bind 127.0.0.1 --directory docs\interactive_map
```

Open:

```text
http://127.0.0.1:8050/
```

Direct reproducible views:

```text
http://127.0.0.1:8050/?layer=fusion&city=420100&year=2060
http://127.0.0.1:8050/?layer=policy&city=420100&year=2060
http://127.0.0.1:8050/?layer=visual&city=420100&year=2060
http://127.0.0.1:8050/?layer=process&city=420100&year=2060
http://127.0.0.1:8050/?layer=allocation&city=420100&year=2060
http://127.0.0.1:8050/?layer=archetype&city=420100&year=2060
```

The app lets users click prefecture-level city regions and inspect:

- current 2030 and future 2060 profitability
- recommended CO2 treatment pathway and product/service
- margin timeline through 2030, 2035, 2040, 2045, 2050, 2055 and 2060
- 2060 LP allocation and route portfolio
- route network overlays
- Monte Carlo positive-margin probability and uncertainty drivers
- multimodal neutrality-backbone heatmap, fusion scores, and near-term/policy-exit/data-quality ranks
- policy-text embedding, satellite/remote-sensing, process-flowsheet, and reservoir simulator component layers
- multimodal evidence quality flags and upgrade gaps
- system-level policy and shock stress matrix

The web app is static HTML/CSS/JavaScript. It needs a local HTTP server because browsers block local `fetch()` calls when opened directly as a `file://` URL.
