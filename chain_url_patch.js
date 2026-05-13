(function(){
  let tries = 0;
  function pickRequestedCity(){
    const cityId = new URLSearchParams(window.location.search).get("city");
    if (!cityId) return;
    if (typeof state === "undefined" || !state.boundaries || typeof renderDetails === "undefined") {
      window.setTimeout(pickRequestedCity, 150);
      return;
    }
    const exists = state.boundaries.features.some((feature) => feature.properties && feature.properties.city_id === cityId);
    if (!exists && tries++ < 60) {
      window.setTimeout(pickRequestedCity, 250);
      return;
    }
    if (!exists) return;
    state.selectedCityId = cityId;
    renderRoutes();
    renderSelectedOutline();
    renderDetails();
  }
  window.setTimeout(pickRequestedCity, 500);
})();
