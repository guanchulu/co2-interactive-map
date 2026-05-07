(function () {
  function text(value) {
    return value === null || value === undefined ? "" : String(value).trim();
  }

  function isCodeText(value) {
    return /^\d{6}$/.test(text(value)) || /^City\s+\d{6}$/i.test(text(value));
  }

  function stripCodeSuffix(value) {
    return text(value).replace(/\s*\(\d{6}\)\s*$/g, "").trim();
  }

  function cleanName(value, fallback) {
    const stripped = stripCodeSuffix(value);
    if (stripped && !isCodeText(stripped)) return stripped;
    const fallbackText = stripCodeSuffix(fallback);
    if (fallbackText && !isCodeText(fallbackText)) return fallbackText;
    return "Unnamed city";
  }

  function featureName(feature) {
    const props = feature?.properties || {};
    return cleanName(
      props.city_name_en || props.city_name || props.name,
      props.city_name || props.name
    );
  }

  function cityName(city) {
    return cleanName(
      city?.display_name_en || city?.city_name_en || city?.display_name || city?.city_name,
      city?.city_name || city?.display_name
    );
  }

  function escapeHtml(value) {
    return text(value)
      .replace(/&/g, "&amp;")
      .replace(/"/g, "&quot;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  if (typeof displayName === "function") {
    const baseDisplayName = displayName;
    displayName = function patchedDisplayName(city) {
      return cleanName(baseDisplayName(city), cityName(city));
    };
  }

  if (typeof featureDisplayName === "function") {
    const baseFeatureDisplayName = featureDisplayName;
    featureDisplayName = function patchedFeatureDisplayName(feature) {
      return cleanName(baseFeatureDisplayName(feature), featureName(feature));
    };
  }

  function selectedFeature() {
    if (typeof state === "undefined" || !state.boundaries || !state.selectedCityId) return null;
    return state.boundaries.features.find((feature) => feature.properties?.city_id === state.selectedCityId) || null;
  }

  function selectedCity() {
    if (typeof state === "undefined" || !state.cities || !state.selectedCityId) return null;
    return state.cities[state.selectedCityId] || null;
  }

  function cleanTitle() {
    if (typeof el === "undefined" || !el.cityTitle) return;
    const city = selectedCity();
    const feature = selectedFeature();
    const preferred = city ? cityName(city) : (feature ? featureName(feature) : "");
    const cleaned = cleanName(el.cityTitle.textContent, preferred);
    if (el.cityTitle.textContent !== cleaned) el.cityTitle.textContent = cleaned;
  }

  function rebuildSearchList() {
    if (typeof el === "undefined" || !el.cityList) return;
    if (el.citySearch) el.citySearch.placeholder = "city name";
    const names = new Set();
    if (typeof state !== "undefined" && state.boundaries?.features?.length) {
      for (const feature of state.boundaries.features) names.add(featureDisplayName(feature));
    } else if (typeof state !== "undefined" && state.cities) {
      for (const city of Object.values(state.cities)) names.add(displayName(city));
    }
    const options = Array.from(names)
      .map((name) => cleanName(name))
      .filter((name) => name && name !== "Unnamed city")
      .sort((a, b) => a.localeCompare(b, "en-US"))
      .map((name) => `<option value="${escapeHtml(name)}"></option>`)
      .join("");
    if (options) el.cityList.innerHTML = options;
  }

  let wrappedRenderDetails = null;

  function wrapRenderDetails() {
    if (typeof renderDetails !== "function") return;
    if (renderDetails === wrappedRenderDetails || renderDetails.__hideCityCodesPatched) return;
    const baseRenderDetails = renderDetails;
    const patched = function patchedRenderDetails() {
      const result = baseRenderDetails.apply(this, arguments);
      cleanNow();
      return result;
    };
    patched.__hideCityCodesPatched = true;
    renderDetails = patched;
    wrappedRenderDetails = patched;
  }

  function cleanNow() {
    wrapRenderDetails();
    cleanTitle();
    rebuildSearchList();
  }

  [0, 250, 750, 1500, 3000, 6000].forEach((delay) => window.setTimeout(cleanNow, delay));
  document.addEventListener("click", () => window.setTimeout(cleanNow, 0), true);
  document.addEventListener("change", () => window.setTimeout(cleanNow, 0), true);
  document.addEventListener("DOMContentLoaded", cleanNow);
})();
