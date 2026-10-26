// Screens and behaviour. Every prediction and price comes from the backend API.
//
// Flow:  register -> your user ID -> log in -> choose language -> home -> weather prediction / market prices
(function () {
  const RW = window.RW;
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  const QUICK_IDS = ["kolkata", "asansol", "bankura", "purulia", "ranchi", "jamshedpur", "dhanbad", "deoghar"];
  const CONF_COLOR = { high: "var(--ok)", medium: "var(--warn)", low: "var(--bad)" };
  const AUTH_STAGES = ["login", "register", "registered"];
  const MAIN_STAGES = ["home", "form", "result", "market"];

  const state = {
    lang: "en",
    stage: "login",
    conn: "connecting", // connecting | ready | offline
    user: null, // {user_id, name, phone_hint} once logged in
    stations: [],
    point: null, // {latitude, longitude} typed in the form
    activeChip: "ranchi",
    result: null, // last response from POST /predict
    market: { list: [], id: "ranchi", group: "all", sort: "price", data: null },
    newUserId: "",
  };

  const tr = (k) => RW.T[state.lang][k];
  const fmt = (s, o) => s.replace(/\{(\w+)\}/g, (_, k) => o[k]);
  const dateText = (d, opts) => {
    try { return new Intl.DateTimeFormat(RW.LOCALES[state.lang], opts).format(d); }
    catch (e) { return new Intl.DateTimeFormat("en-IN", opts).format(d); }
  };

  /* ---------- three-language text, for screens shown before the farmer picks a language ---------- */
  function triHtml(key, stack, vars) {
    const part = (l) => esc(vars ? fmt(RW.T[l][key], vars) : RW.T[l][key]);
    if (stack) {
      return `<span class="t1" lang="en">${part("en")}</span><span class="t3" lang="bn">${part("bn")}</span><span class="t3" lang="hi">${part("hi")}</span>`;
    }
    return `<span class="t1" lang="en">${part("en")}</span><span class="t2"><span lang="bn">${part("bn")}</span> · <span lang="hi">${part("hi")}</span></span>`;
  }
  function renderTri() {
    document.querySelectorAll("[data-tri]").forEach((el) => { el.innerHTML = triHtml(el.dataset.tri, el.hasAttribute("data-stack")); });
  }
  const showTriError = (id, key) => { $(id).innerHTML = triHtml(key, true); };
  const clearErr = (id) => { $(id).innerHTML = ""; };

  /* ---------- server connection ---------- */
  function renderStatus() {
    $("dot").className = "dot" + (state.conn === "ready" ? " ready" : state.conn === "offline" ? " off" : " busy");
    $("status").textContent = tr({ connecting: "srvConn", ready: "srvReady", offline: "srvOff" }[state.conn]);
  }

  async function connect() {
    try {
      const health = await RW.api.health();
      if (!health.model_ready) throw new Error("model not ready");
      state.stations = await RW.api.stations();
      state.conn = "ready";
    } catch (e) {
      state.conn = "offline";
      setTimeout(connect, 4000);
      renderStatus();
      return;
    }
    renderStatus();
    renderChips();
    drawMap();
    renderFacts();
    restoreSession();
  }

  // A farmer who logged in recently skips straight to the language step.
  async function restoreSession() {
    if (state.user || !RW.api.hasToken()) return;
    try {
      state.user = await RW.api.me();
      if (state.stage === "login") { renderUser(); show("lang"); }
    } catch (e) {
      RW.api.clearSession();
    }
  }

  /* ---------- screens ---------- */
  function show(stage) {
    state.stage = stage;
    const auth = AUTH_STAGES.includes(stage), main = MAIN_STAGES.includes(stage);
    $("stage-auth").hidden = !auth;
    AUTH_STAGES.forEach((k) => { $(k).hidden = k !== stage; });
    $("stage-lang").hidden = stage !== "lang";
    $("stage-main").hidden = !main;
    $("stage-main").classList.toggle("wide", stage === "market");
    MAIN_STAGES.forEach((k) => { $(k).hidden = k !== stage; });
    $("langsw").hidden = !main;
    $("userbox").hidden = !state.user;
    window.scrollTo(0, 0);
  }

  function renderUser() {
    if (!state.user) return;
    $("u-name").textContent = state.user.name;
    $("u-id").textContent = state.user.user_id;
    $("hm-greet").textContent = fmt(tr("greet"), { name: state.user.name });
    $("lang-welcome").innerHTML = triHtml("welcome", true, { name: state.user.name });
  }

  function renderFacts() {
    $("fact-st").textContent = state.stations.length ? fmt(tr("factSt"), { n: state.stations.length }) : "";
    $("fact-ml").textContent = tr("factMl");
  }

  function applyLang() {
    document.documentElement.lang = state.lang;
    document.querySelectorAll("[data-i]").forEach((e) => { e.textContent = tr(e.dataset.i); });
    document.querySelectorAll("#langsw button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.l === state.lang)));
    renderStatus();
    renderFacts();
    renderUser();
    renderChips();
    drawMap();
    if (state.stage === "result" && state.result) renderResult();
    if (state.stage === "market") { renderMarketControls(); renderMarket(); }
  }

  function setLang(l) { state.lang = l; applyLang(); }

  /* ---------- accounts ---------- */
  function saveSession(token, user) {
    RW.api.setSession(token);
    state.user = user;
    renderUser();
  }

  function logout(errKey) {
    RW.api.clearSession();
    state.user = null;
    state.result = null;
    state.market.data = null;
    $("lg-pw").value = "";
    clearErr("lg-err");
    if (errKey) showTriError("lg-err", errKey);
    show("login");
  }

  RW.api.onUnauthorized = () => { if (state.user) logout("errSession"); };

  async function onLogin(e) {
    e.preventDefault();
    clearErr("lg-err");
    const userId = $("lg-id").value.trim(), password = $("lg-pw").value;
    if (!userId) return showTriError("lg-err", "errUserId");
    if (!password) return showTriError("lg-err", "errCreds");
    const btn = $("lg-submit");
    btn.disabled = true;
    try {
      const r = await RW.api.login({ user_id: userId, password });
      saveSession(r.token, r.user);
      $("lg-pw").value = "";
      show("lang");
    } catch (ex) {
      showTriError("lg-err", RW.ERROR_KEYS[ex.code] || "errServer");
    } finally {
      btn.disabled = false;
    }
  }

  async function onRegister(e) {
    e.preventDefault();
    clearErr("rg-err");
    const name = $("rg-name").value.trim().replace(/\s+/g, " ");
    let phone = $("rg-phone").value.replace(/[\s-]/g, "");
    phone = phone.replace(/^\+91/, "").replace(/^91(?=\d{10}$)/, "").replace(/^0(?=\d{10}$)/, "");
    const password = $("rg-pw").value;
    if (name.length < 2 || name.length > 60 || /[<>]/.test(name)) return showTriError("rg-err", "errName");
    if (!/^[6-9]\d{9}$/.test(phone)) return showTriError("rg-err", "errPhone");
    if (password.length < 6) return showTriError("rg-err", "errPw");

    const btn = $("rg-submit");
    btn.disabled = true;
    try {
      const r = await RW.api.register({ name, phone, password });
      state.newUserId = r.user_id;
      $("new-uid").textContent = r.user_id;
      $("copy-note").textContent = "";
      $("register-form").reset();
      show("registered");
    } catch (ex) {
      showTriError("rg-err", RW.ERROR_KEYS[ex.code] || "errServer");
    } finally {
      btn.disabled = false;
    }
  }

  async function copyId() {
    const note = $("copy-note");
    try {
      await navigator.clipboard.writeText(state.newUserId);
      note.textContent = RW.T.en.copied + " · " + RW.T.bn.copied + " · " + RW.T.hi.copied;
    } catch (e) {
      // Clipboard blocked: select the ID so it can be copied by hand.
      const range = document.createRange();
      range.selectNodeContents($("new-uid"));
      const sel = window.getSelection();
      sel.removeAllRanges();
      sel.addRange(range);
    }
  }

  function togglePassword(btn) {
    const input = $(btn.dataset.toggle), showing = input.type === "text";
    input.type = showing ? "password" : "text";
    btn.firstElementChild.innerHTML = triHtml(showing ? "show" : "hide");
  }

  /* ---------- weather form ---------- */
  function today() {
    const d = new Date();
    return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0");
  }

  function readPoint() {
    const la = parseFloat($("lat").value), lo = parseFloat($("lon").value);
    state.point = isFinite(la) && isFinite(lo) ? { latitude: la, longitude: lo } : null;
    return state.point;
  }

  function renderChips() {
    const box = $("chips");
    box.innerHTML = "";
    QUICK_IDS.map((id) => state.stations.find((s) => s.id === id)).filter(Boolean).forEach((s) => {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "chip";
      b.textContent = s.name[state.lang];
      b.setAttribute("aria-pressed", String(s.id === state.activeChip));
      b.addEventListener("click", () => {
        $("lat").value = s.latitude;
        $("lon").value = s.longitude;
        state.activeChip = s.id;
        renderChips();
        readPoint();
        drawMap();
      });
      box.appendChild(b);
    });
  }

  function drawMap() {
    RW.map.draw($("map"), state.stations, state.point, state.lang);
    $("map").setAttribute("aria-label", tr("mapTitle"));
    $("map-coord").textContent = state.point ? state.point.latitude.toFixed(2) + "°N " + state.point.longitude.toFixed(2) + "°E" : "";
  }

  async function onPredict(e) {
    e.preventDefault();
    const err = $("err"), btn = $("submit");
    err.textContent = "";
    const p = readPoint();
    if (!p) { err.textContent = tr("errNum"); return; }
    if (p.latitude < 20 || p.latitude > 27 || p.longitude < 82 || p.longitude > 90) { err.textContent = tr("errRange"); return; }
    const date = $("date").value;
    if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) { err.textContent = tr("errDate"); return; }

    btn.disabled = true;
    btn.setAttribute("aria-busy", "true");
    try {
      state.result = await RW.api.predict({ latitude: p.latitude, longitude: p.longitude, date });
      show("result");
      renderResult();
    } catch (ex) {
      if (state.user) err.textContent = tr(RW.ERROR_KEYS[ex.code] || "errServer");
    } finally {
      btn.disabled = false;
      btn.removeAttribute("aria-busy");
    }
  }

  /* ---------- weather result ---------- */
  function renderResult() {
    const r = state.result, p = r.prediction;
    const [y, m, d] = r.date.split("-").map(Number);
    const when = new Date(y, m - 1, d);

    $("rs-where").textContent =
      r.location.latitude.toFixed(2) + "°N " + r.location.longitude.toFixed(2) + "°E · " +
      dateText(when, { weekday: "short", day: "numeric", month: "short", year: "numeric" });
    $("rs-cond").textContent = tr(RW.CONDITION_KEYS[r.condition]);
    const gloss = tr("ssnG")[r.season.index];
    $("rs-season").textContent = tr("ssn")[r.season.index] + (gloss ? " (" + gloss + ")" : "");

    const advice = (r.advice || []).filter((code) => tr("a_" + code));
    $("rs-advice-box").hidden = advice.length === 0;
    $("rs-advice").innerHTML = advice.map((code) => "<li>" + esc(tr("a_" + code)) + "</li>").join("");

    $("rs-hi").textContent = Math.round(p.temp_max_c) + "°";
    $("rs-lo").textContent = Math.round(p.temp_min_c) + "°";
    const rainPct = Math.round(p.rain_probability * 100);
    $("v-rain").textContent = rainPct + "%";
    $("b-rain").style.width = rainPct + "%";
    $("v-hum").textContent = Math.round(p.humidity_pct) + "%";
    $("b-hum").style.width = Math.round(p.humidity_pct) + "%";
    $("v-amt").textContent = (p.rain_mm_per_day < 0.1 ? "0" : p.rain_mm_per_day.toFixed(1)) + " " + tr("mm");

    $("ribbon").innerHTML = tr("ssn")
      .map((n, i) => "<div" + (i === r.season.index ? ' class="on" aria-current="true"' : "") + ">" + esc(n) + "</div>")
      .join("");

    $("m-near").textContent = r.nearest_station.name[state.lang] + ", " + Math.round(r.nearest_station.distance_km) + " " + tr("km");
    const level = r.confidence;
    $("m-conf").innerHTML = '<i class="cdot" style="background:' + CONF_COLOR[level] + '"></i>' + esc(tr("conf" + level[0].toUpperCase() + level.slice(1)));
    $("m-model").textContent = fmt(tr("modelLine"), { x: r.model.validation_mae_c.toFixed(1) });
    $("note").textContent = fmt(tr("note"), { n: state.stations.length || 17 });

    RW.chart.draw($("chart"), r.yearly, r.day_of_year, {
      aria: tr("chartTitle"),
      hiLabel: tr("hiS"),
      loLabel: tr("loS"),
      monthLabel: (i) => dateText(new Date(2026, i, 1), { month: "short" }),
      onReadout: (day, hi, lo) => {
        $("readout").textContent =
          dateText(new Date(2026, 0, day), { day: "numeric", month: "short" }) +
          " · " + tr("hiS") + " " + Math.round(hi) + "° · " + tr("loS") + " " + Math.round(lo) + "°";
      },
    });
  }

  /* ---------- market prices ---------- */
  function renderMarketControls() {
    const box = $("mk-markets");
    box.innerHTML = "";
    state.market.list.forEach((m) => {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "chip";
      b.textContent = m.name[state.lang];
      b.setAttribute("aria-pressed", String(m.id === state.market.id));
      b.addEventListener("click", () => { state.market.id = m.id; renderMarketControls(); loadPrices(); });
      box.appendChild(b);
    });
    document.querySelectorAll("#mk-tabs button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.g === state.market.group)));
    document.querySelectorAll("#mk-sort button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.s === state.market.sort)));
  }

  async function openMarket() {
    show("market");
    $("mk-err").textContent = "";
    try {
      if (!state.market.list.length) {
        const r = await RW.api.markets();
        state.market.list = r.markets;
        if (!r.markets.some((m) => m.id === state.market.id)) state.market.id = r.markets[0].id;
      }
      renderMarketControls();
      await loadPrices();
    } catch (ex) {
      if (state.user) $("mk-err").textContent = tr(RW.ERROR_KEYS[ex.code] || "errServer");
    }
  }

  async function loadPrices() {
    $("mk-err").textContent = "";
    $("mk-list").setAttribute("aria-busy", "true");
    try {
      state.market.data = await RW.api.prices({ market: state.market.id, date: today() });
      renderMarket();
    } catch (ex) {
      if (state.user) $("mk-err").textContent = tr(RW.ERROR_KEYS[ex.code] || "errServer");
    } finally {
      $("mk-list").removeAttribute("aria-busy");
    }
  }

  function renderMarket() {
    const data = state.market.data;
    if (!data) return;
    const when = (() => { const [y, m, d] = (data.source === "agmarknet" ? data.price_date : data.date).split("-").map(Number); return new Date(y, m - 1, d); })();
    const dateLong = dateText(when, { weekday: "long", day: "numeric", month: "long", year: "numeric" });
    $("mk-date").textContent = data.market.name[state.lang] + " · " + dateLong;

    const banner = $("mk-banner");
    banner.hidden = false;
    banner.classList.toggle("live", data.source === "agmarknet");
    $("mk-banner-t").textContent =
      data.source === "agmarknet" ? fmt(tr("bannerLive"), { date: dateLong }) : tr(data.note ? "bannerFallback" : "bannerSample");

    const out = RW.market.render(data, { lang: state.lang, group: state.market.group, sort: state.market.sort, t: tr });
    $("mk-movers").innerHTML = out.movers;
    $("mk-list").innerHTML = out.count ? out.rows : '<li class="muted" style="padding:16px 0">' + esc(tr("noPrices")) + "</li>";
    $("mk-sort").querySelector('[data-s="change"]').hidden = !out.hasChange;
    if (!out.hasChange && state.market.sort === "change") { state.market.sort = "price"; renderMarketControls(); renderMarket(); }
  }

  /* ---------- wiring ---------- */
  document.querySelectorAll(".lang-card").forEach((b) => b.addEventListener("click", () => { setLang(b.dataset.l); show("home"); }));
  document.querySelectorAll("#langsw button").forEach((b) => b.addEventListener("click", () => setLang(b.dataset.l)));
  document.querySelectorAll("[data-toggle]").forEach((b) => b.addEventListener("click", () => togglePassword(b)));

  $("login-form").addEventListener("submit", onLogin);
  $("register-form").addEventListener("submit", onRegister);
  $("to-register").addEventListener("click", () => { clearErr("rg-err"); show("register"); });
  $("to-login-from-register").addEventListener("click", () => { clearErr("lg-err"); show("login"); });
  $("copy-id").addEventListener("click", copyId);
  $("to-login").addEventListener("click", () => {
    $("lg-id").value = state.newUserId;
    clearErr("lg-err");
    show("login");
    $("lg-pw").focus();
  });
  $("logout").addEventListener("click", () => logout());

  $("home-back").addEventListener("click", () => show("lang"));
  $("go-form").addEventListener("click", () => show("form"));
  $("go-market").addEventListener("click", openMarket);
  $("form-back").addEventListener("click", () => show("home"));
  $("again").addEventListener("click", () => show("form"));
  $("result-home").addEventListener("click", () => show("home"));
  $("market-back").addEventListener("click", () => show("home"));
  $("f").addEventListener("submit", onPredict);
  ["lat", "lon"].forEach((id) => {
    $(id).addEventListener("input", () => { state.activeChip = null; renderChips(); readPoint(); drawMap(); });
    $(id).addEventListener("focus", (e) => e.target.select());
  });
  $("mk-tabs").addEventListener("click", (e) => {
    const b = e.target.closest("button[data-g]");
    if (b) { state.market.group = b.dataset.g; renderMarketControls(); renderMarket(); }
  });
  $("mk-sort").addEventListener("click", (e) => {
    const b = e.target.closest("button[data-s]");
    if (b) { state.market.sort = b.dataset.s; renderMarketControls(); renderMarket(); }
  });

  $("date").value = today();
  readPoint();
  renderTri();
  applyLang();
  show("login");
  connect();
})();
