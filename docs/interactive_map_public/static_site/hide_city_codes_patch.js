(function () {
  let cityNamesById = {};

  function text(value) {
    return value === null || value === undefined ? "" : String(value).trim();
  }

  function isCodeText(value) {
    return /^\d{6}$/.test(text(value)) || /^City\s+\d{6}$/i.test(text(value));
  }

  function stripCodeSuffix(value) {
    return text(value).replace(/\s*\(\d{6}\)\s*$/g, "").trim();
  }

  function knownName(id) {
    const key = text(id);
    return key ? cityNamesById[key] || "" : "";
  }

  function cleanName(value, fallback, id) {
    const known = knownName(id);
    if (known) return known;
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
      props.city_name || props.name,
      props.city_id
    );
  }

  function cityName(city) {
    return cleanName(
      city?.display_name_en || city?.city_name_en || city?.display_name || city?.city_name,
      city?.city_name || city?.display_name,
      city?.city_id
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
      return cleanName(baseDisplayName(city), cityName(city), city?.city_id);
    };
  }

  if (typeof featureDisplayName === "function") {
    const baseFeatureDisplayName = featureDisplayName;
    featureDisplayName = function patchedFeatureDisplayName(feature) {
      return cleanName(baseFeatureDisplayName(feature), featureName(feature), feature?.properties?.city_id);
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
    const selectedId = typeof state === "undefined" ? "" : state.selectedCityId;
    const cleaned = cleanName(el.cityTitle.textContent, preferred, selectedId);
    if (el.cityTitle.textContent !== cleaned) el.cityTitle.textContent = cleaned;
  }

  function applyKnownNames() {
    if (!Object.keys(cityNamesById).length || typeof state === "undefined") return;
    if (state.boundaries?.features?.length) {
      for (const feature of state.boundaries.features) {
        const props = feature.properties || {};
        const name = knownName(props.city_id);
        if (!name) continue;
        props.city_name = name;
        props.city_name_en = name;
      }
    }
    if (state.cities) {
      for (const [id, city] of Object.entries(state.cities)) {
        const name = knownName(city?.city_id || id);
        if (!name) continue;
        city.city_name = name;
        city.city_name_en = name;
        city.display_name = name;
        city.display_name_en = name;
      }
    }
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
    applyKnownNames();
    wrapRenderDetails();
    cleanTitle();
    rebuildSearchList();
  }

  fetch("./data/city_names_en.json")
    .then((response) => response.ok ? response.json() : {})
    .then((names) => {
      cityNamesById = names || {};
      cleanNow();
    })
    .catch(() => {});

  [0, 250, 750, 1500, 3000, 6000].forEach((delay) => window.setTimeout(cleanNow, delay));
  document.addEventListener("click", () => window.setTimeout(cleanNow, 0), true);
  document.addEventListener("change", () => window.setTimeout(cleanNow, 0), true);
  document.addEventListener("DOMContentLoaded", cleanNow);
})();
