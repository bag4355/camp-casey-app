(() => {
  /* ─── State ─── */

  /** UUID v4 생성 (crypto.randomUUID 미지원 환경 대응) */
  function generateSessionId() {
    if (typeof crypto !== "undefined" && crypto.randomUUID) return crypto.randomUUID();
    return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
      const r = (Math.random() * 16) | 0;
      return (c === "x" ? r : (r & 0x3) | 0x8).toString(16);
    });
  }

  function loadOrCreateSessionId() {
    let sid = localStorage.getItem("camp-casey.session-id");
    if (!sid) {
      sid = generateSessionId();
      localStorage.setItem("camp-casey.session-id", sid);
    }
    return sid;
  }

  const state = {
    locale: localStorage.getItem("camp-casey.locale") || window.__APP_BOOT__.defaultLocale || "ko",
    currencyMode: localStorage.getItem("camp-casey.currency-mode") || "usd_plus_krw",
    sessionId: loadOrCreateSessionId(),
    translations: {},
    bootstrap: null,
    exchangeRate: null,
    currentStoreResults: [],
    currentHolidayResults: [],
    toastTimer: null,
    trackerSchedule: { gate1: [], s0136: [], hovey: [], lastStop: [] },
    trackerInterval: null,
    homeGate1Result: null,
    calendarYear: new Date().getFullYear(),
    calendarMonth: new Date().getMonth(), // 0-indexed
  };

  /* ─── DOM helpers ─── */
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

  const dom = {
    html: document.documentElement,
    toast: $("#toast"),
    homeCards: $("#home-cards"),
    busResultsGate1: $("#bus-results-gate1"),
    busResultsS0136Gate: $("#bus-results-s0136-gate"),
    trainProviderInput: $("#train-provider-input"),
    trainResults: $("#train-results"),
    storeResults: $("#store-results"),
    storeOpenNowInput: $("#store-open-now-input"),
    holidayResults: $("#holiday-results"),
    holidayConfirmedOnly: $("#holiday-confirmed-only"),
    holidayNoteBox: $("#holiday-note-box"),
    calendarContainer: $("#calendar-container"),
    exchangeCurrentRate: $("#exchange-current-rate"),
    exchangeLastUpdated: $("#exchange-last-updated"),
    exchangeRefreshBtn: $("#exchange-refresh-btn"),
    exchangeStatusBadge: $("#exchange-status-badge"),
    converterAmountInput: $("#converter-amount-input"),
    converterDirectionInput: $("#converter-direction-input"),
    converterOutput: $("#converter-output"),
    converterFormula: $("#converter-formula"),
    chatForm: $("#chat-form"),
    chatInput: $("#chat-input"),
    chatLog: $("#chat-log"),
    chatSubmit: $("#chat-submit"),
    storeDialog: $("#store-dialog"),
    storeDialogTitle: $("#store-dialog-title"),
    storeDialogBody: $("#store-dialog-body"),
    clockTime: $("#clock-time"),
    clockDate: $("#clock-date"),
    busTrackerLine: $("#bus-tracker-line"),
    stopGate1: $("#stop-gate1-departures"),
    stopS0136: $("#stop-s0136-departures"),
  };

  /* ─── i18n ─── */
  function t(key, params = {}) {
    const raw = state.translations[key] || key;
    return Object.entries(params).reduce(
      (acc, [k, v]) => acc.replaceAll(`{${k}}`, String(v)),
      raw
    );
  }

  async function loadTranslations() {
    try {
      const res = await fetch(`/static/i18n/${state.locale}.json`, { cache: "no-store" });
      if (!res.ok) throw new Error("i18n fetch failed");
      state.translations = await res.json();
    } catch {
      state.translations = {};
    }
  }

  function applyTranslations() {
    $$("[data-i18n]").forEach((node) => {
      const key = node.dataset.i18n;
      node.textContent = t(key);
    });
    const placeholders = {
      "#chat-input": state.locale === "ko" ? "보산역 다음 인천행 언제야?" : "When is the next Incheon-bound train from Bosan?",
    };
    Object.entries(placeholders).forEach(([sel, ph]) => {
      const el = $(sel);
      if (el) el.placeholder = ph;
    });
    // Update suggest-query attributes to match locale
    const suggestQueryMap = {
      "chat.suggestBus":      t("chat.suggestBusQuery"),
      "chat.suggestTrain":    t("chat.suggestTrainQuery"),
      "chat.suggestStore":    t("chat.suggestStoreQuery"),
      "chat.suggestHoliday":  t("chat.suggestHolidayQuery"),
      "chat.suggestExchange": t("chat.suggestExchangeQuery"),
    };
    $$(".chip[data-suggest-query][data-i18n]").forEach((btn) => {
      const mapped = suggestQueryMap[btn.dataset.i18n];
      if (mapped) btn.dataset.suggestQuery = mapped;
    });
  }

  function updateLocaleButtons() {
    $$("[data-locale-switch]").forEach((btn) => {
      const active = btn.dataset.localeSwitch === state.locale;
      btn.setAttribute("aria-pressed", String(active));
      btn.classList.toggle("is-active", active);
    });
  }

  function updateCurrencyButtons() {
    $$("[data-currency-mode]").forEach((btn) => {
      const active = btn.dataset.currencyMode === state.currencyMode;
      btn.setAttribute("aria-pressed", String(active));
      btn.classList.toggle("is-active", active);
    });
  }

  async function setLocale(locale) {
    state.locale = locale;
    localStorage.setItem("camp-casey.locale", locale);
    dom.html.lang = locale;
    dom.html.dataset.locale = locale;
    await loadTranslations();
    updateLocaleButtons();
    applyTranslations();
    renderHome();
    renderStoreResults(state.currentStoreResults);
    renderHolidayResults(state.currentHolidayResults);
    renderCalendar();
    renderExchangePanel();
    renderConverter();
    updateHeaderClock();
    runBusQuery(false).catch(() => {});
  }

  function setCurrencyMode(mode) {
    state.currencyMode = mode;
    localStorage.setItem("camp-casey.currency-mode", mode);
    updateCurrencyButtons();
    renderHome();
    renderStoreResults(state.currentStoreResults);
    if (dom.storeDialog.open) {
      const storeId = dom.storeDialog.dataset.storeId;
      if (storeId) openStoreDetail(storeId);
    }
    renderConverter();
  }

  /* ─── Toast ─── */
  function showToast(msg) {
    dom.toast.textContent = msg;
    dom.toast.classList.add("is-visible");
    clearTimeout(state.toastTimer);
    state.toastTimer = setTimeout(() => dom.toast.classList.remove("is-visible"), 2800);
  }

  function setLoading(btn, loading) {
    if (!btn) return;
    btn.disabled = loading;
    btn.classList.toggle("is-loading", loading);
    btn.setAttribute("aria-busy", String(loading));
  }

  /* ─── Escape ─── */
  function escapeHtml(v) {
    return String(v ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }

  /* ─── Formatters ─── */
  function formatUsd(v) {
    return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 2 }).format(Number(v));
  }

  function formatKrw(v) {
    return new Intl.NumberFormat("ko-KR", { style: "currency", currency: "KRW", maximumFractionDigits: 0 }).format(Number(v));
  }

  function formatMoney(money) {
    if (!money || money.amount == null) return `<span class="subtle">${state.locale === "ko" ? "없음" : "None"}</span>`;
    const amount = Number(money.amount);
    const currency = money.currency || "USD";
    if (currency === "KRW") return formatKrw(amount);
    const usdLabel = formatUsd(amount);
    const rate = state.exchangeRate ? Number(state.exchangeRate.usd_to_krw) : null;
    if (!rate) return usdLabel;
    const krwLabel = formatKrw(Math.round(amount * rate));
    if (state.currencyMode === "usd_only") return usdLabel;
    if (state.currencyMode === "krw_primary") {
      return `<span class="money-tip" data-krw="${escapeHtml(usdLabel)}">${escapeHtml(krwLabel)}</span>`;
    }
    return `<span class="money-tip" data-krw="${escapeHtml(krwLabel)}">${escapeHtml(usdLabel)}</span>`;
  }

  function formatDateTime(v) {
    if (!v) return "—";
    return new Intl.DateTimeFormat(state.locale === "ko" ? "ko-KR" : "en-US", {
      dateStyle: "medium",
      timeStyle: "short",
      hour12: false,
    }).format(new Date(v));
  }

  function formatDate(v) {
    if (!v) return "—";
    return new Intl.DateTimeFormat(state.locale === "ko" ? "ko-KR" : "en-US", {
      dateStyle: "medium",
    }).format(new Date(v + "T00:00:00"));
  }

  function formatTime(v) {
    if (!v) return "—";
    const parts = String(v).split(":");
    const h = String(Number(parts[0])).padStart(2, "0");
    const m = String(Number(parts[1] || 0)).padStart(2, "0");
    return `${h}:${m}`;
  }

  function toDatetimeLocalValue(date = new Date()) {
    const pad = (n) => String(n).padStart(2, "0");
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
  }

  /* ─── API ─── */
  async function api(path, options = {}) {
    const res = await fetch(path, { headers: { "Content-Type": "application/json" }, ...options });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const detail = data.detail || res.statusText || "Request failed";
      throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
    }
    return data;
  }

  function scrollToSection(id) {
    const el = document.getElementById(id);
    if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  /* ─── Header Clock ─── */
  function updateHeaderClock() {
    const now = new Date();
    const timeStr = now.toLocaleTimeString(state.locale === "ko" ? "ko-KR" : "en-US", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
    });
    const dateStr = now.toLocaleDateString(state.locale === "ko" ? "ko-KR" : "en-US", {
      year: "numeric",
      month: "long",
      day: "numeric",
      weekday: "short",
    });

    if (dom.clockTime) dom.clockTime.textContent = timeStr;
    if (dom.clockDate) dom.clockDate.textContent = dateStr;

  }

  function dayTypeBadgeClass(derived) {
    if (!derived) return "badge--neutral";
    if (derived === "weekday") return "badge--neutral";
    if (derived === "saturday" || derived === "sunday") return "badge--info";
    if (derived.includes("holiday") || derived.includes("training")) return "badge--warning";
    return "badge--neutral";
  }

  /* ─── Badges ─── */
  function statusBadge(status) {
    if (!status) return `<span class="badge badge--neutral">${t("common.unknown")}</span>`;
    if (status.open_now) return `<span class="badge badge--success">${t("delivery.open")}</span>`;
    if (status.closes_soon) return `<span class="badge badge--warning">${t("delivery.closesSoon")}</span>`;
    if (status.unsupported_schedule) return `<span class="badge badge--neutral">${t("delivery.hoursUnavailable")}</span>`;
    if (status.closed_today) return `<span class="badge badge--danger">${t("delivery.closedToday")}</span>`;
    if (status.opens_at) return `<span class="badge badge--neutral">${t("delivery.opensAt", { time: formatTime(status.opens_at) })}</span>`;
    return `<span class="badge badge--danger">${t("delivery.closed")}</span>`;
  }

  function holidayBadge(status) {
    const ko = state.locale === "ko";
    if (!status) return `<span class="badge badge--neutral">${t("common.unknown")}</span>`;
    if (status.startsWith("confirmed_official")) return `<span class="badge badge--success">${ko ? "공식 확정" : "Confirmed"}</span>`;
    if (status.startsWith("confirmed_pattern")) return `<span class="badge badge--info">${ko ? "패턴 기반" : "Confirmed"}</span>`;
    if (status.startsWith("likely")) return `<span class="badge badge--warning">${ko ? "가능성 높음" : "Likely"}</span>`;
    return `<span class="badge badge--danger">${ko ? "미확인" : "Unconfirmed"}</span>`;
  }

  function dayTypeBadge(derived) {
    const key = `daytype.${derived}`;
    const label = t(key) || t("daytype.training_holiday") || "Training Holiday";
    const cls = dayTypeBadgeClass(derived);
    return `<span class="badge ${cls}">${escapeHtml(label)}</span>`;
  }

  function renderEmptyState(title, body) {
    return `<div class="empty-state"><h3>${escapeHtml(title)}</h3><p>${escapeHtml(body)}</p></div>`;
  }

  // Gate#1에서 S-0136(Gate방향) 까지 소요 시간(분)
  const GATE1_TO_S0136_GATE_MIN = 53;

  /* ─── Home ─── */
  function renderHome() {
    if (!state.bootstrap) return;
    const { today_day_type, exchange_rate, home } = state.bootstrap;
    dom.homeCards.innerHTML = [
      `<article class="card summary-card interactive-card" data-scroll-target="holidays" role="button" tabindex="0">
        <div class="card-header">
          <h3>${t("home.todayDayType")}</h3>
          ${dayTypeBadge(today_day_type.derived_day_type)}
        </div>
        <p class="hero-value">${escapeHtml(today_day_type.holiday_name || t(`daytype.${today_day_type.derived_day_type}`) || t("daytype.training_holiday") || "Training Holiday")}</p>
      </article>`,
      renderGate1HomeCard(),
      renderS0136GateHomeCard(),
      renderNextDepartureCard(home.next_train, "train", t("home.nextTrain"), "transit"),
      `<article class="card summary-card interactive-card" data-scroll-target="exchange" role="button" tabindex="0">
        <div class="card-header">
          <h3>${t("home.exchangeRate")}</h3>
          <span class="badge badge--success">${t("exchange.autoMode")}</span>
        </div>
        <p class="hero-value">${exchange_rate ? `1 USD = ${Number(exchange_rate.usd_to_krw).toLocaleString("ko-KR")} ₩` : "—"}</p>
        <p class="helper">${t("exchange.summaryHelper")}</p>
      </article>`,
      `<article class="card summary-card interactive-card" data-scroll-target="delivery" role="button" tabindex="0">
        <div class="card-header">
          <h3>${t("home.openStores")}</h3>
          <span class="badge badge--success">${home.open_stores.length}</span>
        </div>
        <div class="metric-list">
          ${home.open_stores.slice(0, 4).map((s) =>
            `<div class="metric"><span class="metric__label">${escapeHtml(s.name)}</span><span class="metric__value">${formatMoney(s.minimum_order)}</span></div>`
          ).join("") || `<p class="subtle">${t("home.noOpenStores")}</p>`}
        </div>
      </article>`,
    ].join("");

    $$("[data-scroll-target]", dom.homeCards).forEach((el) => {
      el.addEventListener("click", () => scrollToSection(el.dataset.scrollTarget));
      el.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") { e.preventDefault(); scrollToSection(el.dataset.scrollTarget); }
      });
    });

    renderExchangePanel();
  }

  // Helper: format S-0136 Gate방향 upcoming times for home card
  function buildS0136GateHomeDeps() {
    const nowMin = (new Date()).getHours() * 60 + (new Date()).getMinutes();
    const allGateMins = getS0136GateTimes();

    const upcoming = [];
    for (const t of allGateMins) {
      const cdMin = t >= nowMin ? Math.round(t - nowMin) : Math.round(t + 1440 - nowMin);
      if (cdMin < 0 || cdMin > 300) continue;
      const h = String(Math.floor(t / 60) % 24).padStart(2, "0");
      const m = String(Math.round(t % 60)).padStart(2, "0");
      upcoming.push({ timeStr: `${h}:${m}`, countdownMin: cdMin });
    }
    upcoming.sort((a, b) => a.countdownMin - b.countdownMin);
    return upcoming.slice(0, 3);
  }

  function cdLabel(min) {
    if (min <= 0) return state.locale === "ko" ? "곧 도착" : "Now";
    return state.locale === "ko" ? `약 ${min}분 후` : `~${min}m`;
  }

  function renderGate1HomeCard() {
    const result = state.homeGate1Result;
    const deps = result?.departures || [];
    const first = deps[0];
    return `<article class="card summary-card interactive-card" data-scroll-target="transit" role="button" tabindex="0">
      <div class="card-header">
        <h3>${t("home.nextBus")}</h3>
        <span class="badge badge--neutral">Gate #1</span>
      </div>
      <p class="hero-value">${first ? formatTime(first.time) : "—"}</p>
      <p class="subtle">${first ? escapeHtml(first.countdown_label) : t("home.noNextBus")}</p>
      <div class="chip-row">
        ${deps.slice(0, 3).map((d) => `<span class="chip">${formatTime(d.time)} · ${escapeHtml(d.countdown_label)}</span>`).join("")}
      </div>
    </article>`;
  }

  function renderS0136GateHomeCard() {
    const deps = buildS0136GateHomeDeps();
    const first = deps[0];
    const label = state.locale === "ko" ? "S-0136 (Gate방향)" : "S-0136 (Gate dir.)";
    return `<article class="card summary-card interactive-card" data-scroll-target="transit" role="button" tabindex="0">
      <div class="card-header">
        <h3>${t("home.nextBus")}</h3>
        <span class="badge badge--neutral">${label}</span>
      </div>
      <p class="hero-value">${first ? first.timeStr : "—"}</p>
      <p class="subtle">${first ? cdLabel(first.countdownMin) : t("home.noNextBus")}</p>
      <div class="chip-row">
        ${deps.slice(0, 3).map((d) => `<span class="chip">${d.timeStr} · ${escapeHtml(cdLabel(d.countdownMin))}</span>`).join("")}
      </div>
    </article>`;
  }

  function renderNextDepartureCard(result, kind, title, targetSection) {
    const deps = result?.departures || [];
    const first = deps[0];
    return `<article class="card summary-card interactive-card" data-scroll-target="${targetSection}" role="button" tabindex="0">
      <div class="card-header">
        <h3>${escapeHtml(title)}</h3>
        <span class="badge badge--neutral">${escapeHtml(result?.service_profile_label || result?.service_label || "—")}</span>
      </div>
      <p class="hero-value">${first ? `${formatTime(first.time)}${first.destination ? ` · ${escapeHtml(first.destination)}` : ""}` : "—"}</p>
      <p class="subtle">${first ? `${first.countdown_label}${first.is_next_day ? " +1d" : ""}` : t(`home.noNext${kind === "bus" ? "Bus" : "Train"}`)}</p>
      <div class="chip-row">
        ${deps.slice(0, 3).map((d) => `<span class="chip">${formatTime(d.time)} · ${escapeHtml(d.countdown_label)}</span>`).join("")}
      </div>
      <p class="helper">${escapeHtml(result?.stop?.name || result?.provider?.station_name || "")}</p>
    </article>`;
  }

  async function fetchHomeGate1() {
    try {
      state.homeGate1Result = await api("/api/bus/next?stop=bus-terminal-gate-1&count=8");
      renderHome();
    } catch {
      // silently ignore; renderHome will show skeleton
    }
  }

  /* ─── Bus Results ─── */
  function renderBusResults(result, fullMode = false, container = null) {
    const el = container || dom.busResultsGate1;
    if (!el) return;
    if (!result || result.available === false) {
      el.innerHTML = renderEmptyState(t("transit.noBusTitle"), result?.message || t("transit.noBusBody"));
      return;
    }
    const deps = result.departures || [];
    if (!deps.length) {
      el.innerHTML = renderEmptyState(t("transit.noBusTitle"), result.message || t("transit.noBusBody"));
      return;
    }
    el.innerHTML = `
      <article class="card result-card">
        <div class="card-header">
          <div>
            <h3>${escapeHtml(result.stop?.name || "")}</h3>
            <p class="subtle">${escapeHtml(result.service_profile_label || "")}</p>
          </div>
          ${dayTypeBadge(result.day_type?.derived_day_type)}
        </div>
        <div class="departure-list">
          ${deps.map((d) => `
            <div class="departure-row">
              <div class="departure-row__main">
                <strong>${formatTime(d.time)} ${d.is_next_day ? "<span class='badge badge--warning'>+1d</span>" : ""}</strong>
                <span>${escapeHtml(d.countdown_label || "")}</span>
              </div>
              <span class="subtle">${formatDateTime(d.departure_datetime)}</span>
            </div>
          `).join("")}
        </div>
        ${fullMode ? `<p class="helper">${t("transit.rolloverHelper")}</p>` : ""}
      </article>`;
  }

  function renderTrainResults(result, fullMode = false) {
    if (!result || result.available === false) {
      dom.trainResults.innerHTML = renderEmptyState(t("transit.noTrainTitle"), result?.message || t("transit.noTrainBody"));
      return;
    }
    const deps = result.departures || [];
    if (!deps.length) {
      dom.trainResults.innerHTML = renderEmptyState(t("transit.noTrainTitle"), result.message || t("transit.noTrainBody"));
      return;
    }
    dom.trainResults.innerHTML = `
      <article class="card result-card">
        <div class="card-header">
          <div>
            <h3>${escapeHtml(result.provider?.station_name || "")}</h3>
            <p class="subtle">${escapeHtml(result.service_label || "")}</p>
          </div>
          <span class="badge badge--info">${escapeHtml(result.matched_destination || t("transit.allDestinations"))}</span>
        </div>
        <div class="departure-list">
          ${deps.map((d) => `
            <div class="departure-row">
              <div class="departure-row__main">
                <strong>${formatTime(d.time)} · ${escapeHtml(d.destination || "")}</strong>
                <span>${escapeHtml(d.countdown_label || "")}</span>
              </div>
              <span class="subtle">${formatDateTime(d.departure_datetime)}</span>
            </div>
          `).join("")}
        </div>
      </article>`;
  }

  /* ─── Store Results ─── */
  function renderStoreResults(results) {
    state.currentStoreResults = results || [];
    if (!results || !results.length) {
      dom.storeResults.innerHTML = renderEmptyState(t("delivery.emptyTitle"), t("delivery.emptyBody"));
      return;
    }
    dom.storeResults.innerHTML = results.map((store) => `
      <article class="card result-card interactive-card" data-store-id="${escapeHtml(store.store_id)}" tabindex="0" role="button">
        <div class="card-header">
          <div>
            <h3>${escapeHtml(store.name)}</h3>
            <p class="subtle">${escapeHtml(store.match_reason || "")}</p>
          </div>
          ${statusBadge(store.status)}
        </div>
        <div class="metric-list">
          <div class="metric"><span class="metric__label">${t("delivery.minOrder")}</span><span class="metric__value">${formatMoney(store.minimum_order)}</span></div>
          <div class="metric"><span class="metric__label">${t("delivery.deliveryCharge")}</span><span class="metric__value">${formatMoney(store.delivery_charge)}</span></div>
          <div class="metric"><span class="metric__label">${t("delivery.phone")}</span><span class="metric__value">${escapeHtml((store.phones || [])[0] || "—")}</span></div>
        </div>
      </article>
    `).join("");

    $$("[data-store-id]", dom.storeResults).forEach((card) => {
      const open = () => openStoreDetail(card.dataset.storeId);
      card.addEventListener("click", open);
      card.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") { e.preventDefault(); open(); }
      });
    });
  }

  /* ─── Holiday name formatting ─── */
  function getHolidayNameByDate(dateStr) {
    return (state.currentHolidayResults || []).find(
      (i) => i.date === dateStr && i.holiday_name
    )?.holiday_name || null;
  }

  function formatHolidayDisplayName(item) {
    const type = item.holiday_type || "";
    // federal_holiday and rok_holiday → show their name directly
    if (type === "federal_holiday" || type === "rok_holiday") {
      return item.holiday_name || (type === "federal_holiday" ? "Federal Holiday" : "ROK Holiday");
    }
    // training_holiday and everything else (possible_local_*, etc.) → Training Holiday
    const linkedName = item.paired_with ? getHolidayNameByDate(item.paired_with) : null;
    const baseName = item.holiday_name && type === "training_holiday" ? item.holiday_name : null;
    const label = baseName || (linkedName ? `Training Holiday (${linkedName})` : "Training Holiday");
    return label;
  }

  /* ─── Holiday Results ─── */
  function renderHolidayResults(results) {
    state.currentHolidayResults = results || [];
    // Actual rendering is handled by renderCalendar → renderHolidayResultsForMonth
    renderCalendar();
  }

  function renderHolidayNotes() {
    // Notes/comments intentionally hidden
    if (dom.holidayNoteBox) dom.holidayNoteBox.innerHTML = "";
  }

  /* ─── Calendar ─── */
  function renderCalendar() {
    if (!dom.calendarContainer) return;
    const holidays = state.currentHolidayResults || [];
    const confirmedOnly = dom.holidayConfirmedOnly?.checked;

    const today = new Date();
    const todayStr = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-${String(today.getDate()).padStart(2, "0")}`;

    const monthNames = state.locale === "ko"
      ? ["1월","2월","3월","4월","5월","6월","7월","8월","9월","10월","11월","12월"]
      : ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
    const dayNames = state.locale === "ko"
      ? ["일","월","화","수","목","금","토"]
      : ["Su","Mo","Tu","We","Th","Fr","Sa"];

    const { calendarYear: year, calendarMonth: month } = state;

    // Build holiday map for this month only
    const holidayMap = {};
    holidays.forEach((h) => { if (h.date?.startsWith(`${year}-${String(month + 1).padStart(2, "0")}`)) holidayMap[h.date] = h; });

    const firstDay = new Date(year, month, 1).getDay();
    const daysInMonth = new Date(year, month + 1, 0).getDate();
    const cells = [];
    for (let i = 0; i < firstDay; i++) cells.push(`<div class="calendar-day calendar-day--empty"></div>`);

    for (let day = 1; day <= daysInMonth; day++) {
      const dateStr = `${year}-${String(month + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
      const dow = (firstDay + day - 1) % 7;
      const isSun = dow === 0;
      const isSat = dow === 6;
      const isToday = dateStr === todayStr;
      const holiday = holidayMap[dateStr];

      let cls = "calendar-day";
      if (isToday) cls += " calendar-day--today";
      else if (isSun) cls += " calendar-day--sun";
      else if (isSat) cls += " calendar-day--sat";

      let offCls = "";
      if (isSun || isSat) {
        offCls = " calendar-day--off";
      } else if (holiday) {
        const isConfirmed = holiday.status?.startsWith("confirmed");
        const dateMonthNum = parseInt((dateStr || "").slice(5, 7), 10);
        const isEffectivelyConfirmed = isConfirmed || (year === 2026 && dateMonthNum <= 9);
        if (!confirmedOnly || isEffectivelyConfirmed || isConfirmed) {
          offCls = " calendar-day--confirmed-off";
        }
      }

      const title = holiday ? ` title="${escapeHtml(formatHolidayDisplayName(holiday))}"` : "";
      cells.push(`<div class="${cls}${offCls}"${title}>${day}</div>`);
    }

    dom.calendarContainer.innerHTML = `
      <div class="calendar-grid" style="padding: 0 var(--space-5);">
        <div class="calendar-weekdays">
          ${dayNames.map((d, i) => `<div class="calendar-weekday" style="${i===0?"color:var(--danger)":i===6?"color:var(--info)":""}">${d}</div>`).join("")}
        </div>
        <div class="calendar-days">${cells.join("")}</div>
      </div>`;

    // Update pager label
    const label = $("#cal-month-label");
    if (label) label.textContent = state.locale === "ko" ? `${year}년 ${monthNames[month]}` : `${monthNames[month]} ${year}`;

    // Update holiday list for this month
    renderHolidayResultsForMonth(year, month, holidays, confirmedOnly);
  }

  function renderHolidayResultsForMonth(year, month, holidays, confirmedOnly) {
    const el = dom.holidayResults;
    if (!el) return;
    const prefix = `${year}-${String(month + 1).padStart(2, "0")}`;
    const monthHolidays = holidays.filter((h) => {
      if (!h.date?.startsWith(prefix)) return false;
      if (!confirmedOnly) return true;
      const isConfirmed = h.status?.startsWith("confirmed");
      const dateMonthNum = parseInt(h.date.slice(5, 7), 10);
      return isConfirmed || (year === 2026 && dateMonthNum <= 9);
    });

    if (!monthHolidays.length) {
      el.innerHTML = `<p class="subtle" style="padding: var(--space-3) var(--space-5);">${state.locale === "ko" ? "이 달에 휴일 없음" : "No holidays this month"}</p>`;
      return;
    }
    el.innerHTML = monthHolidays.map((h) => {
      const name = formatHolidayDisplayName(h);
      return `<div class="holiday-item">
        <span class="holiday-item__date">${escapeHtml(h.date || "")}</span>
        <span class="holiday-item__name">${escapeHtml(name)}</span>
      </div>`;
    }).join("");
  }

  /* ─── Exchange ─── */
  function renderExchangePanel() {
    const snap = state.exchangeRate;
    if (!snap) {
      dom.exchangeCurrentRate.textContent = t("exchange.noRate");
      dom.exchangeLastUpdated.textContent = t("exchange.noRateHelper");
      dom.exchangeStatusBadge.textContent = "—";
      return;
    }
    dom.exchangeCurrentRate.textContent = `1 USD = ${Number(snap.usd_to_krw).toLocaleString("ko-KR")} ₩`;
    dom.exchangeLastUpdated.textContent = `${t("exchange.updatedAt")}: ${formatDateTime(snap.updated_at)}`;
    dom.exchangeStatusBadge.textContent = snap.is_auto ? t("exchange.autoMode") : t("exchange.manualMode");
    dom.exchangeStatusBadge.className = `badge ${snap.is_auto ? "badge--success" : "badge--info"}`;
  }

  async function refreshExchangeRate() {
    try {
      const data = await api("/api/exchange-rate");
      state.exchangeRate = data.snapshot;
      renderExchangePanel();
      renderConverter();
      showToast(state.locale === "ko" ? "환율 새로고침 완료" : "Rate refreshed");
    } catch (err) {
      showToast(err.message);
    }
  }

  function renderConverter() {
    const amount = Number(dom.converterAmountInput.value);
    const direction = dom.converterDirectionInput.value;
    if (!Number.isFinite(amount) || amount < 0 || !state.exchangeRate) {
      dom.converterOutput.innerHTML = `<span class="subtle">${t("exchange.converterHint")}</span>`;
      dom.converterFormula.textContent = "";
      return;
    }
    const rate = Number(state.exchangeRate.usd_to_krw);
    if (direction === "USD_TO_KRW") {
      const result = Math.round(amount * rate);
      dom.converterOutput.innerHTML = `${formatUsd(amount)} → <strong>${formatKrw(result)}</strong>`;
      dom.converterFormula.textContent = `${amount} × ${rate} = ${result}`;
    } else {
      const result = (amount / rate).toFixed(2);
      dom.converterOutput.innerHTML = `${formatKrw(amount)} → <strong>${formatUsd(result)}</strong>`;
      dom.converterFormula.textContent = `${amount} ÷ ${rate} = ${result}`;
    }
  }

  /* ─── Store Hours formatting ─── */
  const SELECTOR_LABEL = {
    ko: {
      daily:                               "매일",
      open:                                "상시 운영",
      mon_fri:                             "월–금",
      fri_sat:                             "금–토",
      sun_thu:                             "일–목",
      fri_sat_holiday:                     "금·토·공휴일",
      sat_sun_us_holiday:                  "토·일·공휴일",
      sat_sun_us_holiday_training_holiday: "토·일·공휴일·훈련 휴일",
    },
    en: {
      daily:                               "Daily",
      open:                                "Always open",
      mon_fri:                             "Mon – Fri",
      fri_sat:                             "Fri – Sat",
      sun_thu:                             "Sun – Thu",
      fri_sat_holiday:                     "Fri, Sat & Holidays",
      sat_sun_us_holiday:                  "Sat, Sun & Holidays",
      sat_sun_us_holiday_training_holiday: "Sat, Sun & all Holidays",
    },
  };

  function formatSelectorRaw(raw) {
    if (!raw) return "";
    const loc = state.locale === "ko" ? "ko" : "en";
    return SELECTOR_LABEL[loc][raw] || raw.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
  }

  function formatStoreHours(store, status) {
    const rules = (store.delivery_hours_rules?.length ? store.delivery_hours_rules : store.hours_rules) || [];
    if (!rules.length) {
      if (status?.unsupported_schedule) return `<span class="subtle">${t("delivery.hoursUnavailable")}</span>`;
      return `<span class="subtle">${state.locale === "ko" ? "없음" : "None"}</span>`;
    }
    const lines = rules.map((r) => {
      const windows = (r.windows || []).map((w) => {
        const s = String(w.start).substring(0, 5);
        const e = String(w.end).substring(0, 5);
        return `${s}–${e}`;
      }).join(", ");
      const sel = r.selectors_raw ? formatSelectorRaw(r.selectors_raw) : "";
      const lbl = r.period_label ? `<em>${escapeHtml(r.period_label)}</em> · ` : "";
      return `<span class="store-hours-row">${lbl}${sel ? `<span class="hours-selector">${escapeHtml(sel)}</span> ` : ""}${windows || "—"}</span>`;
    });
    return lines.join("<br>");
  }

  function renderStoreDetail(store, status) {
    dom.storeDialogTitle.textContent = store.name;
    dom.storeDialog.dataset.storeId = store.store_id;
    dom.storeDialogBody.innerHTML = `
      <div class="card result-card">
        <div class="card-header">
          <div>
            <h4>${escapeHtml(store.name)}</h4>
            <p class="subtle">${escapeHtml(store.updated_date || "")}</p>
          </div>
          ${statusBadge(status)}
        </div>
        <div class="metric-list">
          <div class="metric"><span class="metric__label">${t("delivery.minOrder")}</span><span class="metric__value">${formatMoney(store.minimum_delivery_order || store.minimum_order)}</span></div>
          <div class="metric"><span class="metric__label">${t("delivery.deliveryCharge")}</span><span class="metric__value">${formatMoney(store.delivery_charge)}</span></div>
          <div class="metric"><span class="metric__label">${t("delivery.phone")}</span><span class="metric__value">${(store.phones || []).map((p) => `<a class="link-inline" href="tel:${escapeHtml(p)}">${escapeHtml(p)}</a>`).join(", ") || `<span class="subtle">${state.locale === "ko" ? "없음" : "None"}</span>`}</span></div>
          <div class="metric metric--hours"><span class="metric__label">${t("delivery.hours")}</span><span class="metric__value metric__value--hours">${formatStoreHours(store, status)}</span></div>
        </div>
        ${(store.notes || []).length ? `<div class="info-banner" style="border-radius:var(--radius-md);"><strong>${t("common.note")}</strong><p class="helper">${(store.notes || []).map(escapeHtml).join(" · ")}</p></div>` : ""}
      </div>
      <div class="status-grid">
        ${(store.sections || []).map((section) => `
          <section class="menu-section card result-card">
            <div class="card-header">
              <div>
                <h4>${escapeHtml(section.name)}</h4>
                ${section.flags?.includes("alternate_board") ? `<span class="badge badge--warning">alternate board</span>` : ""}
              </div>
              ${section.section_hours_text ? `<span class="badge badge--neutral">${escapeHtml(section.section_hours_text)}</span>` : ""}
            </div>
            ${section.note ? `<p class="helper">${escapeHtml(section.note)}</p>` : ""}
            <div class="menu-list">
              ${(section.items || []).map((item) => `
                <article class="menu-row">
                  <div class="menu-row__main">
                    <strong>${escapeHtml(item.name)}</strong>
                    <div class="menu-item-prices">
                      ${(item.pricing || []).map((v) => `<span class="price-pill">${v.label ? `${escapeHtml(v.label)} ` : ""}${formatMoney(v.price)}</span>`).join("") || `<span class="subtle">—</span>`}
                    </div>
                  </div>
                  ${item.description ? `<span class="subtle">${escapeHtml(item.description)}</span>` : ""}
                  ${(item.addons || []).length ? `<span class="helper">${t("delivery.addons")}: ${(item.addons || []).map((a) => `${escapeHtml(a.label || "")} ${formatMoney(a.price)}`).join(", ")}</span>` : ""}
                  ${(item.options || []).length ? `<span class="helper">${t("delivery.options")}: ${(item.options || []).map(escapeHtml).join(", ")}</span>` : ""}
                  ${(item.flavors || []).length ? `<span class="helper">${t("delivery.flavors")}: ${(item.flavors || []).map(escapeHtml).join(", ")}</span>` : ""}
                </article>
              `).join("")}
            </div>
          </section>
        `).join("")}
      </div>`;
    if (!dom.storeDialog.open) dom.storeDialog.showModal();
  }

  /* ─── Chat ─── */
  function appendChatBubble(role, html, metaHtml = "") {
    if (dom.chatLog.querySelector(".empty-state")) dom.chatLog.innerHTML = "";
    const bubble = document.createElement("article");
    bubble.className = `chat-bubble chat-bubble--${role}`;
    bubble.innerHTML = `${metaHtml ? `<div class="chat-meta">${metaHtml}</div>` : ""}<div>${html}</div>`;
    dom.chatLog.appendChild(bubble);
    dom.chatLog.scrollTop = dom.chatLog.scrollHeight;
  }

  function renderSources(sources) {
    if (!sources?.length) return "";
    return `<div class="source-list">${sources.map((s) => `
      <div class="source-row">
        <span class="source-row__label">${escapeHtml(s.label)}</span>
        ${s.excerpt ? `<span class="subtle">${escapeHtml(s.excerpt)}</span>` : ""}
      </div>`).join("")}</div>`;
  }

  async function runChat(query) {
    scrollToSection("chat");
    appendChatBubble("user", `<p>${escapeHtml(query)}</p>`, `<span class="badge badge--neutral">${state.locale === "ko" ? "사용자" : "User"}</span>`);
    setLoading(dom.chatSubmit, true);
    try {
      const response = await api("/api/chat", {
        method: "POST",
        body: JSON.stringify({
          query,
          locale: state.locale,
          currency_mode: state.currencyMode,
          reference_time: new Date().toISOString(),
          session_id: state.sessionId,
        }),
      });
      const turnCount = response.debug?.history_turns ?? 0;
      const historyBadge = turnCount > 0
        ? `<span class="badge badge--muted" title="${state.locale === "ko" ? "이전 대화 기억 중" : "Remembering context"}">${turnCount}${state.locale === "ko" ? "턴" : "t"}</span>`
        : "";
      const meta = [
        `<span class="badge badge--info">${escapeHtml(response.intent)}</span>`,
        `<span class="badge badge--neutral">${response.used_llm ? "AI" : (state.locale === "ko" ? "코드" : "Code")}</span>`,
        historyBadge,
      ].join("");
      appendChatBubble("assistant", `<p>${escapeHtml(response.answer)}</p>`, meta);
      if (response.intent === "store") fetchStores();
      if (response.intent === "exchange") {
        const rd = await api("/api/exchange-rate");
        state.exchangeRate = rd.snapshot;
        renderExchangePanel();
        renderConverter();
      }
    } catch (err) {
      appendChatBubble("assistant", `<p>${escapeHtml(err.message)}</p>`, `<span class="badge badge--danger">${state.locale === "ko" ? "오류" : "Error"}</span>`);
    } finally {
      setLoading(dom.chatSubmit, false);
    }
  }

  /* ─── Dual Stop Dashboard ─── */
  function renderDualStopDepartures(containerId, result) {
    const container = $(containerId);
    if (!container) return;
    const deps = result?.departures || [];
    if (!deps.length) {
      container.innerHTML = `<div class="departure-pill"><span class="departure-pill__time">—</span><span class="departure-pill__countdown">${t("transit.noServiceNow")}</span></div>`;
      return;
    }
    container.innerHTML = deps.slice(0, 3).map((d) => `
      <div class="departure-pill">
        <span class="departure-pill__time">${formatTime(d.time)}</span>
        <span class="departure-pill__countdown">${escapeHtml(d.countdown_label || "")}</span>
      </div>`).join("");
  }

  async function fetchDualStops() {
    try {
      const gate1 = await api("/api/bus/next?stop=bus-terminal-gate-1&count=6");
      renderDualStopDepartures("#stop-gate1-departures", gate1);
      renderS0136GateDepartures();
    } catch (err) {
      showToast(err.message);
    }
  }

  function renderS0136GateDepartures() {
    const container = $("#stop-s0136-departures");
    if (!container) return;
    const nowMin = (new Date()).getHours() * 60 + (new Date()).getMinutes();
    const deps = buildS0136GateHomeDeps();

    if (!deps.length) {
      container.innerHTML = `<div class="departure-pill"><span class="departure-pill__time">—</span><span class="departure-pill__countdown">${t("transit.noServiceNow")}</span></div>`;
      return;
    }
    container.innerHTML = deps.map((d) => `
      <div class="departure-pill">
        <span class="departure-pill__time">${d.timeStr}</span>
        <span class="departure-pill__countdown">${state.locale === "ko" ? `약 ${d.countdownMin}분` : `~${d.countdownMin}m`}</span>
      </div>`).join("");
  }

  /* ─── Bus Live Tracker (5-stop full-loop) ─── */
  // Stop positions as percentages along the tracker rail
  const TRACKER_STOP_PCTS = [0, 20.6, 52.4, 84.1, 100];

  function timeStrToMinutes(timeStr) {
    const parts = String(timeStr || "").split(":");
    return Number(parts[0]) * 60 + Number(parts[1] || 0);
  }

  async function fetchTrackerSchedules() {
    const today = new Date().toISOString().slice(0, 10);
    try {
      const [gate1Sched, s0136Sched, hoveySched, lastSched] = await Promise.all([
        api(`/api/bus/schedule?stop=bus-terminal-gate-1&date=${today}`),
        api(`/api/bus/schedule?stop=bus-stop-s-0136&date=${today}`),
        api(`/api/bus/schedule?stop=opposite-the-dfac-bus-stop-s-4159&date=${today}`),
        api(`/api/bus/schedule?stop=bowling-ctr-bldg-s-3014&date=${today}`),
      ]);
      state.trackerSchedule.gate1   = (gate1Sched?.departures   || []).map((d) => timeStrToMinutes(d.time));
      state.trackerSchedule.s0136   = (s0136Sched?.departures   || []).map((d) => timeStrToMinutes(d.time));
      state.trackerSchedule.hovey   = (hoveySched?.departures   || []).map((d) => timeStrToMinutes(d.time));
      state.trackerSchedule.lastStop = (lastSched?.departures   || []).map((d) => timeStrToMinutes(d.time));
    } catch {
      state.trackerSchedule = { gate1: [], s0136: [], hovey: [], lastStop: [] };
    }
    updateBusTracker();
    renderS0136GateDepartures();
    renderHome();
    runBusQuery(false).catch(() => {});
  }

  function findNearest(times, after, within) {
    return times.find((t) => t > after && t - after <= within) ?? null;
  }

  /**
   * Find the time that is within a SPECIFIC offset range [minOff, maxOff] after base.
   * This prevents picking up times from adjacent trips that happen to fall in a wider window.
   * Offsets confirmed from schedule data: Hovey+13, Hovey-stop+33, Gate+53, Bowling+63.
   */
  function findNearestInRange(times, base, minOff, maxOff) {
    return times.find((t) => {
      const diff = t - base;
      return diff >= minOff && diff <= maxOff;
    }) ?? null;
  }

  /**
   * Extract stop-36 (S-0136 Gate방향) times.
   * Strategy: Gate방향 time = Gate#1 departure + 53 min (consistent offset).
   * We verify each candidate against the actual S-0136 schedule (±5 min tolerance).
   * This avoids the ambiguity of "closest preceding G1" logic.
   */
  function getS0136GateTimes() {
    const { gate1, s0136 } = state.trackerSchedule;
    if (!gate1.length || !s0136.length) return [];

    const OFFSET = 53;       // minutes: Gate#1 → S-0136 stop-36
    const TOLERANCE = 5;     // ±5 min tolerance for schedule rounding

    const result = new Set();
    for (const g1 of gate1) {
      const expected = (g1 + OFFSET) % 1440;
      // Find an S-0136 entry within ±TOLERANCE of the expected time
      const found = s0136.find((t) => {
        const diff = Math.min(Math.abs(t - expected), 1440 - Math.abs(t - expected));
        return diff <= TOLERANCE;
      });
      if (found !== undefined) result.add(found);
    }
    return [...result].sort((a, b) => a - b);
  }

  function updateBusTracker() {
    const trackerLine = $("#bus-tracker-line");
    if (!trackerLine) return;
    const now = new Date();
    const nowMin = now.getHours() * 60 + now.getMinutes() + now.getSeconds() / 60;

    const { gate1, s0136, hovey, lastStop } = state.trackerSchedule;

    // Remove previous dynamic bus icons (keep rail and stop markers)
    trackerLine.querySelectorAll(".bus-tracker__bus--dynamic").forEach((el) => el.remove());

    if (!gate1?.length) return;

    const stopNames = ["Gate #1", "S-0136\n(Hovey)", "Hovey", "S-0136\n(Gate)", "Last"];
    const segCount = 4;

    // Exact offsets from bus schedule data (same for every trip):
    //   S-0136 Hovey-dir (row12): gate1 + 13 min
    //   Hovey stop  (row25): gate1 + 33 min
    //   S-0136 Gate-dir (row38): gate1 + 53 min
    //   Bowling Ctr (row46): gate1 + 63 min
    // Use a ±5 min tolerance window to robustly match ONLY the trip's own stop time.
    const T_S0136_HOV = 13, T_HOVEY = 33, T_S0136_GATE = 53, T_BOWL = 63, TOL = 5;

    // Find ALL Gate#1 departures whose trips are currently in progress
    const activeTrips = [];
    for (let i = 0; i < gate1.length; i++) {
      const g1 = gate1[i];
      if (g1 > nowMin) continue;
      const t1 = findNearestInRange(s0136, g1, T_S0136_HOV - TOL, T_S0136_HOV + TOL);
      const t2 = findNearestInRange(hovey,  g1, T_HOVEY     - TOL, T_HOVEY     + TOL);
      const t3 = findNearestInRange(s0136, g1, T_S0136_GATE - TOL, T_S0136_GATE + TOL);
      const t4 = findNearestInRange(lastStop, g1, T_BOWL - TOL, T_BOWL + TOL);
      if (t4 && nowMin <= t4 + 10) {
        activeTrips.push([g1, t1, t2, t3, t4]);
      }
    }

    // Deduplicate: if two trips produce nearly identical positions (< 2% apart), keep only one.
    // This guards against edge cases like duplicate gate1 times in the schedule.
    const seen = [];
    const uniqueTrips = activeTrips.filter((trip) => {
      const key = trip[0]; // gate1 time uniquely identifies a trip
      if (seen.includes(key)) return false;
      seen.push(key);
      return true;
    });

    uniqueTrips.forEach((tripTimes) => {
      // Find which segment the bus is in
      let pct = -1;
      let nextStopIdx = -1;
      for (let i = 0; i < segCount; i++) {
        const tStart = tripTimes[i];
        const tEnd   = tripTimes[i + 1];
        if (tStart == null || tEnd == null) continue;
        if (nowMin >= tStart && nowMin <= tEnd) {
          const progress = (nowMin - tStart) / (tEnd - tStart);
          pct = TRACKER_STOP_PCTS[i] + progress * (TRACKER_STOP_PCTS[i + 1] - TRACKER_STOP_PCTS[i]);
          nextStopIdx = i + 1;
          break;
        }
      }
      if (pct < 0) return;

      // Create bus icon — all buses share the same rail-center top (set via CSS)
      const busEl = document.createElement("div");
      busEl.className = "bus-tracker__bus--dynamic";
      busEl.style.left = `${Math.max(0, Math.min(100, pct))}%`;
      busEl.textContent = "🚌";

      // ETA: show minutes only (stop name is already visible on the track)
      if (nextStopIdx >= 0 && nextStopIdx < tripTimes.length) {
        const tEnd = tripTimes[nextStopIdx];
        if (tEnd != null && nowMin < tEnd) {
          const etaMin = Math.round(tEnd - nowMin);
          const etaEl = document.createElement("span");
          etaEl.className = "bus-tracker__eta";
          etaEl.textContent = state.locale === "ko" ? `→ ${etaMin}분` : `→ ${etaMin}m`;
          busEl.appendChild(etaEl);
        }
      }

      trackerLine.appendChild(busEl);
    });
  }

  /* ─── Data Fetching ─── */
  async function fetchBootstrap() {
    state.bootstrap = await api("/api/bootstrap");
    state.exchangeRate = state.bootstrap.exchange_rate;
    renderHolidayNotes(state.bootstrap.holiday_notes || {});
    fillBusStops(state.bootstrap.bus_stops || []);
    fillTrainProviders(state.bootstrap.train_providers || []);
    applyDefaultSelections();
    renderHome();
  }

  // S-0136 is a dual-direction stop; we split it into two distinct dropdown options.
  const S0136_STOP_ID        = "bus-stop-s-0136";
  const S0136_HOVEY_VALUE    = "bus-stop-s-0136__hovey";
  const S0136_GATE_VALUE     = "bus-stop-s-0136__gate";
  const S0136_HOVEY_LABEL_KO = "S-0136 (Hovey방향)";
  const S0136_GATE_LABEL_KO  = "S-0136 (Gate방향)";
  const S0136_HOVEY_LABEL_EN = "S-0136 (Hovey dir.)";
  const S0136_GATE_LABEL_EN  = "S-0136 (Gate dir.)";

  function s0136Label(direction) {
    if (direction === "hovey") return state.locale === "ko" ? S0136_HOVEY_LABEL_KO : S0136_HOVEY_LABEL_EN;
    return state.locale === "ko" ? S0136_GATE_LABEL_KO : S0136_GATE_LABEL_EN;
  }

  function fillBusStops(stops) {
    if (!dom.busStopInput) return;
    const savedStop = localStorage.getItem("camp-casey.default-bus-stop-id");
    const options = [];
    for (const s of (stops || [])) {
      if (s.stop_id === S0136_STOP_ID) {
        // Expand into two directional entries
        options.push(`<option value="${S0136_HOVEY_VALUE}"${savedStop === S0136_HOVEY_VALUE ? " selected" : ""}>${s0136Label("hovey")}</option>`);
        options.push(`<option value="${S0136_GATE_VALUE}"${savedStop === S0136_GATE_VALUE ? " selected" : ""}>${s0136Label("gate")}</option>`);
      } else {
        options.push(`<option value="${escapeHtml(s.stop_id)}"${s.stop_id === savedStop ? " selected" : ""}>${escapeHtml(s.name)}</option>`);
      }
    }
    dom.busStopInput.innerHTML = options.join("");
    // Set default to Gate#1 if no saved preference
    if (!savedStop) {
      const gate1Option = Array.from(dom.busStopInput.options).find((o) => o.value.includes("gate-1") || o.value.includes("terminal"));
      if (gate1Option) dom.busStopInput.value = gate1Option.value;
    }
  }

  function fillTrainProviders(providers) {
    dom.trainProviderInput.innerHTML = (providers || []).map((p) => `
      <option value="${escapeHtml(p.provider_id)}" ${p.available ? "" : "disabled"}>
        ${escapeHtml(p.station_name)}${p.available ? "" : ` — ${escapeHtml(p.not_available_reason || "Not available")}`}
      </option>`).join("");
  }

  function applyDefaultSelections() {
    dom.trainProviderInput.value = localStorage.getItem("camp-casey.train-provider") || "bosan";
  }

  async function fetchStores() {
    const params = new URLSearchParams();
    if (dom.storeOpenNowInput.checked) params.set("open_now", "true");
    const results = await api(`/api/stores?${params.toString()}`);
    renderStoreResults(results);
  }

  async function fetchHolidays() {
    const params = new URLSearchParams();
    if (dom.holidayConfirmedOnly?.checked) params.set("confirmed_only", "true");
    // always fetch all of 2026
    params.set("from", "2026-01-01");
    params.set("to", "2026-12-31");
    const data = await api(`/api/holidays?${params.toString()}`);
    renderHolidayResults(data.items || []);
    renderCalendar();
  }

  async function openStoreDetail(storeId) {
    try {
      const data = await api(`/api/stores/${encodeURIComponent(storeId)}`);
      renderStoreDetail(data.store, data.status);
    } catch (err) {
      showToast(err.message);
    }
  }

  async function runBusQuery(fullMode = false) {
    const today = new Date().toISOString().slice(0, 10);
    const nowMin = (new Date()).getHours() * 60 + (new Date()).getMinutes();
    const gate1Tracker = state.trackerSchedule.gate1;

    // Fetch Gate#1 data independently
    const gate1Params = new URLSearchParams({ stop: "bus-terminal-gate-1" });
    if (fullMode) gate1Params.set("date", today);
    const gate1Data = await api(fullMode ? `/api/bus/schedule?${gate1Params}` : `/api/bus/next?${gate1Params}`);

    let s0136GateData;

    if (!fullMode && gate1Tracker.length > 0 && state.trackerSchedule.s0136.length > 0) {
      // Tracker loaded → use getS0136GateTimes() with the corrected algorithm
      const allGateMins = getS0136GateTimes();

      // Build upcoming deps: include today's remaining times AND early next-day times
      // Times < nowMin could be next-day (00:xx, 01:xx); include them with is_next_day=true
      const upcoming = [];
      for (const t of allGateMins) {
        const cdMin = t >= nowMin ? Math.round(t - nowMin) : Math.round(t + 1440 - nowMin);
        if (cdMin < 0 || cdMin > 300) continue; // skip too-far or already-passed
        upcoming.push({ t, cdMin, isNextDay: t < nowMin });
      }
      upcoming.sort((a, b) => a.cdMin - b.cdMin);

      const synthDeps = upcoming.slice(0, 5).map(({ t, cdMin, isNextDay }) => {
        const h = String(Math.floor(t / 60) % 24).padStart(2, "0");
        const m = String(Math.round(t % 60)).padStart(2, "0");
        const cdLabel = cdMin <= 1
          ? (state.locale === "ko" ? "곧 도착" : "Now")
          : (state.locale === "ko" ? `약 ${cdMin}분 후` : `~${cdMin}m`);
        return { time: `${h}:${m}:00`, countdown_label: cdLabel, is_next_day: isNextDay };
      });

      s0136GateData = {
        stop: { name: s0136Label("gate") },
        service_profile_label: gate1Data.service_profile_label || "",
        day_type: gate1Data.day_type,
        departures: synthDeps,
        available: synthDeps.length > 0,
        message: synthDeps.length === 0 ? (state.locale === "ko" ? "오늘 남은 버스 없음" : "No more buses today") : undefined,
      };
    } else {
      // Full schedule mode or tracker not yet loaded → show all S-0136 times (unfiltered)
      // When tracker unavailable we can't distinguish direction; show all as placeholder
      const s0136Params = new URLSearchParams({ stop: S0136_STOP_ID });
      if (fullMode) s0136Params.set("date", today);
      else s0136Params.set("count", "10");
      const s0136Raw = await api(fullMode ? `/api/bus/schedule?${s0136Params}` : `/api/bus/next?${s0136Params}`);
      s0136GateData = {
        ...s0136Raw,
        stop: { ...(s0136Raw.stop || {}), name: s0136Label("gate") },
        // No filtering when tracker data unavailable - show best-effort
      };
    }

    if (dom.busResultsGate1)     renderBusResults(gate1Data, fullMode, dom.busResultsGate1);
    if (dom.busResultsS0136Gate) renderBusResults(s0136GateData, fullMode, dom.busResultsS0136Gate);
    toggleQueryButtons("#bus-submit", "#bus-show-full", fullMode);
  }

  async function runTrainQuery(fullMode = false) {
    const provider = dom.trainProviderInput.value;
    const params = new URLSearchParams();
    params.set("provider", provider);
    if (fullMode) params.set("date", new Date().toISOString().slice(0, 10));
    const data = await api(fullMode ? `/api/train/schedule?${params}` : `/api/train/next?${params}`);
    renderTrainResults(data, fullMode);
    toggleQueryButtons("#train-submit", "#train-show-full", fullMode);
  }

  function toggleQueryButtons(nextSel, fullSel, fullMode) {
    const nextBtn = $(nextSel);
    const fullBtn = $(fullSel);
    if (!nextBtn || !fullBtn) return;
    nextBtn.classList.toggle("is-active", !fullMode);
    nextBtn.classList.toggle("btn--primary", !fullMode);
    nextBtn.classList.toggle("btn--secondary", fullMode);
    fullBtn.classList.toggle("is-active", fullMode);
    fullBtn.classList.toggle("btn--primary", fullMode);
    fullBtn.classList.toggle("btn--secondary", !fullMode);
  }


  function activateTab(panelId, tabId) {
    $$("[role=tab]").forEach((tab) => {
      const active = tab.id === tabId;
      tab.classList.toggle("is-active", active);
      tab.setAttribute("aria-selected", String(active));
    });
    $$(".tab-panel").forEach((panel) => panel.classList.toggle("is-active", panel.id === panelId));
  }

  /* ─── Event Binding ─── */
  function bindEvents() {
    // Locale
    $$("[data-locale-switch]").forEach((btn) => btn.addEventListener("click", () => setLocale(btn.dataset.localeSwitch)));

    // Currency
    $$("[data-currency-mode]").forEach((btn) => btn.addEventListener("click", () => setCurrencyMode(btn.dataset.currencyMode)));

    // Scroll targets (outside home cards)
    $$("[data-scroll-target]").forEach((btn) => btn.addEventListener("click", () => scrollToSection(btn.dataset.scrollTarget)));

    // Quick chips (suggest query → chat)
    $$(".chip[data-suggest-query]").forEach((btn) => btn.addEventListener("click", () => {
      const query = btn.dataset.suggestQuery;
      dom.chatInput.value = query;
      runChat(query);
    }));

    // Bus form
    $("#bus-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      setLoading($("#bus-submit"), true);
      try { await runBusQuery(false); } catch (err) { showToast(err.message); } finally { setLoading($("#bus-submit"), false); }
    });

    $("#bus-show-full").addEventListener("click", async () => {
      setLoading($("#bus-show-full"), true);
      try { await runBusQuery(true); } catch (err) { showToast(err.message); } finally { setLoading($("#bus-show-full"), false); }
    });

    // Train form
    $("#train-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      localStorage.setItem("camp-casey.train-provider", dom.trainProviderInput.value);
      setLoading($("#train-submit"), true);
      try { await runTrainQuery(false); } catch (err) { showToast(err.message); } finally { setLoading($("#train-submit"), false); }
    });

    $("#train-show-full").addEventListener("click", async () => {
      setLoading($("#train-show-full"), true);
      try { await runTrainQuery(true); } catch (err) { showToast(err.message); } finally { setLoading($("#train-show-full"), false); }
    });

    // Store filter
    $("#store-filter-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      setLoading($("#store-filter-submit"), true);
      try { await fetchStores(); } catch (err) { showToast(err.message); } finally { setLoading($("#store-filter-submit"), false); }
    });

    // Holiday filter
    dom.holidayConfirmedOnly?.addEventListener("change", () => fetchHolidays().catch((e) => showToast(e.message)));

    // Calendar month pager
    $("#cal-prev-btn")?.addEventListener("click", () => {
      state.calendarMonth -= 1;
      if (state.calendarMonth < 0) { state.calendarMonth = 11; state.calendarYear -= 1; }
      renderCalendar();
    });
    $("#cal-next-btn")?.addEventListener("click", () => {
      state.calendarMonth += 1;
      if (state.calendarMonth > 11) { state.calendarMonth = 0; state.calendarYear += 1; }
      renderCalendar();
    });

    // Exchange: refresh from Naver API
    dom.exchangeRefreshBtn?.addEventListener("click", () => refreshExchangeRate());

    // Converter
    dom.converterAmountInput.addEventListener("input", renderConverter);
    dom.converterDirectionInput.addEventListener("change", renderConverter);

    // Chat
    dom.chatForm.addEventListener("submit", (e) => {
      e.preventDefault();
      const query = dom.chatInput.value.trim();
      if (!query) return;
      runChat(query);
      dom.chatInput.value = "";
    });

    $("#chat-clear").addEventListener("click", async () => {
      // 서버 세션 히스토리 초기화
      try {
        await api(`/api/chat/session/${encodeURIComponent(state.sessionId)}`, { method: "DELETE" });
      } catch (_) { /* 무시 */ }
      // 새 세션 ID 발급
      state.sessionId = generateSessionId();
      localStorage.setItem("camp-casey.session-id", state.sessionId);
      // 화면 초기화
      dom.chatLog.innerHTML = `<div class="empty-state"><h3>${t("chat.emptyTitle")}</h3><p>${t("chat.emptyBody")}</p></div>`;
    });

    // Store dialog
    dom.storeDialog?.addEventListener("close", () => { dom.storeDialogBody.innerHTML = ""; });

    // Tabs
    $$("[data-tab-target]").forEach((tab) => {
      tab.addEventListener("click", () => activateTab(tab.dataset.tabTarget, tab.id));
      tab.addEventListener("keydown", (e) => {
        const tabs = $$("[role=tab]");
        const idx = tabs.indexOf(tab);
        if (e.key === "ArrowRight") { e.preventDefault(); const n = tabs[(idx + 1) % tabs.length]; activateTab(n.dataset.tabTarget, n.id); n.focus(); }
        if (e.key === "ArrowLeft") { e.preventDefault(); const p = tabs[(idx - 1 + tabs.length) % tabs.length]; activateTab(p.dataset.tabTarget, p.id); p.focus(); }
      });
    });

    // Keyboard shortcut: / → chat input
    document.addEventListener("keydown", (e) => {
      if (e.key === "/" && !["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement?.tagName)) {
        e.preventDefault();
        dom.chatInput.focus();
        scrollToSection("chat");
      }
    });
  }

  /* ─── Init ─── */
  async function init() {
    updateLocaleButtons();
    updateCurrencyButtons();

    // Start 1-second clock immediately
    setInterval(updateHeaderClock, 1000);
    updateHeaderClock();

    bindEvents();

    await loadTranslations();
    applyTranslations();

    try {
      await fetchBootstrap();
      updateHeaderClock(); // re-render with day type

      await Promise.all([
        fetchStores(),
        fetchHolidays(),
        fetchDualStops(),
        fetchHomeGate1(),
        runBusQuery(false).catch(() => {}),
        runTrainQuery(false).catch(() => {}),
        fetchTrackerSchedules(),
      ]);

      // Polling: dual stops + tracker + home bus every 60s
      setInterval(async () => {
        await fetchDualStops().catch(() => {});
        await fetchHomeGate1().catch(() => {});
        updateBusTracker();
      }, 60_000);

      // Polling: bus/train results every 60s
      setInterval(() => {
        runBusQuery(false).catch(() => {});
        runTrainQuery(false).catch(() => {});
      }, 60_000);

      // Polling: stores every 60s
      setInterval(() => fetchStores().catch(() => {}), 60_000);

      // Polling: bootstrap (day type, open stores) every 5 min
      setInterval(async () => {
        try { await fetchBootstrap(); } catch {}
      }, 300_000);

      // Tracker position update every 30s
      setInterval(updateBusTracker, 30_000);

    } catch (err) {
      showToast(err.message);
    }
  }

  init();
})();
