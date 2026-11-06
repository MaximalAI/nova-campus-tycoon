// ---------------------------------------------------------------------------
// UI: HUD, toasts, dialog template with a queue, world labels
// ---------------------------------------------------------------------------
class UI {
  constructor(game, root) {
    this.game = game;
    this.root = root;
    this.$ = (sel) => root.querySelector(sel);
    this.queue = [];
    this.current = null;
    this.labels = new Map();
    this.$("#hud").addEventListener("pointerdown", (e) => e.stopPropagation());
    root.querySelectorAll(".speed").forEach((b) =>
      b.addEventListener("click", () => game.setSpeed(Number(b.dataset.speed))));
    this.$("#pause-btn").addEventListener("click", () => game.flow.openPause());
    this.$("#skip-btn").addEventListener("click", () => game.flow.skipToOpening());
    this.$("#tray").addEventListener("click", (e) => {
      const b = e.target.closest("button");
      if (!b) return;
      if (b.dataset.act === "discard") game.flow.discardTray();
      if (b.dataset.act === "cancel") game.flow.confirmCancelOrder();
    });
  }
  // Only touch the DOM when the content really changed (keeps buttons clickable).
  setHtml(sel, html) {
    const e = this.$(sel);
    if (e._html !== html) { e.innerHTML = html; e._html = html; }
    return e;
  }

  // HUD --------------------------------------------------------------------
  showHud(on) { this.$("#hud").classList.toggle("hidden", !on); }
  updateHud() {
    const g = this.game, v = g.view;
    if (!v) return;
    this.$("#clock").textContent = fmtTime(g.clock.t);
    this.$("#day").textContent = `Day ${v.day}`;
    const money = this.$("#money");
    money.textContent = euro(v.money);
    money.classList.toggle("neg", v.money <= 0);
    this.$("#rep-fill").style.width = `${v.reputation}%`;
    this.$("#rep-value").textContent = `${v.reputation} / 100`;
    this.updateRepPerks(v);
    this.updateStock(v);
    this.updateShopPanel(v);
    const skip = g.flow.canSkipToOpening();
    this.$("#skip-btn").classList.toggle("hidden", !skip);
    this.$("#objective").textContent = g.flow.objectiveText();
    this.placeObjective();
    this.root.querySelectorAll(".speed").forEach((b) => b.classList.toggle("active", Number(b.dataset.speed) === g.clock.speed));
    this.$("#pause-btn").classList.toggle("active", g.clock.paused);
    const tray = this.$("#tray");
    const order = v.current_order;
    if (order) {
      tray.classList.remove("hidden");
      const need = order.items.map((p) => g.config.products[p].icon).join(" ");
      this.setHtml("#tray", `<span>Order: ${need}</span><span>→ Tray:</span>` +
        (v.tray.length ? v.tray.map((p) => `<div class="tray-slot">${g.config.products[p].icon}</div>`).join("") : `<div class="tray-slot"></div>`) +
        (v.tray.length ? `<button data-act="discard" title="Throw away what is on the tray">🗑 Throw away</button>` : "") +
        `<button data-act="cancel" class="danger" title="Give up this order">✖ Cancel order</button>`);
    } else tray.classList.add("hidden");
  }

  // The objective sits centred in the free space between the left cards and the clock card.
  placeObjective() {
    const left = this.$("#hud-topleft").getBoundingClientRect().right + 12;
    const right = window.innerWidth - this.$("#hud-right").getBoundingClientRect().left + 12;
    const o = this.$("#objective");
    o.style.left = `${Math.round(left)}px`; o.style.right = `${Math.round(right)}px`;
  }

  // Reputation: what it brings right now
  updateRepPerks(v) {
    const p = v.rep_perks;
    if (!p) return;
    const pct = (x) => `${x >= 0 ? "+" : ""}${Math.round(x * 100)}%`;
    const cls = (x) => (x > 0.001 ? "up" : x < -0.001 ? "down" : "");
    const tip = p.tip > 0 ? `<span class="up">${Math.round(p.tip * 100)}% tips</span>` : `no tips${p.next_tip ? ` (from ${p.next_tip})` : ""}`;
    this.setHtml("#rep-perks",
      `Customers today: <span class="${cls(p.demand_today)}">${pct(p.demand_today)}</span><br>` +
      `Patience: <span class="${cls(p.patience - 1)}">${pct(p.patience - 1)}</span> · ${tip}`);
  }

  // Stock: how many portions your shops can still sell
  updateStock(v) {
    const cfg = this.game.config;
    let html = "";
    const owned = Object.keys(v.shops).filter((s) => v.shops[s].owner === "player");
    for (const s of owned) {
      const portions = v.shops[s].portions || {};
      if (owned.length > 1) html += `<div class="stock-shop">${esc(cfg.shops[s].name)}${v.shops[s].staff ? " (barista)" : ""}</div>`;
      html += `<div class="stock-row">` + Object.entries(portions).map(([p, n]) => {
        const c = n === 0 ? "out" : n <= 3 ? "low" : "";
        return `<span class="${c}" title="${esc(cfg.products[p].name)}: ${n} left">${cfg.products[p].icon} ${n}</span>`;
      }).join("") + `</div>`;
    }
    const bag = Object.entries(v.bag || {});
    if (bag.length) html += `<div class="stock-shop">In your bag</div><div class="stock-row">` +
      bag.map(([i, q]) => `<span>${cfg.wholesale_items[i].icon} ${q}</span>`).join("") + `</div>`;
    this.setHtml("#stock-list", html || "empty");
  }

  // Wholesaler: shopping list next to what is already in the cart
  updateShopPanel(v) {
    const panel = this.$("#shop-panel");
    const show = v.in_wholesaler || ["WALK_TO_WHOLESALE", "WHOLESALE_SHOPPING"].includes(v.day_state);
    if (!show) { panel.classList.add("hidden"); return; }
    panel.classList.remove("hidden");
    const items = this.game.config.wholesale_items;
    const keys = [...new Set([...Object.keys(v.shopping_list || {}), ...Object.keys(v.cart || {})])];
    let html = `<h4>🛒 Shopping list · cart</h4>`;
    if (!keys.length) html += `<div class="row">Nothing planned yet</div>`;
    for (const i of keys) {
      const want = (v.shopping_list || {})[i] || 0, have = (v.cart || {})[i] || 0;
      const cls = have >= want && want ? "ok" : have < want ? "miss" : "";
      const mark = have >= want && want ? "✔" : have < want ? `${want - have} missing` : "extra";
      html += `<div class="row ${cls}"><span>${items[i].icon} ${esc(items[i].name)}</span><span>${have}/${want} · ${mark}</span></div>`;
    }
    html += `<div class="row total"><span>Cart total</span><span>${euro(v.cart_total || 0)}</span></div>`;
    html += `<div class="row"><span>Cash</span><span>${euro(v.money)}</span></div>`;
    const bag = Object.entries(v.bag || {});
    if (bag.length) html += `<div class="row ok"><span>Paid, in your bag</span><span>${bag.map(([i, q]) => `${items[i].icon}${q}`).join(" ")}</span></div>`;
    this.setHtml("#shop-panel", html);
  }

  toggleTab(on) {
    const panel = this.$("#tab-panel");
    if (!on) { panel.classList.add("hidden"); return; }
    const g = this.game, v = g.view, items = g.config.wholesale_items;
    const list = (obj) => Object.entries(obj || {}).map(([i, q]) => `<div>${items[i].icon} ${q}x ${esc(items[i].name)}</div>`).join("") || "<div>-</div>";
    let stock = "";
    for (const s of Object.keys(v.shops)) {
      if (v.shops[s].owner !== "player") continue;
      stock += `<h4>Stock: ${esc(g.config.shops[s].name)}</h4>`;
      const st = v.shops[s].stock;
      stock += Object.keys(st).length ? Object.entries(st).map(([i, e]) =>
        `<div>${items[i].icon} ${e.units} ${esc(items[i].base_name)}</div>`).join("") : "<div>empty</div>";
    }
    panel.innerHTML = `<h4>Shopping list</h4>${list(v.shopping_list)}<h4>Cart</h4>${list(v.cart)}` +
      `<h4>Bag</h4>${list(v.bag)}${stock}`;
    panel.classList.remove("hidden");
  }

  // Toasts (T01-T12) -----------------------------------------------------------
  toast(text, error = false) {
    const box = this.$("#toasts");
    const t = el("div", "toast" + (error ? " err" : ""), esc(text));
    box.appendChild(t);
    while (box.children.length > 3) box.firstChild.remove();
    setTimeout(() => t.remove(), error ? 3200 : 2600);
  }

  // Dialogs (P00-P20): one template, at most one open, the rest waits -----------
  get dialogOpen() { return !!this.current; }
  showDialog(spec) {
    if (spec.unique && (this.current?.id === spec.id || this.queue.some((q) => q.id === spec.id))) return;
    this.game.releasePointer(); // dialogs need the mouse cursor
    if (this.current) { if (spec.urgent) this.queue.unshift(spec); else this.queue.push(spec); return; }
    this.current = spec;
    this.renderDialog();
  }
  closeDialog() {
    if (this.current && this.current.onClose) this.current.onClose();
    this.current = null;
    this.$("#modal-layer").classList.add("hidden");
    this.$("#dialog").innerHTML = "";
    if (this.queue.length) {
      const next = this.queue.shift();
      if (!next.valid || next.valid()) { this.current = next; this.renderDialog(); }
      else this.closeDialog();
    }
    this.game.focus();
  }
  refreshDialog() { if (this.current) this.renderDialog(); }
  renderDialog() {
    const d = this.current;
    const box = this.$("#dialog");
    box.innerHTML = "";
    box.className = d.wide ? "wide" : "";
    if (d.custom) { d.custom(box); }
    else {
      box.appendChild(el("div", "dlg-head",
        `<div class="dlg-icon">${d.icon || "☕"}</div><div><div class="dlg-id">${esc(d.id)}</div><div class="dlg-title">${esc(d.title)}</div></div>`));
      if (d.text) box.appendChild(el("div", "dlg-text", d.text));
      const body = el("div", "dlg-body");
      if (d.rows) {
        const table = el("table", "dlg-rows");
        for (const r of d.rows) {
          const tr = el("tr", r.cls || "", `<td>${r.label}</td><td class="${r.vcls || ""}">${r.value}</td>`);
          table.appendChild(tr);
        }
        body.appendChild(table);
      }
      if (d.body) d.body(body);
      box.appendChild(body);
    }
    const buttons = el("div", "dlg-buttons");
    if (d.secondary) {
      const b = el("button", "btn secondary", esc(d.secondary.label));
      b.onclick = () => this.pressSecondary();
      buttons.appendChild(b);
    }
    for (const extra of d.extra || []) {
      const b = el("button", "btn " + (extra.cls || "secondary"), esc(extra.label));
      b.disabled = !!extra.disabled;
      b.onclick = () => extra.action();
      buttons.appendChild(b);
    }
    if (d.primary) {
      const b = el("button", "btn primary", esc(d.primary.label));
      b.disabled = typeof d.primary.disabled === "function" ? d.primary.disabled() : !!d.primary.disabled;
      b.onclick = () => this.pressPrimary();
      buttons.appendChild(b);
      this.primaryButton = b;
    }
    box.appendChild(buttons);
    this.$("#modal-layer").classList.remove("hidden");
  }
  pressPrimary() {
    const d = this.current;
    if (!d || !d.primary || d.busy) return;
    if (typeof d.primary.disabled === "function" ? d.primary.disabled() : d.primary.disabled) return;
    const keep = d.primary.action && d.primary.action() === "keep";
    if (!keep && this.current === d) this.closeDialog();
  }
  pressSecondary() {
    const d = this.current;
    if (!d || (d.busy && !d.cancelWhileBusy)) return;
    if (d.secondary && d.secondary.action) d.secondary.action();
    if (d.noEsc && !d.secondary) return;
    if (this.current === d) this.closeDialog();
  }

  // Labels attached to 3D positions ----------------------------------------------
  label(key, html, cls) {
    let e = this.labels.get(key);
    if (!e) { e = el("div", "wl " + (cls || "")); this.$("#overlay-labels").appendChild(e); this.labels.set(key, e); }
    if (e._html !== html) { e.innerHTML = html; e._html = html; }
    e._seen = true;
    return e;
  }
  placeLabel(e, pos3, camera, w, h) {
    const v = pos3.clone().project(camera);
    if (v.z > 1 || v.z < -1) { e.style.display = "none"; return; }
    e.style.display = "";
    e.style.left = `${(v.x * 0.5 + 0.5) * w}px`;
    e.style.top = `${(-v.y * 0.5 + 0.5) * h}px`;
  }
  beginLabels() { for (const e of this.labels.values()) e._seen = false; }
  endLabels() {
    for (const [k, e] of this.labels) if (!e._seen) { e.remove(); this.labels.delete(k); }
  }
}
