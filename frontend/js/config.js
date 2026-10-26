// Where the backend API lives.
//  - When the backend serves this page (a hosted site, or http://localhost:8000), the API is on the same address.
//  - When the page is opened from the file system or from a separate local server (for example
//    "python -m http.server 5500"), the API is the backend running on this computer.
// If you host the API on a different address from the page, set API_BASE to it,
// for example "https://api.example.org/api/v1", and set CORS_ORIGINS on the backend to the page's address.
(function () {
  const isLocalFile = location.protocol === "file:";
  const isOtherLocalServer = ["localhost", "127.0.0.1"].includes(location.hostname) && location.port !== "8000";
  window.RW = window.RW || {};
  window.RW.CONFIG = {
    API_BASE: isLocalFile || isOtherLocalServer ? "http://localhost:8000/api/v1" : "/api/v1",
  };
})();
