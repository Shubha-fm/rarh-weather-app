// Year chart: daily high and low temperature for the chosen place, with a marker you can drag across the year.
(function () {
  const RW = (window.RW = window.RW || {});

  // yearly: [{day, temp_max_c, temp_min_c}] from the API.
  // opts: {aria, hiLabel, loLabel, monthLabel(i), onReadout(day, tmax, tmin)}
  function draw(container, yearly, doy, opts) {
    const W = 560, H = 232, L = 36, R = 486, Tp = 14, Bt = 196;
    const MID = [16, 45.5, 75, 105.5, 136, 166.5, 197, 228, 258.5, 289, 319.5, 350];

    let lo = Infinity, hi = -Infinity;
    yearly.forEach((p) => { lo = Math.min(lo, p.temp_min_c); hi = Math.max(hi, p.temp_max_c); });
    const y0 = Math.floor((lo - 1) / 5) * 5, y1 = Math.ceil((hi + 1) / 5) * 5;
    const X = (d) => L + ((d - 1) / 364) * (R - L);
    const Y = (v) => Bt - ((v - y0) / (y1 - y0)) * (Bt - Tp);
    const path = (key) => yearly.map((p, i) => (i ? "L" : "M") + X(p.day).toFixed(1) + " " + Y(p[key]).toFixed(1)).join("");
    const back = yearly.slice().reverse().map((p) => "L" + X(p.day).toFixed(1) + " " + Y(p.temp_min_c).toFixed(1)).join("");

    let grid = "";
    for (let v = y0; v <= y1; v += 5) {
      grid += `<line class="c-grid" x1="${L}" x2="${R}" y1="${Y(v)}" y2="${Y(v)}"/><text x="${L - 6}" y="${Y(v) + 3.5}" text-anchor="end">${v}°</text>`;
    }
    let months = "";
    MID.forEach((m, i) => {
      months += `<text x="${X(m).toFixed(1)}" y="${H - 12}" text-anchor="middle">${opts.monthLabel(i)}</text>`;
    });
    const last = yearly[yearly.length - 1];

    container.innerHTML =
      `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${opts.aria}">${grid}${months}` +
      `<path class="c-band" d="${path("temp_max_c")}${back}Z"/>` +
      `<path class="c-hi" d="${path("temp_max_c")}"/><path class="c-lo" d="${path("temp_min_c")}"/>` +
      `<text class="t-hi" x="${R + 6}" y="${Y(last.temp_max_c) + 4}">${opts.hiLabel}</text>` +
      `<text class="t-lo" x="${R + 6}" y="${Y(last.temp_min_c) + 4}">${opts.loLabel}</text>` +
      `<line class="c-mk" id="mk" x1="0" x2="0" y1="${Tp}" y2="${Bt}"/>` +
      `<circle class="c-dh" id="mh" r="4.5" cx="0" cy="0"/><circle class="c-dl" id="ml" r="4.5" cx="0" cy="0"/></svg>`;

    // Temperature at any day, read from the points the API sent (straight line between neighbours).
    function at(day) {
      let i = 0;
      while (i < yearly.length - 2 && yearly[i + 1].day <= day) i++;
      const a = yearly[i], b = yearly[i + 1], t = b.day === a.day ? 0 : Math.min(1, Math.max(0, (day - a.day) / (b.day - a.day)));
      return { max: a.temp_max_c + (b.temp_max_c - a.temp_max_c) * t, min: a.temp_min_c + (b.temp_min_c - a.temp_min_c) * t };
    }

    const svg = container.firstChild;
    const q = (id) => svg.querySelector("#" + id);
    function setMarker(day) {
      day = Math.max(1, Math.min(365, Math.round(day)));
      const v = at(day), x = X(day);
      q("mk").setAttribute("x1", x); q("mk").setAttribute("x2", x);
      q("mh").setAttribute("cx", x); q("mh").setAttribute("cy", Y(v.max));
      q("ml").setAttribute("cx", x); q("ml").setAttribute("cy", Y(v.min));
      opts.onReadout(day, v.max, v.min);
    }
    setMarker(doy);
    svg.addEventListener("pointermove", (ev) => {
      const r = svg.getBoundingClientRect(), vx = ((ev.clientX - r.left) / r.width) * W;
      setMarker(1 + ((vx - L) / (R - L)) * 364);
    });
    svg.addEventListener("pointerleave", () => setMarker(doy));
  }

  RW.chart = { draw };
})();
