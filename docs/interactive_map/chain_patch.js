(function () {
  const BOUNDARY_URL = "./data/city_boundaries.geojson";
  const OVERLAY_URL = "./data/city_overlay.json";
  const DELTA_URL = "./data/expanded_chain_delta.json";
  const SUMMARY_URL = "./data/expanded_chain_summary.json";

  function css() {
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

  function has(value) {
    return value !== null && value !== undefined && !Number.isNaN(Number(value));
  }

  function cityId(value) {
    if (value === null || value === undefined) return "";
    const text = String(value).trim();
    return text.length === 6 ? text : text.padStart(6, "0");
  }

  function featureId(feature) {
    const props = feature.properties || {};
    return cityId(props.city_id || props.id || props.adcode || props["\u533a\u5212\u7801"] || "");
  }

  function label(status) {
    if (status === "model_result") return "Full pathway chain is available in the current optimized model.";
    if (status === "lower_threshold_screen") return "Lower-threshold industrial point sources are available; this is a screening chain, not a full LP optimum.";
    if (status === "tier2_priority_dac") return "Priority city with a DAC fallback chain; base economics remain negative without stronger durable-removal credit.";
    if (status === "emissions_only") return "City emissions are available, but the full source-capture-destination-transport-market chain is incomplete.";
    return "Boundary available; no CO2 pathway or CEADs record is linked yet.";
  }

  function expand(record) {
    if (Array.isArray(record)) {
      const status = {0:"boundary_only",1:"emissions_only",2:"model_result",3:"lower_threshold_screen",4:"tier2_priority_dac"}[record[6]]
        || (record[4] ? "model_result" : (has(record[0]) ? "emissions_only" : "boundary_only"));
      return {
        ceads_latest_emissions: record[0],
        ceads_latest_year: record[1],
        ceads_peak_emissions: record[2],
        ceads_peak_year: record[3],
        screened: Boolean(record[4]),
        screened_source_count: record[5] || 0,
        data_status: status,
        data_status_label: label(status),
        lower_threshold_source_count: record[7] || 0,
        lower_threshold_available_mtco2: record[8] || 0,
        micro_source_count: record[9] || 0,
        micro_available_mtco2: record[10] || 0,
        tier2_priority_city: Boolean(record[11]),
        dac_fallback_available: Boolean(record[12]),
        dac_cost_2060_usd_t: record[13],
        dac_policy_credit_2060_usd_t: record[14],
        dac_margin_2060_usd_t: record[15],
        dac_required_credit_2060_usd_t: record[16],
        dac_module_mtco2_per_year: record[17],
        screening_threshold_gross_mtco2: 0.25,
      };
    }
    if (!record) return {};
    const status = record.data_status || (record.screened ? "model_result" : (has(record.ceads_latest_emissions) ? "emissions_only" : "boundary_only"));
    return {...record, data_status: status, data_status_label: record.data_status_label || label(status)};
  }

  function applyDelta(extra, delta) {
    if (!Array.isArray(delta)) return extra;
    const status = {0:"boundary_only",1:"emissions_only",2:"model_result",3:"lower_threshold_screen",4:"tier2_priority_dac"}[delta[0]] || extra.data_status;
    return {
      ...extra,
      data_status: status,
      data_status_label: label(status),
      lower_threshold_source_count: delta[1] || 0,
      lower_threshold_available_mtco2: delta[2] || 0,
      micro_source_count: delta[3] || 0,
      micro_available_mtco2: delta[4] || 0,
      tier2_priority_city: Boolean(delta[5]),
      dac_fallback_available: Boolean(delta[6]),
      dac_cost_2060_usd_t: delta[6] ? 285 : extra.dac_cost_2060_usd_t,
      dac_policy_credit_2060_usd_t: delta[6] ? 180 : extra.dac_policy_credit_2060_usd_t,
      dac_margin_2060_usd_t: delta[6] ? -105 : extra.dac_margin_2060_usd_t,
      dac_required_credit_2060_usd_t: delta[6] ? 285 : extra.dac_required_credit_2060_usd_t,
      dac_module_mtco2_per_year: delta[6] ? 0.5 : extra.dac_module_mtco2_per_year,
      screening_threshold_gross_mtco2: 0.25,
    };
  }

  function merge(boundaries, overlay, deltaPayload) {
    const byId = overlay?.cities || overlay || {};
    const deltaById = deltaPayload?.cities || {};
    return {
      type: "FeatureCollection",
      features: (boundaries?.features || []).map((feature) => {
        const id = featureId(feature);
        const props = feature.properties || {};
        const extra = applyDelta(expand(byId[id]), deltaById[id]);
        const name = extra.city_name_en || extra.city_name || props.city_name_en || props.city_name || "Boundary city";
        return {
          ...feature,
          properties: {
            ...props,
            ...extra,
            city_id: id,
            city_name: name,
            city_name_en: name,
            screened: Boolean(extra.screened),
            data_status: extra.data_status || "boundary_only",
            data_status_label: extra.data_status_label || label(extra.data_status),
          },
        };
      }),
    };
  }

  function getFeature(id) {
    return state.boundaries.features.find((feature) => feature.properties.city_id === id) || null;
  }

  function steps(props) {
    const model = props.screened || props.data_status === "model_result";
    const emissions = has(props.ceads_latest_emissions);
    const fullCount = Number(props.screened_source_count || 0);
    const lowerCount = Number(props.lower_threshold_source_count || 0);
    const microCount = Number(props.micro_source_count || 0);
    const dac = Boolean(props.dac_fallback_available);
    const lower = lowerCount > 0;
    return [
      ["1. City boundary", "available", "Prefecture polygon is available and drawn on the map."],
      ["2. Industrial source or DAC fallback", model || lower ? "available" : (dac || microCount ? "partial" : "missing"), model ? `${Math.max(fullCount, 1)} full-model point-source package is linked.` : (lower ? `${lowerCount} lower-threshold point source(s) >= ${fmt(props.screening_threshold_gross_mtco2 || 0.25, 2)} MtCO2/yr gross emissions are linked.` : (dac ? "DAC fallback is assigned because no qualifying industrial chain is available." : "No qualifying industrial point source is joined in the current public source package."))],
      ["3. Capture cost, energy, purity and pressure", model || dac ? "available" : (lower ? "partial" : "missing"), model ? "Source-specific capture assumptions are assigned." : (dac ? `DAC cost screen is ${fmt(props.dac_cost_2060_usd_t, 0)} USD/tCO2 in 2060.` : "Needs source-specific capture cost, energy, CO2 purity, pressure and impurity assumptions.")],
      ["4. Destination and CO2 specification", model ? "available" : (lower || dac ? "partial" : "missing"), model ? "Storage/utilization destinations and CO2 specifications are linked." : (lower || dac ? "Screening destination/hub logic is assigned; route engineering still needs audit." : "Needs a linked storage basin, oilfield, mineralization site, chemical/fuel market, hub or port.")],
      ["5. Transport route and cost", model ? "available" : (lower || dac ? "partial" : "missing"), model ? "Source-sink route and transport-cost assumptions are evaluated." : (lower || dac ? "Generic city-to-hub transport/MRV assumptions are assigned for screening." : "Needs route, distance, mode and scale-adjusted transport cost/emissions.")],
      ["6. Market and policy parameters", model ? "available" : (emissions || dac ? "partial" : "missing"), model ? "Product price/capacity and policy assumptions are available." : (dac ? `DAC remains negative in base case; break-even credit is about ${fmt(props.dac_required_credit_2060_usd_t, 0)} USD/tCO2.` : "Market and policy values are screening assumptions and require local validation.")],
    ].map(([name, status, detail]) => ({name, status, detail}));
  }

  function chainHtml(items) {
    return `<div class="chain-list">${items.map((item) => `
      <div class="chain-row ${item.status}"><span class="chain-dot"></span><div><strong>${item.name}</strong><em>${item.status}</em><p>${item.detail}</p></div></div>
    `).join("")}</div>`;
  }

  function renderScreening(feature) {
    const props = feature.properties || {};
    const items = steps(props);
    const missing = items.filter((item) => item.status === "missing").map((item) => item.name);
    const lowerCount = Number(props.lower_threshold_source_count || 0);
    const lowerMt = Number(props.lower_threshold_available_mtco2 || 0);
    const dac = Boolean(props.dac_fallback_available);
    const emissions = has(props.ceads_latest_emissions);
    el.cityTitle.textContent = featureDisplayName(feature);
    el.cityBadges.innerHTML = [
      badge(props.data_status === "lower_threshold_screen" ? "Lower-threshold chain" : (props.data_status === "tier2_priority_dac" ? "DAC fallback chain" : "No LP pathway result"), props.data_status === "lower_threshold_screen" ? "ok" : "warn"),
      badge(props.tier2_priority_city ? "priority city" : "screening city", props.tier2_priority_city ? "ok" : "warn"),
      badge(emissions ? `${fmt(props.ceads_latest_emissions, 0)} Mt CEADs` : "no CEADs history", emissions ? "ok" : "warn"),
      dac ? badge(`DAC ${fmt(props.dac_margin_2060_usd_t, 0)} USD/t`, "neg") : "",
    ].join("");
    el.recommendation.innerHTML = `
      <div class="metric-grid">
        <div class="metric"><strong>${props.data_status === "lower_threshold_screen" ? "Screening chain" : (dac ? "DAC fallback" : "No matched data")}</strong><span>current map status</span></div>
        <div class="metric"><strong>${emissions ? fmt(props.ceads_latest_emissions, 1) : "n/a"}</strong><span>latest CEADs MtCO2</span></div>
        <div class="metric"><strong>${fmt(lowerCount)}</strong><span>point sources >= ${fmt(props.screening_threshold_gross_mtco2 || 0.25, 2)} Mt/yr</span></div>
        <div class="metric"><strong>${fmt(lowerMt, 1)}</strong><span>capturable MtCO2/yr screen</span></div>
        <div class="metric"><strong>${has(props.ceads_peak_emissions) ? fmt(props.ceads_peak_emissions, 1) : "n/a"}</strong><span>CEADs peak MtCO2</span></div>
        <div class="metric"><strong>${dac ? fmt(props.dac_required_credit_2060_usd_t, 0) : "n/a"}</strong><span>DAC break-even credit USD/t</span></div>
      </div>
      <p class="logic">${props.data_status_label || label(props.data_status)}</p>
      <p class="logic">This separates optimized full-chain results from lower-threshold screening and DAC fallback chains.</p>
      ${chainHtml(items)}
    `;
    el.timelineChart.innerHTML = dac
      ? `<div class="metric-grid"><div class="metric"><strong>${fmt(props.dac_cost_2060_usd_t, 0)}</strong><span>DAC 2060 cost USD/tCO2</span></div><div class="metric"><strong>${fmt(props.dac_policy_credit_2060_usd_t, 0)}</strong><span>base credit USD/tCO2</span></div><div class="metric"><strong>${fmt(props.dac_margin_2060_usd_t, 0)}</strong><span>DAC margin USD/tCO2</span></div><div class="metric"><strong>${fmt(props.dac_module_mtco2_per_year, 1)}</strong><span>fallback module Mt/yr</span></div></div><p class="logic">DAC is included for completeness, not because it is profitable in the base case.</p>`
      : `<p class="logic">No model profitability timeline is available for this prefecture yet.</p>`;
    el.allocationPanel.innerHTML = lowerCount
      ? `<p class="logic">The lowered threshold adds ${fmt(lowerCount)} point source(s) and ${fmt(lowerMt, 1)} MtCO2/yr of screening capture potential. This has not yet been re-optimized as a national LP route.</p>`
      : `<p class="logic">No 2060 LP route is allocated from this prefecture in the current screened model.</p>`;
    el.uncertaintyPanel.innerHTML = `<p class="logic">${emissions ? `Latest matched CEADs emissions are ${fmt(props.ceads_latest_emissions, 1)} MtCO2 in ${props.ceads_latest_year}.` : "No matched CEADs city emissions are available; this is missing data, not zero emissions."}</p><p class="logic">Priority data gaps: ${missing.length ? missing.join("; ") : "none"}.</p>`;
    el.stressPanel.innerHTML = "";
  }

  function appendExtension(feature) {
    const props = feature?.properties || {};
    const count = Number(props.lower_threshold_source_count || 0);
    const mt = Number(props.lower_threshold_available_mtco2 || 0);
    const dac = Boolean(props.dac_fallback_available);
    if (!count && !dac) return;
    el.cityBadges.innerHTML += [
      count ? badge(`${fmt(count)} lower-threshold sources`, "ok") : "",
      dac ? badge(`DAC fallback ${fmt(props.dac_margin_2060_usd_t, 0)} USD/t`, "neg") : "",
    ].join("");
    el.recommendation.innerHTML += `<p class="logic"><strong>Screening extension:</strong> the expanded map adds ${fmt(count)} point source(s) above ${fmt(props.screening_threshold_gross_mtco2 || 0.25, 2)} MtCO2/yr and ${fmt(mt, 1)} MtCO2/yr of capturable screening potential. ${dac ? `A DAC fallback module is also carried at ${fmt(props.dac_cost_2060_usd_t, 0)} USD/tCO2 cost and ${fmt(props.dac_margin_2060_usd_t, 0)} USD/tCO2 base-case margin.` : ""}</p>`;
  }

  function patchFunctions() {
    const baseRender = renderDetails;
    const baseFill = featureFill;
    const baseTooltip = showTooltip;
    renderStats = function () {
      const s = state.summary || {};
      const x = state.expandedChainSummary || {};
      el.statsStrip.innerHTML = [
        [`${fmt(s.prefecture_boundary_count || state.boundaries.features.length)}`, "prefecture boundaries"],
        [`${fmt(s.city_count || Object.keys(state.cities).length)}`, "full pathway cities"],
        [`${fmt(x.lower_threshold_city_count || 0)}`, "lower-threshold cities"],
        [`${fmt(x.tier2_priority_city_count || 0)}`, "priority cities"],
        [`${fmt(x.dac_fallback_city_count || 0)}`, "DAC fallback cities"],
        [`${fmt(s.managed_mtco2_2060, 1)} Mt`, "managed CO2 in LP"],
        [`${fmt(s.profit_busd_2060, 1)} BUSD`, "2060 profit pool"],
      ].map(([value, name]) => `<div class="stat"><strong>${value}</strong><span>${name}</span></div>`).join("");
    };
    featureFill = function (feature) {
      if (state.layer === "ceads") return ceadsColor(feature.properties.ceads_latest_emissions);
      if (!cityForFeature(feature)) {
        if (feature.properties.data_status === "lower_threshold_screen") return "#f3c86d";
        if (feature.properties.data_status === "tier2_priority_dac") return "#b9d7ea";
        if (feature.properties.dac_fallback_available) return "#d7e8f2";
      }
      return baseFill(feature);
    };
    selectCity = function (id) {
      if (!state.cities[id] && !getFeature(id)) return;
      state.selectedCityId = id;
      renderRoutes();
      renderSelectedOutline();
      renderDetails();
    };
    renderDetails = function () {
      const city = state.cities[state.selectedCityId];
      const feature = getFeature(state.selectedCityId);
      if (city) {
        baseRender();
        appendExtension(feature);
      } else if (feature) {
        renderScreening(feature);
      }
    };
    showTooltip = function (event, feature) {
      const city = cityForFeature(feature);
      if (city) return baseTooltip(event, feature);
      const props = feature.properties || {};
      el.tooltip.hidden = false;
      el.tooltip.style.left = `${event.clientX + 14}px`;
      el.tooltip.style.top = `${event.clientY + 14}px`;
      el.tooltip.innerHTML = `<strong>${featureDisplayName(feature)}</strong><br>${props.data_status_label || "No model result"}<br>CEADs latest: ${has(props.ceads_latest_emissions) ? `${fmt(props.ceads_latest_emissions, 1)} MtCO2` : "n/a"}<br>Lower-threshold sources: ${fmt(props.lower_threshold_source_count || 0)}`;
    };
  }

  function refreshSearch() {
    const sorted = state.boundaries.features.slice().sort((a, b) => featureDisplayName(a).localeCompare(featureDisplayName(b), "en-US"));
    el.cityList.innerHTML = sorted.map((feature) => `<option value="${featureDisplayName(feature)}"></option>`).join("");
    el.citySearch.addEventListener("change", () => {
      const value = el.citySearch.value.trim();
      const feature = state.boundaries.features.find((item) => featureDisplayName(item) === value || item.properties.city_id === value);
      if (feature) selectCity(feature.properties.city_id);
    });
  }

  function waitBase() {
    return new Promise((resolve) => {
      const timer = setInterval(() => {
        if (typeof state !== "undefined" && state.boundaries && state.cities) {
          clearInterval(timer);
          resolve();
        }
      }, 100);
    });
  }

  async function run() {
    css();
    await waitBase();
    const [boundaries, overlay, delta, summary] = await Promise.all([
      fetch(BOUNDARY_URL).then((r) => r.json()),
      fetch(OVERLAY_URL).then((r) => r.json()),
      fetch(DELTA_URL).then((r) => r.ok ? r.json() : null).catch(() => null),
      fetch(SUMMARY_URL).then((r) => r.ok ? r.json() : null).catch(() => null),
    ]);
    state.boundaries = merge(boundaries, overlay, delta);
    state.expandedChainSummary = summary || delta?.screening_assumptions || overlay.screening_assumptions || {};
    patchFunctions();
    refreshSearch();
    const requested = new URLSearchParams(window.location.search).get("city");
    if (requested && getFeature(requested)) state.selectedCityId = requested;
    renderStats();
    renderMap();
    renderDetails();
  }

  run().catch((error) => console.warn("City-chain patch did not load:", error));
})();
