// API client. The only file that talks to the backend.
(function () {
  const RW = (window.RW = window.RW || {});

  class ApiError extends Error {
    constructor(code, message, status) {
      super(message);
      this.code = code; // "network", "server_error", or a code from the API such as "wrong_credentials"
      this.status = status;
    }
  }

  // ---- login session (kept in the browser so a refresh does not log the farmer out) ----
  let token = null;
  try { token = localStorage.getItem("rw_token"); } catch (e) { /* storage blocked: the session lasts until the page closes */ }

  function setSession(newToken) {
    token = newToken;
    try { localStorage.setItem("rw_token", newToken); } catch (e) { /* ignore */ }
  }
  function clearSession() {
    token = null;
    try { localStorage.removeItem("rw_token"); } catch (e) { /* ignore */ }
  }

  async function request(path, options, needsLogin) {
    options = options || {};
    const headers = Object.assign({}, options.headers);
    if (needsLogin && token) headers["Authorization"] = "Bearer " + token;

    let res;
    try {
      res = await fetch(RW.CONFIG.API_BASE + path, Object.assign({}, options, { headers }));
    } catch (e) {
      throw new ApiError("network", "Cannot reach the server.", 0);
    }
    let body = null;
    try { body = await res.json(); } catch (e) { /* not JSON */ }

    if (!res.ok) {
      const err = body && body.error;
      const error = new ApiError(err ? err.code : "server_error", err ? err.message : "Server error.", res.status);
      if (needsLogin && res.status === 401 && typeof RW.api.onUnauthorized === "function") RW.api.onUnauthorized(error.code);
      throw error;
    }
    return body;
  }

  const post = (data) => ({ method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) });

  RW.api = {
    ApiError,
    onUnauthorized: null, // the app sets this: called when the server says the login is missing or expired
    hasToken: () => !!token,
    setSession,
    clearSession,

    // public
    health: () => request("/health"),
    stations: () => request("/stations").then((b) => b.stations),

    // accounts
    register: (data) => request("/auth/register", post(data)),
    login: (data) => request("/auth/login", post(data)),
    me: () => request("/auth/me", {}, true).then((b) => b.user),

    // need login
    predict: (data) => request("/predict", post(data), true),
    markets: () => request("/markets", {}, true),
    prices: ({ market, date }) =>
      request("/prices?market=" + encodeURIComponent(market) + "&date=" + encodeURIComponent(date), {}, true),
  };
})();
