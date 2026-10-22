// Point GitHub Pages to the hosted API by changing the URL below after Render deployment.
// You can also configure it without editing code: open the site once with
// ?api=https://YOUR-BACKEND.onrender.com/api/v1 (stored in this browser).
(function () {
  window.RW = window.RW || {};
  const DEFAULT_PUBLIC_API = "https://YOUR-BACKEND.onrender.com/api/v1";
  let configured = "";
  try {
    const query = new URLSearchParams(window.location.search).get("api");
    if (query && /^https:\/\/[^\s/]+\/api\/v1\/?$/.test(query)) {
      localStorage.setItem("rw_api_base", query.replace(/\/$/, ""));
    }
    configured = localStorage.getItem("rw_api_base") || "";
  } catch (e) { /* Storage might be disabled. */ }
  const local = ["localhost", "127.0.0.1"].includes(window.location.hostname);
  window.RW.CONFIG = {
    API_BASE: configured || (local ? "http://localhost:8000/api/v1" : (window.location.hostname.endsWith("onrender.com") ? window.location.origin + "/api/v1" : DEFAULT_PUBLIC_API))
  };
})();
