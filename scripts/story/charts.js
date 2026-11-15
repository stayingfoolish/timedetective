const D = JSON.parse(document.getElementById("data").textContent);
const NS = "http://www.w3.org/2000/svg";
const X = JSON.parse(document.getElementById("extra").textContent);
const IND = D.regions.nw_india, HP = D.regions.high_plains;

function S(tag, attrs, parent, text) {
  const e = document.createElementNS(NS, tag);
  for (const k in attrs) e.setAttribute(k, attrs[k]);
  if (text != null) e.textContent = text;
  if (parent) parent.appendChild(e);
  return e;
}
function H(tag, cls, parent, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text != null) e.textContent = text;
  if (parent) parent.appendChild(e);
  return e;
}
const lin = (d0, d1, r0, r1) => v => r0 + (v - d0) * (r1 - r0) / (d1 - d0);
function niceTicks(lo, hi, n) {
  const raw = (hi - lo) / n, mag = Math.pow(10, Math.floor(Math.log10(raw)));
  const step = [1, 2, 2.5, 5, 10].map(m => m * mag).find(s => s >= raw);
  const out = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) out.push(Math.round(v * 1e6) / 1e6);
  return out;
}
const fmt = (v, d = 1) => (v == null ? "no data" : (Object.is(Number(v.toFixed(d)), -0) ? 0 : Number(v.toFixed(d))).toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d }).replace("-", "\u2212"));
const signed = (v, d = 1) => (v > 0 ? "+" : "") + fmt(v, d);

/* One tooltip per chart; text goes in with textContent only. */
function tooltip(host) {
  const tip = H("div", "tip", host);
  return {
    show(title, rows, px, py) {
      tip.textContent = "";
      H("span", "t", tip, title);
      for (const r of rows) {
        const row = H("div", "r", tip), left = H("span", "", row);
        if (r.c) { const k = H("span", "k", left); k.style.setProperty("--c", r.c); }
        left.appendChild(document.createTextNode(r.name));
        H("b", "", row, r.value);
      }
      const w = host.scrollWidth;
      tip.classList.add("on");
      const tw = tip.offsetWidth, th = tip.offsetHeight;
      tip.style.left = Math.max(0, Math.min(w - tw, px + 12)) + "px";
      tip.style.top = Math.max(0, py - th - 10) + "px";
    },
    hide() { tip.classList.remove("on"); }
  };
}
function frame(host, W, Hh, m) {
  const svg = S("svg", { viewBox: `0 0 ${W} ${Hh}`, role: "img", "aria-label": host.dataset.label || "" }, host);
  const g = S("g", { transform: `translate(${m.l},${m.t})` }, svg);
  return { svg, g, iw: W - m.l - m.r, ih: Hh - m.t - m.b, m, W, H: Hh, toPx: (x, y) => { const r = svg.getBoundingClientRect(); return [(x + m.l) * r.width / W, (y + m.t) * r.height / Hh]; } };
}
function yAxis(f, y, ticks, unit, d = 0) {
  for (const t of ticks) {
    S("line", { x1: 0, x2: f.iw, y1: y(t), y2: y(t), style: "stroke:var(--grid);stroke-width:1" }, f.g);
    S("text", { x: -8, y: y(t) + 4, "text-anchor": "end" }, f.g, fmt(t, d));
  }
  if (unit) S("text", { x: -f.m.l + 2, y: -f.m.t + 12, "text-anchor": "start" }, f.g, unit);
}
function xAxis(f, x, ticks, label, fmtTick = String) {
  S("line", { x1: 0, x2: f.iw, y1: f.ih, y2: f.ih, style: "stroke:var(--axis);stroke-width:1" }, f.g);
  for (const t of ticks) S("text", { x: x(t), y: f.ih + 17, "text-anchor": "middle" }, f.g, fmtTick(t));
  if (label) S("text", { x: f.iw, y: f.ih + 34, "text-anchor": "end" }, f.g, label);
}
function tableView(host, cols, rows) {
  const d = H("details", "tbl", host);
  H("summary", "", d, "Show the numbers");
  const box = H("div", "box", d), t = H("table", "", box), hr = H("tr", "", H("thead", "", t));
  cols.forEach(c => H("th", "", hr, c));
  const tb = H("tbody", "", t);
  rows.forEach(r => { const tr = H("tr", "", tb); r.forEach(c => H("td", "", tr, c)); });
}

/* Lines over a numeric x. series: [{name, c, pts:[[x,y|null]], w, dots, end}] */
function linesChart(id, cfg) {
  const host = document.getElementById(id); if (!host) return;
  const m = { l: 46, r: cfg.right || 22, t: 22, b: cfg.xLabel ? 40 : 26 }, f = frame(host, cfg.W || 760, cfg.H || 300, m);
  const xs = cfg.xDomain, ys = cfg.yDomain, x = lin(xs[0], xs[1], 0, f.iw), y = lin(ys[0], ys[1], f.ih, 0);
  if (cfg.band) {
    S("rect", { x: x(cfg.band.x0), y: 0, width: x(cfg.band.x1) - x(cfg.band.x0), height: f.ih, style: "fill:var(--surface-2)" }, f.g);
    S("text", { x: (x(cfg.band.x0) + x(cfg.band.x1)) / 2, y: 12, "text-anchor": "middle", class: "lbl" }, f.g, cfg.band.label);
  }
  yAxis(f, y, cfg.yTicks || niceTicks(ys[0], ys[1], 5), cfg.unit, cfg.yDec || 0);
  if (cfg.zero) S("line", { x1: 0, x2: f.iw, y1: y(0), y2: y(0), style: "stroke:var(--axis);stroke-width:1" }, f.g);
  xAxis(f, x, cfg.xTicks, cfg.xLabel);
  for (const s of cfg.series) {
    let d = "", pen = false;
    for (const [px, py] of s.pts) { if (py == null) { pen = false; continue; } d += (pen ? "L" : "M") + x(px).toFixed(1) + " " + y(py).toFixed(1); pen = true; }
    S("path", { d, style: `fill:none;stroke:${s.c};stroke-width:${s.w || 2};stroke-linejoin:round;stroke-linecap:round;opacity:${s.o || 1}` }, f.g);
    if (s.dots) for (const [px, py] of s.pts) if (py != null) S("circle", { cx: x(px), cy: y(py), r: 3.6, style: `fill:${s.c};stroke:var(--surface);stroke-width:2` }, f.g);
    const last = [...s.pts].reverse().find(p => p[1] != null);
    if (s.end && last) {
      S("circle", { cx: x(last[0]), cy: y(last[1]), r: 4.5, style: `fill:${s.c};stroke:var(--surface);stroke-width:2` }, f.g);
      S("text", { x: x(last[0]) - 8, y: y(last[1]) + (s.endDy || -10), "text-anchor": "end", class: "strong" }, f.g, s.end);
    }
  }
  (cfg.notes || []).forEach(n => S("text", { x: x(n.x), y: y(n.y), "text-anchor": n.anchor || "start", class: "lbl" }, f.g, n.text));
  const cross = S("line", { y1: 0, y2: f.ih, style: "stroke:var(--ink-2);stroke-width:1;opacity:0" }, f.g), tip = tooltip(host);
  const loud = cfg.series.filter(q => !q.quiet), xsAll = loud[0].pts.map(p => p[0]);
  const hit = S("rect", { x: 0, y: 0, width: f.iw, height: f.ih, style: "fill:transparent" }, f.g);
  hit.addEventListener("pointermove", ev => {
    const r = f.svg.getBoundingClientRect(), vx = (ev.clientX - r.left) * f.W / r.width - m.l;
    let bi = 0, bd = Infinity; xsAll.forEach((v, i) => { const dd = Math.abs(x(v) - vx); if (dd < bd) { bd = dd; bi = i; } });
    const xv = xsAll[bi];
    cross.setAttribute("x1", x(xv)); cross.setAttribute("x2", x(xv)); cross.style.opacity = 1;
    const rows = loud.map(s => { const p = s.pts.reduce((a, b) => Math.abs(b[0] - xv) < Math.abs(a[0] - xv) ? b : a); return { name: s.name, c: s.c, value: p[1] == null || Math.abs(p[0] - xv) > (cfg.tol || 0.05) ? "no data" : fmt(p[1], cfg.dec == null ? 1 : cfg.dec) + (cfg.suffix || "") }; });
    const [px, py] = f.toPx(x(xv), 0);
    tip.show(cfg.xFmt ? cfg.xFmt(xv) : String(xv), rows, px, py + 40);
  });
  hit.addEventListener("pointerleave", () => { cross.style.opacity = 0; tip.hide(); });
  if (cfg.table) tableView(host.parentNode, cfg.table.cols, cfg.table.rows);
}

/* Bars from a zero baseline. bars: [{k, v}] */
function barsChart(id, cfg) {
  const host = document.getElementById(id); if (!host) return;
  const m = { l: 46, r: cfg.ref && cfg.ref.label ? 116 : 22, t: 22, b: 26 }, f = frame(host, cfg.W || 760, cfg.H || 260, m);
  const ys = cfg.yDomain, y = lin(ys[0], ys[1], f.ih, 0), n = cfg.bars.length, band = f.iw / n, bw = Math.min(24, band - 2);
  yAxis(f, y, cfg.yTicks || niceTicks(ys[0], ys[1], 5), cfg.unit, 0);
  const tip = tooltip(host);
  cfg.bars.forEach((b, i) => {
    const cx = band * i + band / 2, y0 = y(0), y1 = y(b.v), top = Math.min(y0, y1), h = Math.max(1, Math.abs(y1 - y0)), r = Math.min(4, h, bw / 2), x0 = cx - bw / 2, x1 = cx + bw / 2;
    const d = b.v >= 0
      ? `M${x0} ${y0}V${top + r}Q${x0} ${top} ${x0 + r} ${top}H${x1 - r}Q${x1} ${top} ${x1} ${top + r}V${y0}Z`
      : `M${x0} ${y0}V${y1 - r}Q${x0} ${y1} ${x0 + r} ${y1}H${x1 - r}Q${x1} ${y1} ${x1} ${y1 - r}V${y0}Z`;
    const bar = S("path", { d, style: `fill:${cfg.c}` }, f.g);
    const hit = S("rect", { x: band * i, y: 0, width: band, height: f.ih, style: "fill:transparent" }, f.g);
    const on = () => { bar.style.opacity = 0.75; const [px, py] = f.toPx(cx, top); tip.show(String(b.k), [{ name: cfg.name, c: cfg.c, value: signed(b.v, 1) + (cfg.suffix || "") }], px, py); };
    const off = () => { bar.style.opacity = 1; tip.hide(); };
    hit.addEventListener("pointermove", on); hit.addEventListener("pointerleave", off);
    if (cfg.tickEvery && (i % cfg.tickEvery === (cfg.tickOffset || 0))) S("text", { x: cx, y: f.ih + 17, "text-anchor": "middle" }, f.g, String(b.k));
  });
  S("line", { x1: 0, x2: f.iw, y1: y(0), y2: y(0), style: "stroke:var(--axis);stroke-width:1" }, f.g);
  if (cfg.ref) {
    S("line", { x1: 0, x2: f.iw, y1: y(cfg.ref.v), y2: y(cfg.ref.v), style: "stroke:var(--ink);stroke-width:1.5" }, f.g);
    (cfg.ref.label || []).forEach((t, i) => S("text", { x: f.iw + 9, y: y(cfg.ref.v) - 2 + i * 15, class: "strong" }, f.g, t));
  }
  if (cfg.table) tableView(host.parentNode, cfg.table.cols, cfg.table.rows);
}

/* Histogram of placebo changes with the real one marked. */
function histChart(id, cfg) {
  const host = document.getElementById(id); if (!host) return;
  const m = { l: 46, r: 22, t: 34, b: 42 }, f = frame(host, 760, 290, m);
  const step = cfg.step, lo = Math.floor(Math.min(...cfg.values, cfg.marker) / step) * step, hi = Math.ceil(Math.max(...cfg.values, cfg.marker) / step) * step;
  const bins = []; for (let a = lo; a < hi - 1e-9; a += step) bins.push({ a, b: a + step, n: 0, far: 0 });
  cfg.values.forEach(v => { const b = bins[Math.min(bins.length - 1, Math.floor((v - lo) / step))]; b.n++; if (Math.abs(v) >= Math.abs(cfg.marker)) b.far++; });
  const maxN = Math.max(...bins.map(b => b.n)), x = lin(lo, hi, 0, f.iw), y = lin(0, Math.ceil(maxN / 10) * 10, f.ih, 0);
  yAxis(f, y, niceTicks(0, Math.ceil(maxN / 10) * 10, 4), "number of stretches", 0);
  const tip = tooltip(host);
  bins.forEach(b => {
    const x0 = x(b.a) + 1, w = x(b.b) - x(b.a) - 2;
    const draw = (count, from, c) => { if (!count) return; const top = y(from + count), h = y(from) - top; S("rect", { x: x0, y: top, width: w, height: h, rx: from + count === b.n ? 3 : 0, style: `fill:${c}` }, f.g); };
    draw(b.n - b.far, 0, "var(--neutral-mark)"); draw(b.far, b.n - b.far, "var(--series-1)");
    const hit = S("rect", { x: x(b.a), y: 0, width: x(b.b) - x(b.a), height: f.ih, style: "fill:transparent" }, f.g);
    const on = () => { const [px, py] = f.toPx(x0 + w / 2, y(b.n)); tip.show(`${signed(b.a, 0)} to ${signed(b.b, 0)} cm`, [{ name: "stretches", value: String(b.n) }, { name: "as large as the real gap", c: "var(--series-1)", value: String(b.far) }], px, py); };
    hit.addEventListener("pointermove", on); hit.addEventListener("pointerleave", () => tip.hide());
  });
  xAxis(f, x, niceTicks(lo, hi, 8), cfg.xLabel, t => signed(t, 0));
  S("line", { x1: x(cfg.marker), x2: x(cfg.marker), y1: -8, y2: f.ih, style: "stroke:var(--ink);stroke-width:2" }, f.g);
  S("text", { x: x(cfg.marker) + 8, y: 8, class: "strong" }, f.g, cfg.markerLabel);
  if (cfg.table) tableView(host.parentNode, cfg.table.cols, cfg.table.rows);
}

/* Scatter with a fitted line and the reading at average rainfall. */
function scatterChart(id, cfg) {
  const host = document.getElementById(id); if (!host) return;
  const m = { l: 46, r: 22, t: 22, b: 42 }, f = frame(host, 760, 320, m);
  const x = lin(cfg.xDomain[0], cfg.xDomain[1], 0, f.iw), y = lin(cfg.yDomain[0], cfg.yDomain[1], f.ih, 0);
  yAxis(f, y, niceTicks(cfg.yDomain[0], cfg.yDomain[1], 6), cfg.unit, 0);
  S("line", { x1: 0, x2: f.iw, y1: y(0), y2: y(0), style: "stroke:var(--axis);stroke-width:1" }, f.g);
  S("text", { x: f.iw, y: y(0) - 6, "text-anchor": "end", class: "lbl" }, f.g, "no change in storage");
  xAxis(f, x, niceTicks(cfg.xDomain[0], cfg.xDomain[1], 6), cfg.xLabel, t => fmt(t, 0));
  const line = v => cfg.a + cfg.b * (v - cfg.mean) / 100;
  S("line", { x1: x(cfg.xDomain[0]), x2: x(cfg.xDomain[1]), y1: y(line(cfg.xDomain[0])), y2: y(line(cfg.xDomain[1])), style: "stroke:var(--series-1);stroke-width:2;opacity:0.55" }, f.g);
  S("line", { x1: x(cfg.mean), x2: x(cfg.mean), y1: 0, y2: f.ih, style: "stroke:var(--series-2);stroke-width:1.5" }, f.g);
  S("text", { x: x(cfg.mean) + 7, y: 12, class: "lbl" }, f.g, `average rainfall, ${fmt(cfg.mean, 0)} mm a year`);
  const dots = cfg.pts.map(p => S("circle", { cx: x(p.x), cy: y(p.y), r: 4.5, style: "fill:var(--series-1);stroke:var(--surface);stroke-width:2" }, f.g));
  S("line", { x1: x(cfg.mean), x2: x(cfg.mean), y1: y(cfg.aLow), y2: y(cfg.aHigh), style: "stroke:var(--ink);stroke-width:3;stroke-linecap:round" }, f.g);
  S("circle", { cx: x(cfg.mean), cy: y(cfg.a), r: 6.5, style: "fill:var(--ink);stroke:var(--surface);stroke-width:2" }, f.g);
  S("text", { x: x(cfg.mean) + 12, y: y(cfg.aLow) + 16, class: "strong" }, f.g, cfg.aLabel);
  const tip = tooltip(host), hit = S("rect", { x: 0, y: 0, width: f.iw, height: f.ih, style: "fill:transparent" }, f.g);
  hit.addEventListener("pointermove", ev => {
    const r = f.svg.getBoundingClientRect(), vx = (ev.clientX - r.left) * f.W / r.width - m.l, vy = (ev.clientY - r.top) * f.H / r.height - m.t;
    let bi = 0, bd = Infinity; cfg.pts.forEach((p, i) => { const dd = Math.hypot(x(p.x) - vx, y(p.y) - vy); if (dd < bd) { bd = dd; bi = i; } });
    dots.forEach((d, i) => d.setAttribute("r", i === bi ? 6.5 : 4.5));
    const p = cfg.pts[bi], [px, py] = f.toPx(x(p.x), y(p.y));
    tip.show(String(p.k), [{ name: "storage change", c: "var(--series-1)", value: signed(p.y, 1) + " cm" }, { name: "rainfall", c: "var(--series-2)", value: fmt(p.x, 0) + " mm a year" }], px, py);
  });
  hit.addEventListener("pointerleave", () => { dots.forEach(d => d.setAttribute("r", 4.5)); tip.hide(); });
  if (cfg.table) tableView(host.parentNode, cfg.table.cols, cfg.table.rows);
}

/* The region as the satellites see it: one rectangle per measurement block. */
function mapChart(id, cfg) {
  const host = document.getElementById(id); if (!host) return;
  const W = cfg.W || 760, Hh = cfg.H || 360, m = { l: 40, r: 10, t: 10, b: 26 }, f = frame(host, W, Hh, m);
  const lat0 = cfg.lat[0], lat1 = cfg.lat[1], lon0 = cfg.lon[0], lon1 = cfg.lon[1], k = Math.cos(((lat0 + lat1) / 2) * Math.PI / 180);
  const sc = Math.min(f.iw / ((lon1 - lon0) * k), f.ih / (lat1 - lat0)), ox = (f.iw - (lon1 - lon0) * k * sc) / 2;
  const x = v => ox + (v - lon0) * k * sc, y = v => (lat1 - v) * sc;
  for (let v = Math.ceil(lat0 / 2) * 2; v <= lat1; v += 2) { S("line", { x1: x(lon0), x2: x(lon1), y1: y(v), y2: y(v), style: "stroke:var(--grid);stroke-width:1" }, f.g); S("text", { x: x(lon0) - 8, y: y(v) + 4, "text-anchor": "end" }, f.g, v + "°N"); }
  for (let v = Math.ceil(lon0 / 2) * 2; v <= lon1; v += 2) { S("line", { x1: x(v), x2: x(v), y1: y(lat0), y2: y(lat1), style: "stroke:var(--grid);stroke-width:1" }, f.g); S("text", { x: x(v), y: y(lat0) + 17, "text-anchor": "middle" }, f.g, v + "°E"); }
  const tip = tooltip(host);
  cfg.cells.forEach((c, i) => {
    const hot = cfg.hot && cfg.hot.includes(i), dim = cfg.hot && !hot;
    const r = S("rect", { x: x(c.lon - c.dlon / 2) + 1, y: y(c.lat + c.dlat / 2) + 1, width: c.dlon * k * sc - 2, height: c.dlat * sc - 2, rx: 2, style: `fill:${dim ? "var(--neutral-mark)" : "var(--series-1)"};opacity:${dim ? 0.35 : hot ? 0.95 : 0.5}` }, f.g);
    const on = () => { const [px, py] = f.toPx(x(c.lon), y(c.lat + c.dlat / 2)); tip.show(`Block ${i + 1} of ${cfg.cells.length}`, [{ name: "centre", value: `${fmt(c.lat, 0)}°N ${fmt(c.lon, 1)}°E` }], px, py); };
    r.addEventListener("pointermove", on); r.addEventListener("pointerleave", () => tip.hide());
  });
  (cfg.places || []).forEach(p => {
    S("circle", { cx: x(p.lon), cy: y(p.lat), r: 3.5, style: "fill:var(--ink);stroke:var(--surface);stroke-width:2" }, f.g);
    S("text", { x: x(p.lon) + (p.left ? -7 : 7), y: y(p.lat) + 4, "text-anchor": p.left ? "end" : "start", class: "strong", style: "paint-order:stroke;stroke:var(--surface);stroke-width:3px" }, f.g, p.name);
  });
}

/* The playbook as a graph. Steps and arrows come from the playbook file; the thick path comes from the run. */
function playbook(id, cfg) {
  const host = document.getElementById(id); if (!host) return;
  const P = D.playbook, procs = P.nodes.filter(n => n.procedure);
  const W = 760, x0 = 24, bw = 250, bh = 50, rowH = 84, top = 14, yOf = i => top + i * rowH, cx = x0 + bw / 2, Hh = yOf(procs.length) + bh + 14;
  const svg = S("svg", { viewBox: `0 0 ${W} ${Hh}`, role: "img", "aria-label": host.dataset.label || "" }, host);
  const defs = S("defs", {}, svg);
  const head = (name, c) => S("path", { d: "M0 0L9 4.5L0 9Z", style: `fill:${c}` }, S("marker", { id: `${name}-${id}`, markerWidth: 9, markerHeight: 9, refX: 8, refY: 4.5, orient: "auto", markerUnits: "userSpaceOnUse" }, defs));
  head("a", "var(--muted)"); head("b", "var(--ink)");
  const idx = {}; procs.forEach((n, i) => idx[n.id] = i);
  const taken = new Set(cfg.path), stroke = on => `stroke:${on ? "var(--ink)" : "var(--muted)"};stroke-width:${on ? 2.5 : 1.2};fill:none`, end = on => `url(#${on ? "b" : "a"}-${id})`;
  const rows = P.edges.filter(e => e.target === "refused").map(e => idx[e.origin]);
  const rx = 538, rw = 198, rTop = yOf(Math.min(...rows)), rBot = yOf(Math.max(...rows)) + bh, busX = 512, yEnd = yOf(procs.length) + bh / 2;
  P.edges.forEach(e => {
    const y = yOf(idx[e.origin]), on = taken.has(e.id);
    if (e.outcome === "ok") {
      S("line", { x1: cx, y1: y + bh, x2: cx, y2: y + rowH - 2, style: stroke(on), "marker-end": end(on) }, svg);
      S("text", { x: cx + 12, y: y + bh + 21, class: "lbl" }, svg, `ok · rule from ${X.short[e.source] || e.source}`);
    } else if (e.target === "refused") {
      S("line", { x1: x0 + bw, y1: y + bh / 2, x2: rx - 2, y2: y + bh / 2, style: stroke(on), "marker-end": end(on) }, svg);
      S("text", { x: x0 + bw + 12, y: y + bh / 2 - 7, class: "lbl" }, svg, X.reasons[e.id] || "refused");
    } else {
      S("path", { d: `M${x0 + bw} ${y + bh / 2}H${busX}V${yEnd}H${x0 + bw + 2}`, style: stroke(on), "marker-end": end(on) }, svg);
      S("text", { x: x0 + bw + 12, y: y + bh / 2 - 7, class: "lbl" }, svg, X.reasons[e.id] || "skip");
    }
  });
  S("rect", { x: rx, y: rTop, width: rw, height: rBot - rTop, rx: 10, style: "fill:var(--surface);stroke:var(--stop);stroke-width:1.5" }, svg);
  S("text", { x: rx + 16, y: rTop + 30, class: "strong", style: "font-size:14px" }, svg, "refused");
  ["The check stops here.", "It reports what failed", "and what would change", "the answer. No trend", "is computed past", "this point."].forEach((t, i) => S("text", { x: rx + 16, y: rTop + 54 + i * 17, class: "lbl" }, svg, t));
  ["If a record is missing,", "the finding is written", "from the steps that ran."].forEach((t, i) => S("text", { x: busX + 12, y: yOf(procs.length - 1) + 4 + i * 17, class: "lbl" }, svg, t));
  procs.forEach((n, i) => {
    const y = yOf(i);
    S("rect", { x: x0, y, width: bw, height: bh, rx: 8, style: "fill:var(--surface);stroke:var(--ink);stroke-width:1.5" }, svg);
    S("text", { x: x0 + 14, y: y + 21, class: "strong", style: "font-size:13px" }, svg, `${i + 1}  ${n.id}`);
    S("text", { x: x0 + bw - 14, y: y + 21, "text-anchor": "end" }, svg, D.procedures[n.procedure].category);
    S("text", { x: x0 + 14, y: y + 39, class: "lbl", style: "font-family:var(--mono);font-size:11.5px" }, svg, n.procedure);
  });
  const y = yOf(procs.length);
  S("rect", { x: x0, y, width: bw, height: bh, rx: bh / 2, style: "fill:var(--ink)" }, svg);
  S("text", { x: cx, y: y + 21, "text-anchor": "middle", style: "fill:var(--page);font-size:13px;font-weight:600" }, svg, "finding");
  S("text", { x: cx, y: y + 38, "text-anchor": "middle", style: "fill:var(--page)" }, svg, cfg.endLabel);
}

const monthX = t => Number(t.slice(0, 4)) + (Number(t.slice(5, 7)) - 0.5) / 12;
const monthName = xv => { const yv = Math.floor(xv), mo = Math.min(11, Math.floor((xv - yv) * 12)); return ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][mo] + " " + yv; };
const yearsTicks = [2002, 2006, 2010, 2014, 2018, 2022, 2026];
const GAP = { x0: 2017.5, x1: 2018.42, label: "no satellites" };

const dm = X.domains;
linesChart("c-subtract", {
  H: 320, xDomain: [2002, 2026.8], yDomain: dm.monthly, yTicks: dm.monthlyTicks, unit: "cm of water", xTicks: yearsTicks, band: GAP, zero: true, tol: 0.05, suffix: " cm", xFmt: monthName, right: 26,
  series: [
    { name: "All stored water", c: "var(--neutral-mark)", w: 1.5, pts: IND.monthly.map(d => [monthX(d.t), d.total]) },
    { name: "Soil moisture and snow (model)", c: "var(--series-4)", w: 1.5, pts: IND.monthly.map(d => [monthX(d.t), d.model]) },
    { name: "Groundwater estimate", c: "var(--series-1)", w: 2, pts: IND.monthly.map(d => [monthX(d.t), d.gw]) }],
  table: { cols: ["Month", "All stored water, cm", "Soil moisture and snow, cm", "Groundwater estimate, cm"], rows: IND.monthly.map(d => [d.t, fmt(d.total, 1), fmt(d.model, 1), fmt(d.gw, 1)]) }
});
const PLACES = [{ name: "Delhi", lat: 28.61, lon: 77.21, left: true }, { name: "Amritsar", lat: 31.63, lon: 74.87, left: true }, { name: "Jaipur", lat: 26.91, lon: 75.79 }, { name: "Ludhiana", lat: 30.9, lon: 75.85 }];
mapChart("c-map", { W: 380, H: 330, lat: dm.mapLat, lon: dm.mapLon, cells: IND.mascons, places: PLACES });
const A0 = IND.annual[0], A1 = IND.annual[IND.annual.length - 1];
linesChart("c-annual", {
  H: 320, xDomain: [2002, 2026.8], yDomain: dm.monthly, yTicks: dm.monthlyTicks, unit: "cm of water", xTicks: yearsTicks, band: GAP, zero: true, tol: 0.6, suffix: " cm", xFmt: v => String(Math.floor(v)), right: 26,
  series: [
    { name: "Monthly estimate", c: "var(--neutral-mark)", w: 1, quiet: true, pts: IND.monthly.map(d => [monthX(d.t), d.gw]) },
    { name: "Yearly value", c: "var(--series-1)", w: 2, dots: true, pts: IND.annual.map(d => [d.year + 0.5, d.value]) }],
  notes: [{ x: A0.year + 1.2, y: A0.value + 5, text: `${A0.year}: ${signed(A0.value, 0)} cm` }, { x: A1.year + 0.3, y: A1.value - 12, anchor: "end", text: `${A1.year}: ${signed(A1.value, 0)} cm` }],
  table: { cols: ["Year", "Groundwater estimate, cm", "Months of data"], rows: IND.annual.map(d => [String(d.year), fmt(d.value, 1), String(IND.thin_years[d.year] || 12)]) }
});
const changeBars = (id, R, o = {}) => barsChart(id, Object.assign({
  yDomain: dm.changes, c: "var(--series-1)", name: "change from the year before", suffix: " cm", unit: "cm of water", tickEvery: 4, tickOffset: 1,
  bars: R.changes.map(d => ({ k: d.year, v: d.value })), ref: { v: R.trend.mean_change, label: ["average change", `${signed(R.trend.mean_change, 1)} cm a year`] },
  table: { cols: ["Year", "Change from the year before, cm"], rows: R.changes.map(d => [String(d.year), signed(d.value, 1)]) }
}, o));
changeBars("c-changes", IND);
scatterChart("c-rain", {
  xDomain: dm.rain, yDomain: dm.changes, unit: "cm of water", xLabel: "rain over the same two years, mm a year", mean: IND.rainfall.mean_rain, a: IND.rainfall.a, b: IND.rainfall.b, aLow: IND.rainfall.a_low, aHigh: IND.rainfall.a_high,
  aLabel: `${signed(IND.rainfall.a, 1)} cm a year`, pts: IND.rainfall.pairs.map(p => ({ k: p.year, x: p.rain, y: p.change })),
  table: { cols: ["Year", "Rain over the same two years, mm a year", "Storage change, cm"], rows: IND.rainfall.pairs.map(p => [String(p.year), fmt(p.rain, 0), signed(p.change, 1)]) }
});
const greenYears = IND.greenness.values.yearly;
linesChart("c-green-water", { H: 200, xDomain: [2001.5, 2026], yDomain: dm.annual, yTicks: dm.annualTicks, unit: "groundwater estimate, cm of water", xTicks: yearsTicks.slice(0, 6), zero: true, tol: 0.6, suffix: " cm", xFmt: v => String(Math.floor(v)),
  series: [{ name: "Groundwater estimate", c: "var(--series-1)", w: 2, dots: true, pts: greenYears.map(d => [d.year + 0.5, d.storage_cm]) }] });
linesChart("c-green-ndvi", { H: 200, xDomain: [2001.5, 2026], yDomain: dm.ndvi, yTicks: dm.ndviTicks, yDec: 2, dec: 3, unit: "greenness of the land (NDVI)", xTicks: yearsTicks.slice(0, 6), tol: 0.6, xFmt: v => String(Math.floor(v)),
  series: [{ name: "Greenness (NDVI)", c: "var(--series-3)", w: 2, dots: true, pts: greenYears.map(d => [d.year + 0.5, d.greenness]) }],
  table: { cols: ["Year", "Groundwater estimate, cm", "Greenness (NDVI)"], rows: greenYears.map(d => [String(d.year), fmt(d.storage_cm, 1), fmt(d.greenness, 3)]) } });
histChart("c-gap", { values: IND.handover.placebos, marker: IND.handover.observed, step: 2, xLabel: "change across a stretch of the same length, cm, after taking out the overall slide", markerLabel: `the real gap: ${signed(IND.handover.observed, 1)} cm`,
  table: { cols: ["Stretch", "Change, cm"], rows: IND.handover.placebos.map((v, i) => [String(i + 1), signed(v, 1)]) } });
mapChart("c-district", { W: 380, H: 330, lat: dm.mapLat, lon: dm.mapLon, cells: IND.mascons, hot: X.hot, places: [PLACES[3]] });
playbook("c-playbook", { path: IND.steps.map(s => s.edge), endLabel: "the critic sets the label" });
const regionLine = (id, R) => linesChart(id, { W: 380, H: 240, xDomain: [2002, 2027], yDomain: dm.annual, yTicks: dm.annualTicks, unit: "cm of water", xTicks: [2002, 2010, 2018, 2026], zero: true, tol: 0.6, suffix: " cm", xFmt: v => String(Math.floor(v)),
  series: [{ name: "Groundwater estimate", c: "var(--series-1)", w: 2, dots: true, pts: R.annual.map(d => [d.year + 0.5, d.value]) }],
  table: { cols: ["Year", "Groundwater estimate, cm"], rows: R.annual.map(d => [String(d.year), fmt(d.value, 1)]) } });
regionLine("c-cmp-ind", IND); regionLine("c-cmp-hp", HP);
const smallBars = (id, R) => changeBars(id, R, { W: 380, H: 220, tickEvery: 8, ref: { v: R.trend.mean_change } });
smallBars("c-cmpb-ind", IND); smallBars("c-cmpb-hp", HP);
