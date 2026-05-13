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
const DATA_BASE = window.CO2_MAP_BASE || "./";
const BOUNDARY_CDN_URL = "https://cdn.jsdelivr.net/npm/cn-atlas@0.1.2/prefectures.json";

function dataPath(path) {
  const base = DATA_BASE.endsWith("/") ? DATA_BASE : `${DATA_BASE}/`;
  return `${base}${path}`;
}

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

function hasNumber(value) {
  return value !== null && value !== undefined && !Number.isNaN(Number(value));
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

function featureForCityId(cityId) {
  return state.boundaries.features.find((feature) => feature.properties.city_id === cityId) || null;
}

function normalizeCityId(value) {
  if (value === null || value === undefined) return "";
  const text = String(value).trim();
  return text.length === 6 ? text : text.padStart(6, "0");
}

function boundaryFeatureId(feature) {
  const props = feature.properties || {};
  return normalizeCityId(props.city_id || props.id || props.adcode || props["\u533a\u5212\u7801"] || "");
}

function dataStatusLabel(dataStatus) {
  if (dataStatus === "model_result") return "Full pathway chain is available in the current screened model.";
  if (dataStatus === "emissions_only") return "City emissions are available, but the full source-capture-destination-transport-market chain is incomplete.";
  return "Boundary available; no CO2 pathway or CEADs record is linked yet.";
}

function expandOverlayRecord(record) {
  if (Array.isArray(record)) {
    const [latestEmissions, latestYear, peakEmissions, peakYear, screenedFlag, sourceCount] = record;
    const screened = Boolean(screenedFlag);
    const dataStatus = screened ? "model_result" : (hasNumber(latestEmissions) ? "emissions_only" : "boundary_only");
    return {
      screened,
      data_status: dataStatus,
      data_status_label: dataStatusLabel(dataStatus),
      screened_source_count: sourceCount || 0,
      ceads_latest_emissions: latestEmissions,
      ceads_latest_year: latestYear,
      ceads_peak_emissions: peakEmissions,
      ceads_peak_year: peakYear,
    };
  }
  return record || {};
}

function mergeBoundaryOverlay(boundaries, overlay) {
  const overlayById = overlay?.cities || overlay || {};
  const features = (boundaries?.features || []).map((feature) => {
    const cityId = boundaryFeatureId(feature);
    const props = feature.properties || {};
    const extra = expandOverlayRecord(overlayById[cityId]);
    const defaultName = isEnglishSafe(props.name) ? props.name : "Boundary city";
    const dataStatus = extra.data_status || "boundary_only";
    const merged = {
      city_id: cityId,
      city_name: extra.city_name || defaultName,
      city_name_en: extra.city_name_en || extra.city_name || defaultName,
      province_name: extra.province_name || "",
      province_name_en: extra.province_name_en || extra.province_name || "",
      screened: false,
      data_status: dataStatus,
      data_status_label: extra.data_status_label || dataStatusLabel(dataStatus),
      screened_source_count: 0,
      missing_chain_count: undefined,
      missing_chain_labels: [],
      ...props,
      ...extra,
      city_id: cityId,
    };
    return { ...feature, properties: merged };
  });
  return { type: "FeatureCollection", features };
}

async function fetchJsonOrNull(url) {
  try {
    const response = await fetch(url);
    if (!response.ok) return null;
    return response.json();
  } catch (_) {
    return null;
  }
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
  return "Boundary city";
}

function featureDisplayName(feature) {
  const props = feature.properties || {};
  if (isEnglishSafe(props.city_name_en)) return props.city_name_en;
  if (isEnglishSafe(props.city_name)) return props.city_name;
  return "Boundary city";
}

function featureFill(feature) {
  if (state.layer === "ceads") return ceadsColor(feature.properties.ceads_latest_emissions);
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
  if (state.layer === "archetype") return ARCHETYPE_COLORS[yd.archetype] || COLORS.wait;
  return marginColor(yd.best_margin_usd_per_tco2);
}

function renderStats() {
  const s = state.summary;
  el.statsStrip.innerHTML = [
    [`${fmt(s.prefecture_boundary_count)}`, "prefecture boundaries"],
    [`${fmt(s.city_count)}`, "full pathway cities"],
    [`${fmt(s.emissions_only_city_count)}`, "emissions-only cities"],
    [`${fmt(s.boundary_only_city_count)}`, "boundary-only cities"],
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
    : `<strong>${featureDisplayName(feature)}</strong><br>${feature.properties.data_status_label || "No model result / not screened"}<br>CEADs latest: ${hasNumber(feature.properties.ceads_latest_emissions) ? `${fmt(feature.properties.ceads_latest_emissions, 1)} MtCO2` : "n/a"}`;
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
  if (!state.cities[cityId] && !featureForCityId(cityId)) return;
  state.selectedCityId = cityId;
  renderRoutes();
  renderSelectedOutline();
  renderDetails();
}

function renderDetails() {
  const city = state.cities[state.selectedCityId];
  if (!city) {
    renderNoDataDetails(featureForCityId(state.selectedCityId));
    return;
  }
  const current = yearData(city, "2030");
  const future = yearData(city, "2060");
  const active = yearData(city, state.year);
  const alloc = city.allocation_summary || {};
  const uncertainty = state.support.uncertainty[future.best_pathway] || null;

  el.cityTitle.textContent = displayName(city);
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

function chainStatusLabel(status) {
  if (status === "available") return "available";
  if (status === "partial") return "partial";
  return "missing";
}

function renderChainList(steps = []) {
  return `
    <div class="chain-list">
      ${steps
        .map((step) => `
          <div class="chain-row ${step.status}">
            <span class="chain-dot"></span>
            <div>
              <strong>${step.label}</strong>
              <em>${chainStatusLabel(step.status)}</em>
              <p>${step.detail}</p>
            </div>
          </div>
        `)
        .join("")}
    </div>
  `;
}

function inferChainSteps(props = {}) {
  const hasMetrics = props.screened || props.data_status === "model_result";
  const hasCeads = hasNumber(props.ceads_latest_emissions);
  const sourceCount = Number(props.screened_source_count || 0);
  return [
    {
      label: "1. City boundary",
      status: "available",
      detail: "Prefecture polygon is available and drawn on the map.",
    },
    {
      label: "2. Large industrial CO2 point source",
      status: hasMetrics || sourceCount > 0 ? "available" : "missing",
      detail: hasMetrics || sourceCount > 0
        ? `${Math.max(sourceCount, 1)} screened point-source package is linked.`
        : "No screened large industrial point source is joined to this prefecture in the current public source package.",
    },
    {
      label: "3. Capture cost, energy, purity and pressure",
      status: hasMetrics ? "available" : "missing",
      detail: hasMetrics
        ? "Capture cost, energy, purity, pressure and impurity assumptions are assigned."
        : "Needs source-specific capture cost, capture energy, CO2 purity, pressure and impurity assumptions.",
    },
    {
      label: "4. Destination and CO2 specification",
      status: hasMetrics ? "available" : "missing",
      detail: hasMetrics
        ? "Storage/utilization destinations, capacity limits and CO2 acceptance specifications are linked."
        : "Needs a linked storage basin, oilfield, mineralization site, chemical/fuel market, hub or port with CO2 acceptance specifications.",
    },
    {
      label: "5. Transport route and cost",
      status: hasMetrics ? "available" : "missing",
      detail: hasMetrics
        ? "Source-sink distance, transport mode and route-cost assumptions are evaluated."
        : "Needs a source-to-destination route, distance, transport mode and scale-adjusted cost/emissions calculation.",
    },
    {
      label: "6. Market and policy parameters",
      status: hasMetrics ? "available" : (hasCeads ? "partial" : "missing"),
      detail: hasMetrics
        ? "Product price/capacity, carbon price, carbon tax and credit assumptions are available."
        : (hasCeads
          ? "City emissions are available, but product-market, policy-credit and pathway-capacity parameters are not linked."
          : "Needs product market size/prices and carbon-policy assumptions before profitability can be evaluated."),
    },
  ];
}

function renderNoDataDetails(feature) {
  if (!feature) return;
  const props = feature.properties || {};
  const hasEmissions = hasNumber(props.ceads_latest_emissions);
  const chainSteps = props.chain_steps?.length ? props.chain_steps : inferChainSteps(props);
  const missingLabels = props.missing_chain_labels?.length
    ? props.missing_chain_labels
    : chainSteps.filter((step) => step.status === "missing").map((step) => step.label);
  el.cityTitle.textContent = featureDisplayName(feature);
  el.cityBadges.innerHTML = [
    badge("No pathway result", "warn"),
    badge(props.data_status === "emissions_only" ? "CEADs emissions only" : "boundary only", "warn"),
    badge(hasEmissions ? `${fmt(props.ceads_latest_emissions, 0)} Mt CEADs` : "no CEADs history", hasEmissions ? "ok" : "warn"),
  ].join("");
  el.recommendation.innerHTML = `
    <div class="metric-grid">
      <div class="metric"><strong>${props.data_status === "emissions_only" ? "Emissions-only" : "No matched data"}</strong><span>current map status</span></div>
      <div class="metric"><strong>${hasEmissions ? fmt(props.ceads_latest_emissions, 1) : "n/a"}</strong><span>latest CEADs MtCO2</span></div>
      <div class="metric"><strong>${props.ceads_latest_year || "n/a"}</strong><span>CEADs latest year</span></div>
      <div class="metric"><strong>${fmt(props.screened_source_count || 0)}</strong><span>screened point sources</span></div>
      <div class="metric"><strong>${hasNumber(props.ceads_peak_emissions) ? fmt(props.ceads_peak_emissions, 1) : "n/a"}</strong><span>CEADs peak MtCO2</span></div>
      <div class="metric"><strong>${fmt(hasNumber(props.missing_chain_count) ? props.missing_chain_count : missingLabels.length)}</strong><span>missing chain nodes</span></div>
    </div>
    <p class="logic">${props.data_status_label || "This prefecture has a boundary polygon but no city-level pathway result in the current screened source-sink model."}</p>
    <p class="logic">Interpretation: this does not mean the city has no CO2 emissions. It means the current public map has not linked it to every source-capture-destination-transport-market node required for a pathway recommendation.</p>
    ${renderChainList(chainSteps)}
  `;
  el.timelineChart.innerHTML = `<p class="logic">No model profitability timeline is available for this prefecture yet.</p>`;
  el.allocationPanel.innerHTML = `<p class="logic">No 2060 LP route is allocated from this prefecture in the current screened model.</p>`;
  el.uncertaintyPanel.innerHTML = `
    <p class="logic">${hasEmissions ? `The latest matched CEADs city emissions are ${fmt(props.ceads_latest_emissions, 1)} MtCO2 in ${props.ceads_latest_year || "the latest matched year"}.` : "No matched CEADs city emissions are available in the current crosswalk; this is missing data, not zero emissions."}</p>
    <p class="logic">Priority data gaps: ${missingLabels.length ? missingLabels.join("; ") : "none"}.</p>
  `;
  el.stressPanel.innerHTML = "";
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
  const sortedFeatures = state.boundaries.features
    .slice()
    .sort((a, b) => featureDisplayName(a).localeCompare(featureDisplayName(b), "en-US"));
  el.cityList.innerHTML = sortedFeatures
    .map((feature) => `<option value="${featureDisplayName(feature)}"></option>`)
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
    const feature = state.boundaries.features.find((item) => featureDisplayName(item) === value || item.properties.city_id === value);
    if (feature) selectCity(feature.properties.city_id);
  });
}

async function loadData() {
  const [localBoundaries, boundaryOverlay, cdnBoundaries, cities, routes, support, summary] = await Promise.all([
    fetchJsonOrNull(dataPath("data/city_boundaries.geojson")),
    fetchJsonOrNull(dataPath("data/city_overlay.json")),
    fetchJsonOrNull(BOUNDARY_CDN_URL),
    fetch(dataPath("data/city_metrics.json")).then((response) => response.json()),
    fetch(dataPath("data/route_links.json")).then((response) => response.json()),
    fetch(dataPath("data/supporting_tables.json")).then((response) => response.json()),
    fetch(dataPath("data/summary.json")).then((response) => response.json()),
  ]);
  const boundarySource = cdnBoundaries?.features?.length >= 300 ? cdnBoundaries : localBoundaries;
  state.boundaries = mergeBoundaryOverlay(boundarySource, boundaryOverlay);
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
