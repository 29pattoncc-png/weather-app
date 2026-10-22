const STORAGE_KEY = "weather-desk-saved-locations";

const searchForm = document.querySelector("#search-form");
const searchInput = document.querySelector("#place-search");
const statusMessage = document.querySelector("#status-message");
const weatherContent = document.querySelector("#weather-content");
const savedLocations = document.querySelector("#saved-locations");
const saveButton = document.querySelector("#save-location-button");

let activeLocation = null;
document.querySelector("#today-label").textContent = new Intl.DateTimeFormat(undefined, {
  weekday: "long",
  month: "long",
  day: "numeric",
}).format(new Date());

searchForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const zipCode = searchInput.value.trim();
  if (!/^\d{5}$/.test(zipCode)) {
    showMessage("Enter a valid 5-digit U.S. ZIP code.", true);
    return;
  }
  loadWeather(zipCode);
});

saveButton.addEventListener("click", () => {
  if (!activeLocation) return;
  const locations = getSavedLocations();
  const exists = locations.some((location) => location.zip === activeLocation.zip);
  if (exists) {
    showMessage("This location is already saved.");
    return;
  }
  locations.push(activeLocation);
  localStorage.setItem(STORAGE_KEY, JSON.stringify(locations));
  renderSavedLocations();
  updateSaveButton();
  showMessage("Location saved.");
});

function showMessage(text, isError = false) {
  statusMessage.textContent = text;
  statusMessage.classList.toggle("error", isError);
  statusMessage.hidden = false;
}

function hideMessage() {
  statusMessage.hidden = true;
  statusMessage.classList.remove("error");
}

async function requestJson(url) {
  let response;
  try {
    response = await fetch(url, { headers: { Accept: "application/json" } });
  } catch {
    throw new Error("Could not connect to the weather app server. Make sure it is running and try again.");
  }
  let data;
  try {
    data = await response.json();
  } catch {
    throw new Error("The server returned an unreadable response. Please try again.");
  }
  if (!response.ok) throw new Error(data.error || "The request failed. Please try again.");
  return data;
}

async function loadWeather(zipCode) {
  weatherContent.hidden = true;
  showMessage(`Loading forecast for ZIP code ${zipCode}…`);
  try {
    const data = await requestJson(`/api/weather?zip=${encodeURIComponent(zipCode)}`);
    activeLocation = {
      name: `${data.location.city}, ${data.location.state} (${data.location.zip})`,
      zip: data.location.zip,
    };
    renderWeather(data);
    hideMessage();
    weatherContent.hidden = false;
  } catch (error) {
    showMessage(error.message || "Weather information is currently unavailable. Please try again.", true);
  }
}

function getSavedLocations() {
  try {
    const data = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
    if (!Array.isArray(data)) return [];
    return data.filter((location) => (
      typeof location.name === "string"
      && typeof location.zip === "string" && /^\d{5}$/.test(location.zip)
    ));
  } catch {
    return [];
  }
}

function renderSavedLocations() {
  const locations = getSavedLocations();
  savedLocations.replaceChildren();
  for (const location of locations) {
    const chip = document.createElement("span");
    chip.className = "saved-chip";
    const open = document.createElement("button");
    open.type = "button";
    open.className = "saved-open";
    open.textContent = location.name;
    open.addEventListener("click", () => {
      searchInput.value = location.zip;
      loadWeather(location.zip);
    });
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "remove-saved";
    remove.setAttribute("aria-label", `Remove ${location.name}`);
    remove.textContent = "×";
    remove.addEventListener("click", () => {
      const updated = getSavedLocations().filter((saved) => (
        saved.zip !== location.zip
      ));
      localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
      renderSavedLocations();
      updateSaveButton();
    });
    chip.append(open, remove);
    savedLocations.append(chip);
  }
  document.querySelector("#saved-hint").hidden = locations.length > 0;
}

function updateSaveButton() {
  if (!activeLocation) return;
  const saved = getSavedLocations().some((location) => (
    location.zip === activeLocation.zip
  ));
  saveButton.textContent = saved ? "✓ Saved" : "＋ Save location";
  saveButton.disabled = saved;
}

function renderWeather(data) {
  const city = data.location.city;
  const state = data.location.state;
  const nwsLocation = [city, state].filter(Boolean).join(", ");
  document.querySelector("#location-title").textContent = nwsLocation || `ZIP ${data.location.zip}`;
  document.querySelector("#forecast-provider").textContent = data.provider || "Weather service";
  document.querySelector("#coordinates-label").textContent =
    `ZIP ${data.location.zip} · ${data.latitude.toFixed(4)}, ${data.longitude.toFixed(4)}`;
  const source = document.querySelector("#forecast-source");
  source.href = data.forecastUrl;
  source.textContent = `View ${data.provider || "weather"} source ↗`;
  renderAlerts(data.alerts, data.alertsError);
  renderDaily(data.forecast);
  renderHourly(data.hourly, data.hourlyError);
  updateSaveButton();
}

function renderAlerts(alerts, error) {
  const panel = document.querySelector("#alerts-panel");
  panel.replaceChildren();
  if (error) {
    panel.className = "alert-panel panel";
    panel.textContent = error;
    return;
  }
  if (!alerts.length) {
    panel.className = "alert-panel panel no-alerts";
    const check = document.createElement("span");
    check.className = "alert-check";
    check.setAttribute("aria-hidden", "true");
    check.textContent = "✓";
    const text = document.createElement("p");
    text.textContent = "No active NWS alerts for this location.";
    panel.append(check, text);
    return;
  }
  panel.className = "alert-panel panel";
  const heading = document.createElement("h2");
  heading.textContent = `Active weather alerts (${alerts.length})`;
  panel.append(heading);
  for (const feature of alerts) {
    const properties = feature.properties || {};
    const card = document.createElement("article");
    card.className = `alert-card${["Extreme", "Severe"].includes(properties.severity) ? " severe" : ""}`;
    const title = document.createElement("h3");
    title.textContent = properties.headline || properties.event || "Weather alert";
    const details = document.createElement("p");
    details.textContent = properties.areaDesc || "";
    const meta = document.createElement("p");
    meta.className = "alert-meta";
    meta.textContent = [properties.severity, properties.expires ? `Expires ${formatDateTime(properties.expires)}` : ""]
      .filter(Boolean).join(" · ");
    card.append(title, details, meta);
    if (properties.description) {
      const description = document.createElement("p");
      description.className = "alert-description";
      description.textContent = properties.description;
      card.append(description);
    }
    if (properties.instruction) {
      const instruction = document.createElement("p");
      instruction.textContent = `Instructions: ${properties.instruction}`;
      card.append(instruction);
    }
    panel.append(card);
  }
}

function renderDaily(periods) {
  const container = document.querySelector("#daily-forecast");
  container.replaceChildren();
  for (const period of periods || []) {
    const card = document.createElement("article");
    card.className = "forecast-card";
    const title = document.createElement("div");
    title.className = "period";
    title.textContent = period.name || "Forecast";
    const symbol = document.createElement("div");
    symbol.className = "weather-symbol";
    symbol.setAttribute("aria-hidden", "true");
    symbol.textContent = weatherSymbol(period.shortForecast);
    const temperature = document.createElement("p");
    temperature.className = "temperature";
    const range = period.temperatureLow === undefined || period.temperatureLow === null
      ? String(period.temperature ?? "—")
      : `${period.temperature ?? "—"} / ${period.temperatureLow}`;
    temperature.textContent = `${range} `;
    const unit = document.createElement("small");
    unit.textContent = period.temperatureUnit
      ? `${period.temperatureUnit}${period.temperatureLow === undefined ? "" : " · high/low"}`
      : "";
    temperature.append(unit);
    const conditions = document.createElement("p");
    conditions.className = "conditions";
    conditions.textContent = period.shortForecast || "Conditions unavailable";
    const wind = document.createElement("p");
    wind.className = "wind";
    wind.textContent = `Wind ${period.windSpeed || "N/A"} ${period.windDirection || ""}`.trim();
    card.append(title, symbol, temperature, conditions, wind);
    container.append(card);
  }
  if (!periods || periods.length === 0) {
    const empty = document.createElement("p");
    empty.className = "muted";
    empty.textContent = "No forecast periods were returned for this location.";
    container.append(empty);
  }
}

function renderHourly(periods, error) {
  const container = document.querySelector("#hourly-forecast");
  const message = document.querySelector("#hourly-message");
  container.replaceChildren();
  message.hidden = true;
  if (error) {
    message.textContent = error;
    message.hidden = false;
    return;
  }
  for (const period of (periods || []).slice(0, 12)) {
    const card = document.createElement("div");
    card.className = "hour-card";
    const time = document.createElement("time");
    time.dateTime = period.startTime || "";
    time.textContent = formatHour(period.startTime);
    const symbol = document.createElement("span");
    symbol.className = "hour-symbol";
    symbol.setAttribute("aria-hidden", "true");
    symbol.textContent = weatherSymbol(period.shortForecast);
    const temperature = document.createElement("strong");
    temperature.textContent = `${period.temperature ?? "—"}${period.temperatureUnit || "°"}`;
    const conditions = document.createElement("small");
    conditions.textContent = period.shortForecast || "";
    card.append(time, symbol, temperature, conditions);
    container.append(card);
  }
  if (!periods || periods.length === 0) {
    message.textContent = "Hourly forecast is not available for this location.";
    message.hidden = false;
  }
}

function weatherSymbol(forecast = "") {
  const text = forecast.toLowerCase();
  if (text.includes("thunder")) return "⛈️";
  if (text.includes("snow") || text.includes("blizzard") || text.includes("ice")) return "❄️";
  if (text.includes("rain") || text.includes("shower") || text.includes("drizzle")) return "🌧️";
  if (text.includes("fog") || text.includes("haze")) return "🌫️";
  if (text.includes("overcast") || text.includes("cloud")) return "☁️";
  if (text.includes("wind")) return "💨";
  if (text.includes("sun") || text.includes("clear")) return "☀️";
  return "🌡️";
}

function formatHour(value) {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "—"
    : new Intl.DateTimeFormat(undefined, { hour: "numeric" }).format(date);
}

function formatDateTime(value) {
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? value
    : new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }).format(date);
}

renderSavedLocations();
