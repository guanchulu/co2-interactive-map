(function () {
  const BOUNDARY_CDN_URL = "https://cdn.jsdelivr.net/npm/cn-atlas@0.1.2/prefectures.json";

  function injectChainStyles() {
    const style = document.createElement("style");
    style.textContent = `
      .chain-list{display:grid;gap:8px;margin-top:10px}
      .chain-row{display:grid;grid-template-columns:14px minmax(0,1fr);gap:9px;align-items:start;border:1px solid var(--line);border-radius:8px;padding:9px;background:#fff}
      .chain-dot{width:10px;height:10px;margin-top:4px;border-radius:50%;background:var(--rose)}
      .chain-row.available .chain-dot{background:var(--green)}
      .chain-row.partial .chain-dot{background:var(--amber)}
      .chain-row strong{display:block;font-size:12px}
      .chain-row em{display:inline-block;margin-top:3px;color:var(--muted);font-size:10px;font-style:normal;font-weight:800;text-transform:uppercase}
      .chain-row p{margin:5px 0 0;color:var(--muted);font-size:11px;line-height:1.35}
    `;
    document.head.appendChild(style);
  }

  function hasValue(value) {
    return value !== null && value !== undefined && !Number.isNaN(Number(value));
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

  function statusLabel(status) {
    if (status === "model_result") return "Full pathway chain is available in the current screened model.";
    if (status === "emissions_only") return "City emissions are available, but the full source-capture-destination-transport-market chain is incomplete.";
    return "Boundary available; no CO2 pathway or CEADs record is linked yet.";
  }

  function expandOverlay(record) {
    if (Array.isArray(record)) {
      const latest = record[0];
      const screened = Boolean(record[4]);
      const status = screened ? "model_result" : (hasValue(latest) ? "emissions_only" : "boundary_only");
      return {
        screened,
        data_status: status,
        data_status_label: statusLabel(status),
        screened_source_count: record[5] || 0,
        ceads_latest_emissions: latest,
        ceads_latest_year: record[1],
        ceads_peak_emissions: record[2],
        ceads_peak_year: record[3],
      };
    }
    return record || {};
  }

  function mergeBoundaries(boundaries, overlay) {
    const overlayById = overlay?.cities || overlay || {};
    return {
      type: "FeatureCollection",
      features: (boundaries?.features || []).map((feature) => {
        const cityId = boundaryFeatureId(feature);
        const props = feature.properties || {};
        const extra = expandOverlay(overlayById[cityId]);
        const fallbackName = props.name && !/[\u3400-\u9fff]/.test(String(props.name)) ? props.name : `City ${cityId || "unknown"}`;
        const status = extra.data_status || "boundary_only";
        return {
          ...feature,
          properties: {
            ...props,
            city_id: cityId,
            city_name: extra.city_name || fallbackName,
            city_name_en: extra.city_name_en || extra.city_name || fallbackName,
            screened: Boolean(extra.screened),
            data_status: status,
            data_status_label: extra.data_status_label || statusLabel(status),
            screened_source_count: extra.screened_source_count || 0,
            ceads_latest_emissions: extra.ceads_latest_emissions,
            ceads_latest_year: extra.ceads_latest_year,
            ceads_peak_emissions: extra.ceads_peak_emissions,
            ceads_peak_year: extra.ceads_peak_year,
          },
        };
      }),
    };
  }

  function getFeature(cityId) {
    return state.boundaries.features.find((feature) => feature.properties.city_id === cityId) || null;
  }

  function chainStatusLabel(status) {
    if (status === "available") return "available";
    if (status === "partial") return "partial";
    return "missing";
  }

  function inferChainSteps(props) {
    const hasModel = props.screened || props.data_status === "model_result";
    const hasCeads = hasValue(props.ceads_latest_emissions);
    const sourceCount = Number(props.screened_source_count || 0);
    return [
      ["1. City boundary", "available", "Prefecture polygon is available and drawn on the map."],
      ["2. Large industrial CO2 point source", hasModel || sourceCount > 0 ? "available" : "missing", hasModel || sourceCount > 0 ? `${Math.max(sourceCount, 1)} screened point-source package is linked.` : "No screened large industrial point source is joined to this prefecture in the current public source package."],
      ["3. Capture cost, energy, purity and pressure", hasModel ? "available" : "missing", hasModel ? "Capture cost, energy, purity, pressure and impurity assumptions are assigned." : "Needs source-specific capture cost, capture energy, CO2 purity, pressure and impurity assumptions."],
      ["4. Destination and CO2 specification", hasModel ? "available" : "missing", hasModel ? "Storage/utilization destinations, capacity limits and CO2 acceptance specifications are linked." : "Needs a linked storage basin, oilfield, mineralization site, chemical/fuel market, hub or port with CO2 acceptance specifications."],
      ["5. Transport route and cost", hasModel ? "available" : "missing", hasModel ? "Source-sink distance, transport mode and route-cost assumptions are evaluated." : "Needs a source-to-destination route, distance, transport mode and scale-adjusted cost/emissions calculation."],
      ["6. Market and policy parameters", hasModel ? "available" : (hasCeads ? "partial" : "missing"), hasModel ? "Product price/capacity, carbon price, carbon tax and credit assumptions are available." : (hasCeads ? "City emissions are available, but product-market, policy-credit and pathway-capacity parameters are not linked." : "Needs product market size/prices and carbon-policy assumptions before profitability can be evaluated.")],
    ].map(([label, status, detail]) => ({ label, status, detail }));
  }

  function renderChainList(steps) {
    return `<div class="chain-list">${steps.map((step) => `
      <div class="chain-row ${step.status}">
        <span class="chain-dot"></span>
        <div><strong>${step.label}</strong><em>${chainStatusLabel(step.status)}</em><p>${step.detail}</p></div>
      </div>`).join("")}</div>`;
  }

  function renderNoData(feature) {
    const props = feature.properties || {};
    const hasEmissions = hasValue(props.ceads_latest_emissions);
    const steps = inferChainSteps(props);
    const missing = steps.filter((step) => step.status === "missing").map((step) => step.label);
    el.cityTitle.textContent = `${featureDisplayName(feature)} (${props.city_id})`;
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
        <div class="metric"><strong>${hasValue(props.ceads_peak_emissions) ? fmt(props.ceads_peak_emissions, 1) : "n/a"}</strong><span>CEADs peak MtCO2</span></div>
        <div class="metric"><strong>${fmt(missing.length)}</strong><span>missing chain nodes</span></div>
      </div>
      <p class="logic">${props.data_status_label || statusLabel(props.data_status)}</p>
      <p class="logic">This does not mean the city has no CO2 emissions. It means the current public map has not linked it to every node required for a pathway recommendation.</p>
      ${renderChainList(steps)}
    `;
    el.timelineChart.innerHTML = `<p class="logic">No model profitability timeline is available for this prefecture yet.</p>`;
    el.allocationPanel.innerHTML = `<p class="logic">No 2060 LP route is allocated from this prefecture in the current screened model.</p>`;
    el.uncertaintyPanel.innerHTML = `
      <p class="logic">${hasEmissions ? `The latest matched CEADs city emissions are ${fmt(props.ceads_latest_emissions, 1)} MtCO2 in ${props.ceads_latest_year || "the latest matched year"}.` : "No matched CEADs city emissions are available in the current crosswalk; this is missing data, not zero emissions."}</p>
      <p class="logic">Priority data gaps: ${missing.length ? missing.join("; ") : "none"}.</p>
    `;
    el.stressPanel.innerHTML = "";
  }

  function refreshSearchList() {
    const sorted = state.boundaries.features.slice().sort((a, b) => featureDisplayName(a).localeCompare(featureDisplayName(b), "en-US"));
    el.cityList.innerHTML = sorted.map((feature) => `<option value="${featureDisplayName(feature)}">${feature.properties.city_id}</option><option value="${feature.properties.city_id}">${featureDisplayName(feature)}</option>`).join("");
    el.citySearch.addEventListener("change", () => {
      const value = el.citySearch.value.trim();
      const feature = state.boundaries.features.find((item) => featureDisplayName(item) === value || item.properties.city_id === value);
      if (feature) selectCity(feature.properties.city_id);
    });
  }

  function patchFunctions() {
    const baseRenderDetails = renderDetails;
    const baseFeatureFill = featureFill;
    const baseShowTooltip = showTooltip;
    renderStats = function patchedRenderStats() {
      const s = state.summary || {};
      el.statsStrip.innerHTML = [
        [`${fmt(s.prefecture_boundary_count || state.boundaries.features.length)}`, "prefecture boundaries"],
        [`${fmt(s.city_count || Object.keys(state.cities).length)}`, "full pathway cities"],
        [`${fmt(s.emissions_only_city_count || 0)}`, "emissions-only cities"],
        [`${fmt(s.boundary_only_city_count || 0)}`, "boundary-only cities"],
        [`${fmt(s.managed_mtco2_2060, 1)} Mt`, "managed CO2 in LP"],
        [`${fmt(s.profit_busd_2060, 1)} BUSD`, "2060 profit pool"],
      ].map(([value, label]) => `<div class="stat"><strong>${value}</strong><span>${label}</span></div>`).join("");
    };
    featureFill = function patchedFeatureFill(feature) {
      if (state.layer === "ceads") return ceadsColor(feature.properties.ceads_latest_emissions);
      return baseFeatureFill(feature);
    };
    selectCity = function patchedSelectCity(cityId) {
      if (!state.cities[cityId] && !getFeature(cityId)) return;
      state.selectedCityId = cityId;
      renderRoutes();
      renderSelectedOutline();
      renderDetails();
    };
    renderDetails = function patchedRenderDetails() {
      const city = state.cities[state.selectedCityId];
      if (city) return baseRenderDetails();
      const feature = getFeature(state.selectedCityId);
      if (feature) return renderNoData(feature);
    };
    showTooltip = function patchedShowTooltip(event, feature) {
      const city = cityForFeature(feature);
      if (city) return baseShowTooltip(event, feature);
      const props = feature.properties || {};
      el.tooltip.hidden = false;
      el.tooltip.style.left = `${event.clientX + 14}px`;
      el.tooltip.style.top = `${event.clientY + 14}px`;
      el.tooltip.innerHTML = `<strong>${featureDisplayName(feature)}</strong><br>${props.data_status_label || "No model result"}<br>CEADs latest: ${hasValue(props.ceads_latest_emissions) ? `${fmt(props.ceads_latest_emissions, 1)} MtCO2` : "n/a"}`;
    };
  }

  function waitForBaseData() {
    return new Promise((resolve) => {
      const timer = setInterval(() => {
        if (typeof state !== "undefined" && state.boundaries && state.cities) {
          clearInterval(timer);
          resolve();
        }
      }, 100);
    });
  }

  async function applyPatch() {
    injectChainStyles();
    await waitForBaseData();
    const [boundaries, overlay] = await Promise.all([
      fetch(BOUNDARY_CDN_URL).then((response) => response.json()),
      fetch("./data/city_overlay.json").then((response) => response.json()),
    ]);
    state.boundaries = mergeBoundaries(boundaries, overlay);
    patchFunctions();
    refreshSearchList();
    renderStats();
    renderMap();
    renderDetails();
  }

  applyPatch().catch((error) => {
    console.warn("City-chain patch did not load:", error);
  });
})();
