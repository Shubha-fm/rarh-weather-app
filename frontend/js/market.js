// Market price list: each row is a horizontal bar (typical price) with a thin line from the day's lowest to highest rate.
(function () {
  const RW = (window.RW = window.RW || {});

  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const money = new Intl.NumberFormat("en-IN");
  const inr = (n) => "₹" + money.format(Math.round(n));
  const perKg = (n) => { const x = n / 100; return Number.isInteger(x) ? String(x) : x.toFixed(1); };
  const fill = (s, o) => s.replace(/\{(\w+)\}/g, (_, k) => o[k]);

  function change(pct) {
    if (pct === null || pct === undefined) return { text: "–", cls: "flat" };
    const flat = Math.abs(pct) < 0.5;
    const arrow = flat ? "" : pct > 0 ? "▲ " : "▼ ";
    const sign = pct > 0 ? "+" : pct < 0 ? "−" : "";
    return { text: arrow + sign + Math.abs(pct).toFixed(1) + "%", cls: flat ? "flat" : pct > 0 ? "up" : "down" };
  }

  // data: response from GET /prices. opts: {lang, group: all|vegetable|crop, sort: price|name|change, t: text lookup}
  function render(data, opts) {
    const { lang, group, sort, t } = opts;
    let items = data.items.filter((i) => group === "all" || i.group === group);
    const hasChange = data.items.some((i) => i.change_pct !== null && i.change_pct !== undefined);

    const byName = (a, b) => a.name[lang].localeCompare(b.name[lang], RW.LOCALES[lang]);
    if (sort === "name") items.sort(byName);
    else if (sort === "change" && hasChange) items.sort((a, b) => (b.change_pct ?? -999) - (a.change_pct ?? -999));
    else items.sort((a, b) => b.modal_price - a.modal_price);

    const scale = Math.max(1, ...items.map((i) => i.max_price));
    const pct = (v) => ((v / scale) * 100).toFixed(2);

    const rows = items.map((i) => {
      const ch = change(i.change_pct);
      const aria = fill(t("rangeAria"), { a: i.min_price, m: i.modal_price, b: i.max_price });
      return (
        `<li class="pr-row${hasChange ? "" : " no-chg"}">` +
        `<div class="pr-name"><i class="sw" style="background:${esc(i.color)}"></i><span>${esc(i.name[lang])}</span></div>` +
        `<div class="pr-chart" role="img" aria-label="${esc(aria)}">` +
        `<div class="pr-bar" style="width:${pct(i.modal_price)}%;background:${esc(i.color)}"></div>` +
        `<div class="pr-range" style="left:${pct(i.min_price)}%;width:${(pct(i.max_price) - pct(i.min_price)).toFixed(2)}%"></div>` +
        `</div>` +
        `<div class="pr-val"><b>${inr(i.modal_price)}</b><small>${esc(fill(t("perKg"), { x: perKg(i.modal_price) }))}</small></div>` +
        (hasChange ? `<div class="pr-chg ${ch.cls}">${ch.text}</div>` : "") +
        `</li>`
      );
    });

    // Biggest rise and fall of the day, across the items on screen.
    let movers = "";
    const moving = items.filter((i) => i.change_pct !== null && i.change_pct !== undefined);
    if (moving.length > 1) {
      const up = moving.reduce((a, b) => (b.change_pct > a.change_pct ? b : a));
      const down = moving.reduce((a, b) => (b.change_pct < a.change_pct ? b : a));
      const card = (label, i) => {
        const ch = change(i.change_pct);
        return `<div class="mover"><div class="k">${esc(label)}</div><div class="v"><span>${esc(i.name[lang])}</span><span class="${ch.cls}">${ch.text}</span></div></div>`;
      };
      if (up.change_pct > 0.05) movers += card(t("rise"), up);
      if (down.change_pct < -0.05) movers += card(t("fall"), down);
    }

    return { rows: rows.join(""), movers, hasChange, count: items.length };
  }

  RW.market = { render };
})();
