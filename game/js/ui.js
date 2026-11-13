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
    // v8: one press opens the statistics (pointerdown fires at once, the HUD text below updates often)
    this.$("#gain").addEventListener("pointerdown", (e) => { e.preventDefault(); e.stopPropagation(); game.flow.openStats(); });
    this.$("#mono").addEventListener("click", () => game.flow.openMonopoly());
    this.$("#minimap").addEventListener("click", () => game.openBigMap());
    this.$("#bigmap-close").addEventListener("click", () => game.closeBigMap());
    this.$("#bigmap").addEventListener("click", (e) => {
      const spot = e.target.closest("[data-go]");
      if (spot) game.teleportTo(spot.dataset.go);
      else if (e.target.id === "bigmap") game.closeBigMap();
    });
    this.$("#tray").addEventListener("click", (e) => {
      const b = e.target.closest("button");
      if (!b) return;
      if (b.dataset.act === "discard") game.flow.discardTray();
      if (b.dataset.act === "extras") game.flow.discardTray({ only_extras: true });
      if (b.dataset.act === "one") game.flow.discardTray({ product: b.dataset.product });
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
    const gain = v.today ? v.today.gain : 0;
    const gEl = this.$("#gain"), gText = `today ${gain >= 0 ? "+" : ""}${euro(gain)}`;
    if (this.$("#gain-text").textContent !== gText) this.$("#gain-text").textContent = gText;
    gEl.classList.toggle("neg", gain < 0);
    this.$("#rep-fill").style.width = `${v.reputation}%`;
    this.$("#rep-value").textContent = `${v.reputation} / 100`;
    this.updateRepPerks(v);
    if (v.monopoly) {
      const m = v.monopoly;
      // v8: counts the shops you own (your café is shop 1); P35 shows the managers
      this.$("#mono-value").textContent = `${m.owned}/${m.total}`;
      this.$("#mono-fill").style.width = `${(m.owned / m.total) * 100}%`;
    }
    this.updateStock(v);
    this.updateShopPanel(v);
    // v11: a primary button whose state depends on choices in the dialog follows them
    // (Bowl Bar: "Assemble" turns green as soon as an ingredient is picked)
    const cur = this.current;
    if (cur && cur.primary && typeof cur.primary.disabled === "function" && this.primaryButton) {
      const off = !!cur.busy || !!cur.primary.disabled();
      if (this.primaryButton.disabled !== off) this.primaryButton.disabled = off;
    }
    const skip = g.flow.canSkipToOpening();
    this.$("#skip-btn").classList.toggle("hidden", !skip);
    // v11: greyed out while managers are still on their way to or from the wholesaler
    const ready = skip && g.flow.canStartDay();
    this.$("#skip-btn").classList.toggle("waiting", skip && !ready);
    const tip = ready ? "Jump to 08:00 and open the café" : "Your managers are still at the wholesaler";
    if (this.$("#skip-btn").title !== tip) this.$("#skip-btn").title = tip;
    this.$("#objective").textContent = g.flow.objectiveText();
    this.placeObjective();
    this.root.querySelectorAll(".speed").forEach((b) => b.classList.toggle("active", Number(b.dataset.speed) === g.clock.speed));
    this.$("#pause-btn").classList.toggle("active", g.clock.paused);
    const tray = this.$("#tray");
    const order = v.current_order;
    if (order) {
      tray.classList.remove("hidden");
      const need = order.items.map((p) => g.config.products[p].icon).join(" ");
      // v5: each slot on the tray has its own ✕; products the order does not need are marked red
      const rest = [...order.items];
      const slots = v.tray.map((p) => {
        const wanted = rest.includes(p);
        if (wanted) rest.splice(rest.indexOf(p), 1);
        return `<div class="tray-slot ${wanted ? "" : "extra"}" title="${wanted ? "" : "not ordered"}">${g.config.products[p].icon}` +
          `<button data-act="one" data-product="${p}" title="Throw away this ${esc(g.config.products[p].name)}">✕</button></div>`;
      });
      const extras = v.tray.length - (order.items.length - rest.length);
      this.setHtml("#tray", `<span>Order: ${need}</span><span>→ Tray:</span>` +
        (slots.length ? slots.join("") : `<div class="tray-slot"></div>`) +
        (extras > 0 ? `<button data-act="extras" title="Throw away everything the customer did not order">🗑 Throw away extras</button>` : "") +
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
    // v7: with many shops, the ones run by a manager are shown in one compact line
    const managed = owned.length > 2 ? owned.filter((s) => v.shops[s].manager) : [];
    if (v.carried_cash) html += `<div class="stock-shop">💰 Cash to bring to the office: ${euro(v.carried_cash)}</div>`;
    if (managed.length) html += `<div class="stock-shop">🧑‍🍳 Managers run: ${managed.map((s) => cfg.shops[s].icon || "🏪").join(" ")}</div>`;
    for (const s of owned) {
      if (managed.includes(s)) continue;
      const portions = v.shops[s].portions || {};
      if (owned.length > 1) html += `<div class="stock-shop">${esc(cfg.shops[s].name)}${v.shops[s].manager ? " (manager)" : s === v.work_shop ? " (you)" : ""}</div>`;
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
    // The shopping list only matters for the morning shopping, not for a restock during the day.
    const list = v.open || v.closed ? {} : (v.shopping_list || {});
    const keys = [...new Set([...Object.keys(list), ...Object.keys(v.cart || {})])];
    let html = `<h4>${Object.keys(list).length ? "🛒 Shopping list · cart" : "🛒 Cart"}</h4>`;
    if (!keys.length) html += `<div class="row">${v.open ? "Take what you need from the stands" : "Nothing planned yet"}</div>`;
    for (const i of keys) {
      const have = (v.cart || {})[i] || 0;
      if (!(i in list)) { html += `<div class="row"><span>${items[i].icon} ${esc(items[i].name)}</span><span>${have} in cart</span></div>`; continue; }
      const want = list[i];
      const cls = have >= want ? "ok" : "miss";
      const mark = have > want ? `+${have - want} extra` : have === want ? "✔" : `${want - have} missing`;
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
    if (spec.onShow) spec.onShow();
  }
  closeDialog() {
    if (this.current && this.current.onClose) this.current.onClose();
    this.current = null;
    this.$("#modal-layer").classList.add("hidden");
    this.$("#dialog").innerHTML = "";
    if (this.queue.length) {
      const next = this.queue.shift();
      if (!next.valid || next.valid()) { this.current = next; this.renderDialog(); if (next.onShow) next.onShow(); }
      else this.closeDialog();
    }
    this.game.focus();
  }
  refreshDialog() { if (this.current) this.renderDialog(); }
  dialogBody() { return this.$("#dialog .dlg-body"); }
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
      b.onclick = () => { this.game.sound.play("click"); this.pressSecondary(); };
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
      b.onclick = () => { this.game.sound.play("click"); this.pressPrimary(); };
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
