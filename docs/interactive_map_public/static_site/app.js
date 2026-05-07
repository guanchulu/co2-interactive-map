const LON_MIN = 73.0;
const LON_MAX = 135.5;
const LAT_MIN = 18.0;
const LAT_MAX = 53.5;
const MAP_W = 940;
const MAP_H = 650;
const PAD_X = 26;
const PAD_Y = 22;

const COLORS = {
  storage: "#245f6d",
  mineralization: "#3e9568",
  synthetic_fuels: "#c97836",
  chemicals: "#81683e",
  wait: "#aab5b5",
  positive: "#2c8d72",
  negative: "#b95663",
  near: "#d59a32",
  empty: "#d4dcdf",
  emptyStroke: "#aebcc1",
};

const ARCHETYPE_COLORS = {
  storage_first: COLORS.storage,
  mineralization_base: COLORS.mineralization,
  coastal_saf_export_hub: COLORS.synthetic_fuels,
  northwest_h2_chemical_hub: "#b9842f",
  electrochemical_formate_hub: "#8065a8",
  policy_backed_chemical_hub: "#81683e",
  wait_or_aggregate: COLORS.wait,
};

const CATEGORY_LABELS = {
  geological_storage: "Storage",
  mineral_products: "Mineral products",
  synthetic_fuels: "Fuels/SAF",
  chemicals: "Chemicals",
};

const CATEGORY_COLORS = {
  geological_storage: COLORS.storage,
  mineral_products: COLORS.mineralization,
  synthetic_fuels: COLORS.synthetic_fuels,
  chemicals: COLORS.chemicals,
};

const URL_PARAMS = new URLSearchParams(window.location.search);
const ALLOWED_LAYERS = new Set(["margin", "allocation", "fusion", "policy", "visual", "process", "ceads", "archetype"]);
const requestedLayer = URL_PARAMS.get("layer");
const requestedYear = URL_PARAMS.get("year");
const requestedRoutes = URL_PARAMS.get("routes");

const state = {
  year: requestedYear || "2060",
  layer: ALLOWED_LAYERS.has(requestedLayer) ? requestedLayer : "margin",
  showRoutes: requestedRoutes === "0" ? false : true,
  selectedCityId: null,
  boundaries: null,
  cities: null,
  routes: null,
  support: null,
  summary: null,
  pathCache: new Map(),
};

const el = {
  yearSelect: document.querySelector("#yearSelect"),
  layerSelect: document.querySelector("#layerSelect"),
  routeToggle: document.querySelector("#routeToggle"),
  citySearch: document.querySelector("#citySearch"),
  cityList: document.querySelector("#cityList"),
  statsStrip: document.querySelector("#statsStrip"),
  mapSvg: document.querySelector("#mapSvg"),
  cityLayer: document.querySelector("#cityLayer"),
  routeLayer: document.querySelector("#routeLayer"),
  selectedLayer: document.querySelector("#selectedLayer"),
  legend: document.querySelector("#legend"),
  tooltip: document.querySelector("#tooltip"),
  cityTitle: document.querySelector("#cityTitle"),
  cityBadges: document.querySelector("#cityBadges"),
  recommendation: document.querySelector("#recommendation"),
  timelineChart: document.querySelector("#timelineChart"),
  allocationPanel: document.querySelector("#allocationPanel"),
  uncertaintyPanel: document.querySelector("#uncertaintyPanel"),
  stressPanel: document.querySelector("#stressPanel"),
};

function fmt(value, digits = 0) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "n/a";
  return Number(value).toLocaleString("en-US", { maximumFractionDigits: digits, minimumFractionDigits: digits });
}

function project(lon, lat) {
  const x = PAD_X + ((lon - LON_MIN) / (LON_MAX - LON_MIN)) * (MAP_W - 2 * PAD_X);
  const y = PAD_Y + (1 - (lat - LAT_MIN) / (LAT_MAX - LAT_MIN)) * (MAP_H - 2 * PAD_Y);
  return [x, y];
}

function ringToPath(ring) {
  if (!ring || ring.length === 0) return "";
  const first = project(Number(ring[0][0]), Number(ring[0][1]));
  let d = `M${first[0].toFixed(1)},${first[1].toFixed(1)}`;
  for (let i = 1; i < ring.length; i += 1) {
    const point = project(Number(ring[i][0]), Number(ring[i][1]));
    d += `L${point[0].toFixed(1)},${point[1].toFixed(1)}`;
  }
  return `${d}Z`;
}

function geometryToPath(geometry) {
  if (!geometry) return "";
  const polygons = geometry.type === "Polygon" ? [geometry.coordinates] : geometry.coordinates || [];
  return polygons
    .map((polygon) => polygon.map((ring) => ringToPath(ring)).join(""))
    .join("");
}

function marginColor(value) {
  if (value === null || value === undefined) return COLORS.empty;
  const v = Number(value);
  if (v >= 0) {
    const t = Math.min(1, v / 1500);
    return `rgb(${Math.round(232 - 190 * t)}, ${Math.round(246 - 126 * t)}, ${Math.round(235 - 150 * t)})`;
  }
  const t = Math.min(1, Math.abs(v) / 550);
  return `rgb(${Math.round(252 - 105 * t)}, ${Math.round(230 - 135 * t)}, ${Math.round(214 - 96 * t)})`;
}

function allocationColor(value) {
  const t = Math.min(1, Math.max(0, Number(value || 0)) / 32);
  return `rgb(${Math.round(232 - 183 * t)}, ${Math.round(246 - 117 * t)}, ${Math.round(235 - 137 * t)})`;
}

function fusionColor(value) {
  const t = Math.min(1, Math.max(0, Number(value || 0)));
  return `rgb(${Math.round(238 - 196 * t)}, ${Math.round(246 - 118 * t)}, ${Math.round(238 - 158 * t)})`;
}

function componentColor(value) {
  const t = Math.min(1, Math.max(0, Number(value || 0)));
  return `rgb(${Math.round(236 - 172 * t)}, ${Math.round(239 - 112 * t)}, ${Math.round(242 - 127 * t)})`;
}

function ceadsColor(value) {
  if (value === null || value === undefined || Number(value) <= 0) return COLORS.empty;
  const t = Math.min(1, Math.log1p(Number(value)) / Math.log1p(850));
  return `rgb(${Math.round(238 - 195 * t)}, ${Math.round(245 - 111 * t)}, ${Math.round(241 - 129 * t)})`;
}

function stressColor(value) {
  const v = Number(value || 0);
  if (v >= 0) {
    const t = Math.min(1, v / 50);
    return `rgb(${Math.round(232 - 178 * t)}, ${Math.round(246 - 114 * t)}, ${Math.round(235 - 126 * t)})`;
  }
  const t = Math.min(1, Math.abs(v) / 80);
  return `rgb(${Math.round(249 - 80 * t)}, ${Math.round(228 - 112 * t)}, ${Math.round(218 - 97 * t)})`;
}

function cityForFeature(feature) {
  return state.cities[feature.properties.city_id];
}

function yearData(city, year = state.year) {
  return city?.timeline?.[year] || null;
}

function isEnglishSafe(value) {
  return value && !/[\u3400-\u9fff]/.test(String(value));
}

function displayName(city) {
  if (!city) return "Unknown city";
  if (isEnglishSafe(city.display_name_en)) return city.display_name_en;
  if (isEnglishSafe(city.city_name_en)) return city.city_name_en;
  if (isEnglishSafe(city.display_name)) return city.display_name;
  if (isEnglishSafe(city.city_name)) return city.city_name;
  return `City ${city.city_id || "unknown"}`;
}

function featureDisplayName(feature) {
  const props = feature.properties || {};
  if (isEnglishSafe(props.city_name_en)) return props.city_name_en;
  if (isEnglishSafe(props.city_name)) return props.city_name;
  return `City ${props.city_id || "unknown"}`;
}

function featureFill(feature) {
  if (!feature.properties.screened) return COLORS.empty;
  const city = cityForFeature(feature);
  const yd = yearData(city);
  if (!yd) return COLORS.empty;
  if (state.layer === "allocation") return allocationColor(city.allocation_summary?.allocated_mtco2_per_year);
  if (state.layer === "fusion") return fusionColor(city.multimodal?.fusion_scores?.neutrality_backbone);
  if (state.layer === "policy") return componentColor(city.multimodal?.component_scores?.policy_text);
  if (state.layer === "visual") return componentColor(city.multimodal?.component_scores?.visual_remote_sensing);
  if (state.layer === "process") {
    const processScore = 0.55 * Number(city.multimodal?.component_scores?.process_flowsheet || 0) + 0.45 * Number(city.multimodal?.component_scores?.reservoir_simulation || 0);
    return componentColor(processScore);
  }
  if (state.layer === "ceads") return ceadsColor(city.ceads_history?.latest_emissions_mtco2);
  if (state.layer === "archetype") return ARCHETYPE_COLORS[yd.archetype] || COLORS.wait;
  return marginColor(yd.best_margin_usd_per_tco2);
}

function renderStats() {
  const s = state.summary;
  el.statsStrip.innerHTML = [
    [`${fmt(s.city_count)}`, "screened cities"],
    [`${fmt(s.positive_2030)}`, "positive in 2030"],
    [`${fmt(s.positive_2060)}`, "positive in 2060"],
    [`${fmt(s.ceads_history_city_count)}`, "with CEADs history"],
    [`${fmt(s.managed_mtco2_2060, 1)} Mt`, "managed CO2 in LP"],
    [`${fmt(s.profit_busd_2060, 1)} BUSD`, "2060 profit pool"],
  ]
    .map(([value, label]) => `<div class="stat"><strong>${value}</strong><span>${label}</span></div>`)
    .join("");
}

function renderLegend() {
  let items;
  if (state.layer === "archetype") {
    items = [
      ["storage", ARCHETYPE_COLORS.storage_first],
      ["mineralization", ARCHETYPE_COLORS.mineralization_base],
      ["SAF/export", ARCHETYPE_COLORS.coastal_saf_export_hub],
      ["chemical hub", ARCHETYPE_COLORS.policy_backed_chemical_hub],
      ["wait", ARCHETYPE_COLORS.wait_or_aggregate],
      ["no data", COLORS.empty],
    ];
  } else if (state.layer === "allocation") {
    items = [
      ["0 Mt", allocationColor(0)],
      ["5 Mt", allocationColor(5)],
      ["15 Mt", allocationColor(15)],
      ["30+ Mt", allocationColor(32)],
      ["no data", COLORS.empty],
    ];
  } else if (state.layer === "fusion") {
    items = [
      ["0.2", fusionColor(0.2)],
      ["0.4", fusionColor(0.4)],
      ["0.6", fusionColor(0.6)],
      ["0.8+", fusionColor(0.85)],
      ["no data", COLORS.empty],
    ];
  } else if (["policy", "visual", "process"].includes(state.layer)) {
    items = [
      ["0.2", componentColor(0.2)],
      ["0.4", componentColor(0.4)],
      ["0.6", componentColor(0.6)],
      ["0.8+", componentColor(0.85)],
      ["no data", COLORS.empty],
    ];
  } else if (state.layer === "ceads") {
    items = [
      ["0 Mt", ceadsColor(0)],
      ["25 Mt", ceadsColor(25)],
      ["100 Mt", ceadsColor(100)],
      ["300+ Mt", ceadsColor(300)],
      ["no data", COLORS.empty],
    ];
  } else {
    items = [
      ["< -500", marginColor(-550)],
      ["-100", marginColor(-100)],
      ["0", marginColor(0)],
      ["+500", marginColor(500)],
      ["> +1200", marginColor(1400)],
      ["no data", COLORS.empty],
    ];
  }
  const legendTitle = {
    margin: "Best margin, USD/tCO2",
    allocation: "2060 LP allocation",
    fusion: "2060 neutrality-backbone fusion score",
    policy: "Policy-text embedding score",
    visual: "Satellite/visual activity score",
    process: "Process/reservoir simulation score",
    ceads: "Latest CEADs city emissions, MtCO2",
    archetype: "Technology archetype",
  }[state.layer];
  el.legend.innerHTML = `
    <div class="legend-title">${legendTitle}</div>
    <div class="legend-row">
      ${items.map(([label, color]) => `<span class="legend-item"><i class="swatch" style="background:${color}"></i>${label}</span>`).join("")}
    </div>
  `;
}

function renderRoutes() {
  el.routeLayer.innerHTML = "";
  if (!state.showRoutes) return;
  const routes = state.selectedCityId
    ? state.routes.filter((route) => route.city_id === state.selectedCityId)
    : state.routes.slice(0, 45);
  const maxMt = Math.max(...routes.map((route) => route.allocated_mtco2_per_year), 1);
  for (const route of routes) {
    const [sx, sy] = project(route.source_lon, route.source_lat);
    const [dx, dy] = project(route.destination_lon, route.destination_lat);
    const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
    line.setAttribute("x1", sx);
    line.setAttribute("y1", sy);
    line.setAttribute("x2", dx);
    line.setAttribute("y2", dy);
    line.setAttribute("class", "route-line");
    line.setAttribute("stroke", CATEGORY_COLORS[route.category] || COLORS.wait);
    line.setAttribute("stroke-width", 0.7 + 4.6 * (route.allocated_mtco2_per_year / maxMt));
    line.setAttribute("opacity", state.selectedCityId ? "0.72" : "0.32");
    el.routeLayer.appendChild(line);
  }
}

function renderMap() {
  el.cityLayer.innerHTML = "";
  for (const feature of state.boundaries.features) {
    const cityId = feature.properties.city_id;
    let d = state.pathCache.get(cityId);
    if (!d) {
      d = geometryToPath(feature.geometry);
      state.pathCache.set(cityId, d);
    }
    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    path.setAttribute("d", d);
    path.setAttribute("fill", featureFill(feature));
    path.setAttribute("stroke", feature.properties.screened ? "#ffffff" : COLORS.emptyStroke);
    path.setAttribute("stroke-width", feature.properties.screened ? "0.35" : "0.32");
    path.setAttribute("opacity", feature.properties.screened ? "0.96" : "0.88");
    path.setAttribute("class", "city-shape");
    path.dataset.cityId = cityId;
    path.addEventListener("click", () => selectCity(cityId));
    path.addEventListener("mousemove", (event) => showTooltip(event, feature));
    path.addEventListener("mouseleave", hideTooltip);
    el.cityLayer.appendChild(path);
  }
  renderRoutes();
  renderSelectedOutline();
  renderLegend();
}

function renderSelectedOutline() {
  el.selectedLayer.innerHTML = "";
  if (!state.selectedCityId) return;
  const feature = state.boundaries.features.find((item) => item.properties.city_id === state.selectedCityId);
  if (!feature) return;
  const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
  path.setAttribute("d", state.pathCache.get(state.selectedCityId) || geometryToPath(feature.geometry));
  path.setAttribute("class", "selected-outline");
  el.selectedLayer.appendChild(path);
}

function showTooltip(event, feature) {
  const city = cityForFeature(feature);
  const yd = yearData(city);
  el.tooltip.hidden = false;
  el.tooltip.style.left = `${event.clientX + 14}px`;
  el.tooltip.style.top = `${event.clientY + 14}px`;
  el.tooltip.innerHTML = city
    ? `<strong>${displayName(city)}</strong><br>${yd.best_pathway_label}<br>${fmt(yd.best_margin_usd_per_tco2, 1)} USD/tCO2 in ${state.year}<br>CEADs latest: ${city.ceads_history?.available ? `${fmt(city.ceads_history.latest_emissions_mtco2, 1)} MtCO2` : "n/a"}`
    : `<strong>${featureDisplayName(feature)}</strong><br>No model result / not screened`;
}

function hideTooltip() {
  el.tooltip.hidden = true;
}

function badge(label, kind = "") {
  return `<span class="badge ${kind}">${label}</span>`;
}

function routeCategoryColor(category) {
  return CATEGORY_COLORS[category] || COLORS.wait;
}

function selectCity(cityId) {
  if (!state.cities[cityId]) return;
  state.selectedCityId = cityId;
  renderRoutes();
  renderSelectedOutline();
  renderDetails();
}

function renderDetails() {
  const city = state.cities[state.selectedCityId];
  if (!city) return;
  const current = yearData(city, "2030");
  const future = yearData(city, "2060");
  const active = yearData(city, state.year);
  const alloc = city.allocation_summary || {};
  const uncertainty = state.support.uncertainty[future.best_pathway] || null;

  el.cityTitle.textContent = `${displayName(city)} (${city.city_id})`;
  el.cityBadges.innerHTML = [
    badge(current.best_margin_usd_per_tco2 > 0 ? "Profitable now" : "Not profitable now", current.best_margin_usd_per_tco2 > 0 ? "ok" : "neg"),
    badge(future.best_margin_usd_per_tco2 > 0 ? "Profitable in 2060" : "Not profitable in 2060", future.best_margin_usd_per_tco2 > 0 ? "ok" : "warn"),
    badge(active.archetype_label || active.archetype),
    badge(`${fmt(alloc.allocated_mtco2_per_year, 1)} Mt/yr LP`),
    badge(city.ceads_history?.available ? `${fmt(city.ceads_history.latest_emissions_mtco2, 0)} Mt CEADs` : "no CEADs history", city.ceads_history?.available ? "ok" : "warn"),
  ].join("");

  el.recommendation.innerHTML = `
    <div class="metric-grid">
      <div class="metric"><strong>${future.best_pathway_label}</strong><span>recommended pathway</span></div>
      <div class="metric"><strong>${future.best_product || "none"}</strong><span>target product/service</span></div>
      <div class="metric"><strong>${fmt(future.best_margin_usd_per_tco2, 1)}</strong><span>2060 margin, USD/tCO2</span></div>
      <div class="metric"><strong>${fmt(city.multimodal?.fusion_scores?.neutrality_backbone || 0, 2)}</strong><span>multimodal fusion score</span></div>
      <div class="metric"><strong>${city.ceads_history?.available ? fmt(city.ceads_history.latest_emissions_mtco2, 1) : "n/a"}</strong><span>latest CEADs MtCO2</span></div>
      <div class="metric"><strong>${city.ceads_history?.available ? city.ceads_history.peak_year : "n/a"}</strong><span>CEADs peak year</span></div>
    </div>
    <p class="logic">${future.investment_logic}</p>
  `;

  renderTimeline(city);
  renderAllocation(city);
  renderUncertainty(city, uncertainty);
  renderStress();
}

function renderTimeline(city) {
  const values = Object.values(city.timeline).map((item) => item.best_margin_usd_per_tco2);
  const maxAbs = Math.max(...values.map((value) => Math.abs(value)), 1);
  const profitRows = Object.keys(city.timeline)
    .sort()
    .map((year) => {
      const item = city.timeline[year];
      const value = item.best_margin_usd_per_tco2;
      const width = Math.max(1, Math.abs(value) / maxAbs * 50);
      const cls = value >= 0 ? "pos" : "neg";
      return `
        <div class="year-row">
          <strong>${year}</strong>
          <div class="bar-track">
            <span class="bar-zero"></span>
            <span class="bar-fill ${cls}" style="width:${width}%"></span>
          </div>
          <span>${fmt(value, 0)}</span>
        </div>
      `;
    })
    .join("");
  const ceadsSeries = city.ceads_history?.series || [];
  const maxCeads = Math.max(...ceadsSeries.map((item) => item.emissions_mtco2), 1);
  const ceadsRows = ceadsSeries.length
    ? `
      <div class="chart-kicker">CEADs historical emissions</div>
      ${ceadsSeries
        .filter((item) => [1997, 2000, 2005, 2010, 2015, 2019].includes(Number(item.year)))
        .map((item) => `
          <div class="year-row">
            <strong>${item.year}</strong>
            <div class="bar-track">
              <span class="bar-fill ceads" style="width:${Math.max(1, (item.emissions_mtco2 / maxCeads) * 100)}%"></span>
            </div>
            <span>${fmt(item.emissions_mtco2, 0)}</span>
          </div>
        `)
        .join("")}
    `
    : `<p class="logic">No matched CEADs city history for this prefecture.</p>`;
  el.timelineChart.innerHTML = `
    <div class="chart-kicker">Model profitability</div>
    ${profitRows}
    ${ceadsRows}
  `;
}

function renderAllocation(city) {
  const alloc = city.allocations || [];
  if (!alloc.length) {
    el.allocationPanel.innerHTML = `<p class="logic">The 2060 max-profit LP does not select this city. It remains a capture-ready, aggregation, or data-improvement candidate.</p>`;
    return;
  }
  const totals = {};
  for (const item of alloc) {
    totals[item.category] = (totals[item.category] || 0) + item.allocated_mtco2_per_year;
  }
  const total = Object.values(totals).reduce((sum, value) => sum + value, 0);
  const stack = Object.entries(totals)
    .map(([category, value]) => `<span title="${category}" style="width:${(value / total) * 100}%;background:${routeCategoryColor(category)}"></span>`)
    .join("");
  const rows = alloc
    .slice(0, 5)
    .map((item) => `
      <div class="allocation-item">
        <strong>${item.pathway_label}</strong>
        <div class="logic">${CATEGORY_LABELS[item.category] || item.category}; ${fmt(item.allocated_mtco2_per_year, 2)} Mt/yr; ${fmt(item.margin_usd_per_tco2, 0)} USD/t; ${fmt(item.distance_km, 0)} km</div>
      </div>
    `)
    .join("");
  el.allocationPanel.innerHTML = `
    <div class="metric-grid">
      <div class="metric"><strong>${fmt(city.allocation_summary.allocated_mtco2_per_year, 1)} Mt</strong><span>managed CO2/yr</span></div>
      <div class="metric"><strong>${fmt(city.allocation_summary.durable_mtco2_per_year, 1)} Mt</strong><span>durable CO2/yr</span></div>
    </div>
    <div class="allocation-list">
      <div class="stackbar">${stack}</div>
      ${rows}
    </div>
  `;
}

function renderUncertainty(city, uncertainty) {
  const flags = city.multimodal?.flags || {};
  const drivers = state.support.drivers[yearData(city, "2060").best_pathway] || [];
  const driverRows = drivers
    .slice(0, 3)
    .map((item) => `<tr><td>${item.driver}</td><td>${fmt(item.correlation, 2)}</td></tr>`)
    .join("");
  const evidenceRows = Object.entries(flags)
    .map(([name, value]) => `
      <div class="evidence-row">
        <span>${name}</span>
        <div class="evidence-track"><span style="width:${Math.max(4, Number(value) * 100)}%"></span></div>
      </div>
    `)
    .join("");
  el.uncertaintyPanel.innerHTML = `
    <div class="metric-grid">
      <div class="metric"><strong>${uncertainty ? fmt(uncertainty.probability_positive * 100, 0) : "n/a"}%</strong><span>positive-margin probability</span></div>
      <div class="metric"><strong>${fmt(city.multimodal?.readiness_score || 0, 2)}</strong><span>multimodal readiness</span></div>
      <div class="metric"><strong>#${fmt(city.multimodal?.fusion_ranks?.near_term_profit || 0, 0)}</strong><span>near-term rank</span></div>
      <div class="metric"><strong>#${fmt(city.multimodal?.fusion_ranks?.policy_exit_resilience || 0, 0)}</strong><span>policy-exit rank</span></div>
    </div>
    <table class="small-table">
      <thead><tr><th>fusion mode</th><th>score</th><th>rank</th></tr></thead>
      <tbody>
        <tr><td>near-term profit</td><td>${fmt(city.multimodal?.fusion_scores?.near_term_profit || 0, 2)}</td><td>${fmt(city.multimodal?.fusion_ranks?.near_term_profit || 0, 0)}</td></tr>
        <tr><td>2060 neutrality</td><td>${fmt(city.multimodal?.fusion_scores?.neutrality_backbone || 0, 2)}</td><td>${fmt(city.multimodal?.fusion_ranks?.neutrality_backbone || 0, 0)}</td></tr>
        <tr><td>policy exit</td><td>${fmt(city.multimodal?.fusion_scores?.policy_exit_resilience || 0, 2)}</td><td>${fmt(city.multimodal?.fusion_ranks?.policy_exit_resilience || 0, 0)}</td></tr>
        <tr><td>data quality</td><td>${fmt(city.multimodal?.fusion_scores?.data_quality_priority || 0, 2)}</td><td>${fmt(city.multimodal?.fusion_ranks?.data_quality_priority || 0, 0)}</td></tr>
      </tbody>
    </table>
    <table class="small-table">
      <thead><tr><th>driver</th><th>abs corr.</th></tr></thead>
      <tbody>${driverRows || "<tr><td>no driver data</td><td>n/a</td></tr>"}</tbody>
    </table>
    <table class="small-table">
      <thead><tr><th>multimodal component</th><th>score/source</th></tr></thead>
      <tbody>
        <tr><td>policy text</td><td>${fmt(city.multimodal?.component_scores?.policy_text || 0, 2)}; ${city.multimodal?.component_sources?.policy_top_doc_ids || "n/a"}</td></tr>
        <tr><td>satellite/visual</td><td>${fmt(city.multimodal?.component_scores?.visual_remote_sensing || 0, 2)}; ${city.multimodal?.component_sources?.visual_raster_status || "n/a"}</td></tr>
        <tr><td>flowsheet</td><td>${fmt(city.multimodal?.component_scores?.process_flowsheet || 0, 2)}; ${city.multimodal?.component_sources?.flowsheet_source_type || "n/a"}</td></tr>
        <tr><td>reservoir</td><td>${fmt(city.multimodal?.component_scores?.reservoir_simulation || 0, 2)}; ${city.multimodal?.component_sources?.reservoir_simulator || "n/a"}</td></tr>
      </tbody>
    </table>
    ${evidenceRows}
  `;
}

function renderStress() {
  const scenarios = [
    ["policy_supported_effort", "support"],
    ["policy_exit_green_premium", "exit"],
    ["commodity_only_no_support", "no support"],
    ["war_energy_security_shock", "war"],
    ["earthquake_pipeline_disruption", "quake"],
    ["pandemic_demand_slump", "pandemic"],
    ["compound_stress_no_support", "compound"],
  ];
  const cats = ["geological_storage", "mineral_products", "synthetic_fuels", "chemicals"];
  const lookup = new Map(state.support.stress.map((row) => [`${row.scenario}|${row.category}`, row.profit_busd_per_year]));
  el.stressPanel.innerHTML = `
    <div class="stress-row">
      <strong>scenario</strong>
      ${cats.map((cat) => `<strong>${CATEGORY_LABELS[cat]}</strong>`).join("")}
    </div>
    ${scenarios
      .map(([scenario, label]) => `
        <div class="stress-row">
          <strong>${label}</strong>
          ${cats
            .map((cat) => {
              const value = lookup.get(`${scenario}|${cat}`) || 0;
              return `<span class="stress-cell" style="background:${stressColor(value)}">${fmt(value, 1)}</span>`;
            })
            .join("")}
        </div>
      `)
      .join("")}
  `;
}

function initControls() {
  for (const year of state.summary.years) {
    const option = document.createElement("option");
    option.value = String(year);
    option.textContent = String(year);
    option.selected = String(year) === state.year;
    el.yearSelect.appendChild(option);
  }
  if (!state.summary.years.map(String).includes(state.year)) {
    state.year = String(state.summary.years[state.summary.years.length - 1]);
    el.yearSelect.value = state.year;
  }
  el.layerSelect.value = state.layer;
  el.routeToggle.checked = state.showRoutes;
  const sortedCities = Object.values(state.cities).sort((a, b) => displayName(a).localeCompare(displayName(b), "en-US"));
  el.cityList.innerHTML = sortedCities
    .map((city) => `<option value="${displayName(city)}">${city.city_id}</option><option value="${city.city_id}">${displayName(city)}</option>`)
    .join("");
  el.yearSelect.addEventListener("change", () => {
    state.year = el.yearSelect.value;
    renderMap();
    renderDetails();
  });
  el.layerSelect.addEventListener("change", () => {
    state.layer = el.layerSelect.value;
    renderMap();
  });
  el.routeToggle.addEventListener("change", () => {
    state.showRoutes = el.routeToggle.checked;
    renderRoutes();
  });
  el.citySearch.addEventListener("change", () => {
    const value = el.citySearch.value.trim();
    const city = Object.values(state.cities).find((item) => displayName(item) === value || item.city_id === value);
    if (city) selectCity(city.city_id);
  });
}

async function loadData() {
  const [boundaries, cities, routes, support, summary] = await Promise.all([
    fetch("./data/city_boundaries.geojson").then((response) => response.json()),
    fetch("./data/city_metrics.json").then((response) => response.json()),
    fetch("./data/route_links.json").then((response) => response.json()),
    fetch("./data/supporting_tables.json").then((response) => response.json()),
    fetch("./data/summary.json").then((response) => response.json()),
  ]);
  state.boundaries = boundaries;
  state.cities = cities;
  state.routes = routes;
  state.support = support;
  state.summary = summary;
  const topCity = Object.values(cities).sort((a, b) => b.allocation_summary.allocated_mtco2_per_year - a.allocation_summary.allocated_mtco2_per_year)[0];
  const requestedCity = URL_PARAMS.get("city");
  state.selectedCityId = cities[requestedCity] ? requestedCity : topCity.city_id;
}

loadData()
  .then(() => {
    initControls();
    renderStats();
    renderMap();
    renderDetails();
  })
  .catch((error) => {
    el.cityTitle.textContent = "Data load failed";
    el.recommendation.innerHTML = `<p class="logic">${error.message}</p>`;
    console.error(error);
  });
