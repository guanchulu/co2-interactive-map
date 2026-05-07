(function(){
  function pickRequestedCity(){
    if (typeof state === "undefined" || !state.boundaries || typeof renderDetails === "undefined") {
      window.setTimeout(pickRequestedCity, 150);
      return;
    }
    const cityId = new URLSearchParams(window.location.search).get("city");
    if (!cityId) return;
    const exists = state.boundaries.features.some((feature) => feature.properties && feature.properties.city_id === cityId);
    if (!exists) return;
    state.selectedCityId = cityId;
    renderRoutes();
    renderSelectedOutline();
    renderDetails();
  }
  window.setTimeout(pickRequestedCity, 1200);
})();
