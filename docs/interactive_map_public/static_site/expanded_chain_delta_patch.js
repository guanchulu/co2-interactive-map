(function () {
  const DELTA_URL = "./data/expanded_chain_delta.json";
  const SUMMARY_URL = "./data/expanded_chain_summary.json";

  function statusLabel(status) {
    if (status === "model_result") return "Full pathway chain is available in the current optimized model.";
    if (status === "lower_threshold_screen") return "Lower-threshold industrial point sources are available; this is a screening chain, not a full LP optimum.";
    if (status === "tier2_priority_dac") return "Priority city with a DAC fallback chain; base economics remain negative without stronger durable-removal credit.";
    if (status === "emissions_only") return "City emissions are available, but the full source-capture-destination-transport-market chain is incomplete.";
    return "Boundary available; no CO2 pathway or CEADs record is linked yet.";
  }

  function applyDelta(props, delta) {
    if (!Array.isArray(delta)) return;
    const status = {0:"boundary_only",1:"emissions_only",2:"model_result",3:"lower_threshold_screen",4:"tier2_priority_dac"}[delta[0]] || props.data_status;
    props.data_status = status;
    props.data_status_label = statusLabel(status);
    props.lower_threshold_source_count = delta[1] || 0;
    props.lower_threshold_available_mtco2 = delta[2] || 0;
    props.micro_source_count = delta[3] || 0;
    props.micro_available_mtco2 = delta[4] || 0;
    props.tier2_priority_city = Boolean(delta[5]);
    props.dac_fallback_available = Boolean(delta[6]);
    props.screening_threshold_gross_mtco2 = 0.25;
    if (props.dac_fallback_available) {
      props.dac_cost_2060_usd_t = 285;
      props.dac_policy_credit_2060_usd_t = 180;
      props.dac_margin_2060_usd_t = -105;
      props.dac_required_credit_2060_usd_t = 285;
      props.dac_module_mtco2_per_year = 0.5;
    }
  }

  function waitReady() {
    return new Promise((resolve) => {
      const timer = setInterval(() => {
        if (typeof state !== "undefined" && state.boundaries && typeof renderMap === "function") {
          clearInterval(timer);
          resolve();
        }
      }, 100);
    });
  }

  async function run() {
    await waitReady();
    const [delta, summary] = await Promise.all([
      fetch(DELTA_URL).then((r) => r.ok ? r.json() : null).catch(() => null),
      fetch(SUMMARY_URL).then((r) => r.ok ? r.json() : null).catch(() => null),
    ]);
    const byId = delta?.cities || {};
    for (const feature of state.boundaries.features || []) {
      applyDelta(feature.properties || {}, byId[feature.properties?.city_id]);
    }
    state.expandedChainSummary = summary || delta?.screening_assumptions || state.expandedChainSummary || {};
    if (typeof renderStats === "function") renderStats();
    if (typeof renderMap === "function") renderMap();
    if (typeof renderDetails === "function") renderDetails();
  }

  run().catch((error) => console.warn("Expanded chain delta did not load:", error));
})();