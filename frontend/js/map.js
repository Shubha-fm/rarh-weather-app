// Station map: a plain latitude/longitude grid with the reference stations and the chosen point.
(function () {
  const RW = (window.RW = window.RW || {});
  const LON0 = 83.6, LON1 = 89.2, LAT0 = 21.8, LAT1 = 25.6, W = 400, H = 300;
  const X = (lon) => ((lon - LON0) / (LON1 - LON0)) * W;
  const Y = (lat) => ((LAT1 - lat) / (LAT1 - LAT0)) * H;

  function km(lat1, lon1, lat2, lon2) {
    const r = Math.PI / 180, dl = (lat2 - lat1) * r, dg = (lon2 - lon1) * r;
    const h = Math.sin(dl / 2) ** 2 + Math.cos(lat1 * r) * Math.cos(lat2 * r) * Math.sin(dg / 2) ** 2;
    return 2 * 6371 * Math.asin(Math.sqrt(h));
  }

  function nearestIndex(stations, lat, lon) {
    let best = -1, bestKm = Infinity;
    stations.forEach((s, i) => {
      const d = km(lat, lon, s.latitude, s.longitude);
      if (d < bestKm) { bestKm = d; best = i; }
    });
    return best;
  }

  // point: {latitude, longitude} or null. lang: "en" | "bn" | "hi".
  function draw(svg, stations, point, lang) {
    let s = "";
    for (let lo = 84; lo <= 89; lo++) {
      s += `<line class="m-grid" x1="${X(lo)}" x2="${X(lo)}" y1="0" y2="${H}"/><text x="${X(lo) + 3}" y="${H - 4}" font-size="9">${lo}°E</text>`;
    }
    for (let la = 22; la <= 25; la++) {
      s += `<line class="m-grid" x1="0" x2="${W}" y1="${Y(la)}" y2="${Y(la)}"/><text x="3" y="${Y(la) - 3}" font-size="9">${la}°N</text>`;
    }
    const inBox = point && point.latitude >= LAT0 && point.latitude <= LAT1 && point.longitude >= LON0 && point.longitude <= LON1;
    const near = point && stations.length ? nearestIndex(stations, point.latitude, point.longitude) : -1;
    stations.forEach((st, i) => {
      const x = X(st.longitude), y = Y(st.latitude), onRight = x > 320, isNear = i === near && inBox;
      s += `<circle class="m-st" cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="${isNear ? 4 : 3}"/>` +
        `<text class="m-lab${isNear ? " m-near-lab" : ""}" x="${(onRight ? x - 6 : x + 6).toFixed(1)}" y="${(y + 3.2).toFixed(1)}" text-anchor="${onRight ? "end" : "start"}">${st.name[lang]}</text>`;
    });
    if (inBox) {
      const px = X(point.longitude), py = Y(point.latitude);
      if (near >= 0) {
        s += `<line class="m-link" x1="${px}" y1="${py}" x2="${X(stations[near].longitude)}" y2="${Y(stations[near].latitude)}"/>`;
      }
      s += `<circle class="m-halo" cx="${px}" cy="${py}" r="13"/><circle class="m-pt" cx="${px}" cy="${py}" r="5.5"/>`;
    }
    svg.innerHTML = s;
  }

  RW.map = { draw };
})();
