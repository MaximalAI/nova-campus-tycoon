// ---------------------------------------------------------------------------
// Flow: guided daily loop, pop-up catalog P00-P20, students, queues, triggers
// ---------------------------------------------------------------------------
const TICKS = [8.0, 19.75, 20.0, 21.0];

class Flow {
  constructor(game) {
    this.game = game;
    this.agents = new Map();
    this.queues = { cafe: [], rival: [] };
    this.auto = { cafe: null, rival: null };
    this.sentTicks = new Set();
    this.zoneFlags = {};
    this.p09For = null;
    this.progress = null;
    this.wholesaleAllowed = false;
    this.leftWithOrderToast = false;
  }

  get v() { return this.game.view; }
  get cfg() { return this.game.config; }
  send(type, payload, cb) { return this.game.bridge.send(type, payload, cb); }
  ok(cb) { return (r) => { if (r.ok) { if (r.result && r.result.toast) this.game.ui.toast(r.result.toast); if (cb) cb(r.result); } else this.game.ui.toast(r.error, true); }; }

  // ------------------------------------------------------------------ helpers
  playerIn(shop) { return this.game.world.buildingAt(this.game.player.pos) === shop; }
  bagHasItemsFor(shop) {
    if (!this.v) return false;
    const usable = new Set(this.cfg.shops[shop].products.flatMap((p) => Object.keys(this.cfg.products[p].uses)));
    return Object.keys(this.v.bag).some((i) => usable.has(i));
  }
  shopName(shop) { return this.cfg.shops[shop].name; }
  icons(items) { return items.map((p) => this.cfg.products[p].icon).join(" "); }

  objectiveText() {
    if (!this.v) return "";
    if (this.v.day_state === "SHOP_OPEN") {
      const manual = Object.keys(this.v.shops).filter((s) => this.game.isManual(s));
      if (manual.length && !manual.some((s) => this.playerIn(s))) return "Geh in dein Café - Kunden warten an der Theke.";
      if (this.v.current_order) return "Bereite die Bestellung an den Stationen zu und übergib sie.";
    }
    if (this.v.day_state === "WHOLESALE_SHOPPING" && !this.v.in_wholesaler) return "Geh in den Großhandel.";
    return this.v.objective;
  }

  objectiveTarget() {
    const v = this.v;
    if (!v || this.game.ui.dialogOpen) return null;
    switch (v.day_state) {
      case "MORNING_PLANNING": return { x: -37.4, z: -4.9 };
      case "WALK_TO_WHOLESALE": return Object.keys(v.bag).length ? { x: -38.6, z: 3.6 } : P.wholesale.doorOut;
      case "WHOLESALE_SHOPPING": return v.in_wholesaler ? { x: 32, z: 2.3 } : P.wholesale.doorOut;
      case "WALK_TO_CAFE": return this.bagHasItemsFor("cafe") ? { x: -38.6, z: 3.6 } : { x: 4.2, z: -25.5 };
      case "SET_PRICES": return { x: -35.8, z: -0.6 };
      case "SHOP_OPEN": {
        for (const s of ["cafe", "rival"]) if (this.game.isManual(s) && !this.playerIn(s)) return s === "cafe" ? { x: -36.4, z: 0 } : { x: 0.6, z: -22.4 };
        return null;
      }
      case "CLOSING": {
        const it = this.game.world.interactables.find((i) => i.cleaning && !v.cleaning[i.cleaning]);
        return it ? it.pos : null;
      }
      default: return null;
    }
  }

  registerLabel(shop) {
    if (!this.v) return "Kasse";
    if (!this.v.open && !this.v.closed) return "Preise festlegen";
    return "Kasse";
  }
  useRegister(shop) {
    if (!this.v.open && !this.v.closed) return this.openPrices(shop);
    this.game.ui.toast(this.v.open ? "Kassiert wird bei der Übergabe." : "Der Laden ist geschlossen.");
  }
  counterLabel(shop) {
    if (!this.v || !this.game.isManual(shop) || !this.playerIn(shop)) return null;
    const order = this.v.current_order;
    if (order && order.shop === shop) return "Bestellung übergeben";
    const front = this.queues[shop][0] && this.agents.get(this.queues[shop][0]);
    if (front && front.atCounter && !order) return "Bestellung ansehen";
    return null;
  }
  useCounterFront(shop) {
    const order = this.v.current_order;
    if (order && order.shop === shop) return this.openHandover(shop);
    const sid = this.queues[shop][0];
    if (sid) this.openOrder(shop, sid);
  }

  // ------------------------------------------------------------- P00 title
  showTitle(hasSave) {
    const ui = this.game.ui;
    ui.showDialog({
      id: "P00", noEsc: true,
      custom: (box) => {
        box.appendChild(el("div", "title-logo", "☕ Nova Campus<br>Tycoon"));
        box.appendChild(el("div", "title-sub", "Führe dein Café, schlag die Konkurrenz und hol dir das Campus-Monopol."));
        box.appendChild(el("div", "dlg-text",
          "Steuerung: <b>Pfeiltasten/WASD</b> laufen, <b>E</b> oder Klick benutzen, <b>Enter</b> bestätigen, <b>Esc</b> abbrechen, <b>Tab</b> Einkaufszettel, <b>P</b> Pause."));
      },
      extra: hasSave ? [{ label: "Fortsetzen", action: () => { ui.closeDialog(); this.game.startSession("continue_game"); } }] : [],
      primary: { label: "Neues Spiel", action: () => this.game.startSession("new_game") },
    });
  }

  // ------------------------------------------------------------- P01 morning
  openMorning() {
    const v = this.v, y = v.yesterday;
    const stock = [];
    for (const s of Object.keys(v.shops)) for (const [i, e] of Object.entries(v.shops[s].stock)) {
      const days = e.batches.map((b) => b.days_left).filter((d) => d !== null);
      const shelf = days.length ? ` (noch ${Math.min(...days)} Tag${Math.min(...days) === 1 ? "" : "e"})` : "";
      stock.push(`${this.cfg.wholesale_items[i].icon} ${e.units} ${this.cfg.wholesale_items[i].base_name}${shelf}`);
    }
    const sold = y ? Object.entries(y.sold).map(([p, n]) => `${this.cfg.products[p].icon} ${n}`).join(" &nbsp; ") || "nichts" : "noch keine";
    this.game.ui.showDialog({
      id: "P01", icon: "🌅", title: `Guten Morgen, Tag ${v.day}`, unique: true,
      text: v.day === 1
        ? "Willkommen auf dem Campus! Du führst das Café links. Plane deinen Tag an der <b>Planungstafel</b>, kauf im <b>Großhandel</b> ein und öffne um 08:00 Uhr."
        : "Ein neuer Tag beginnt. Was willst du heute verkaufen?",
      rows: [
        { label: "Kassenstand", value: euro(v.money) },
        { label: "Lager", value: stock.join("<br>") || "leer" },
        { label: "Verkauft gestern", value: sold },
      ],
      primary: { label: "Los geht's" },
    });
  }

  // ------------------------------------------------------------- P02 planning
  openPlanning() {
    const v = this.v, ui = this.game.ui;
    const products = Object.keys(v.shops).filter((s) => v.shops[s].owner === "player").flatMap((s) => this.cfg.shops[s].products);
    const unique = [...new Set(products)];
    const plan = Object.fromEntries(unique.map((p) => [p, v.plan[p] ?? 0]));
    const items = this.cfg.wholesale_items;
    const need = () => {
      // Display only; Python computes the binding shopping list when confirming.
      const units = {};
      for (const [p, n] of Object.entries(plan)) for (const [i, q] of Object.entries(this.cfg.products[p].uses)) units[i] = (units[i] || 0) + n * q;
      const out = {};
      for (const [i, u] of Object.entries(units)) {
        let have = 0;
        for (const s of Object.keys(v.shops)) if (v.shops[s].owner === "player" && v.shops[s].stock[i]) have += v.shops[s].stock[i].units;
        const packs = Math.ceil(Math.max(0, u - have) / items[i].base_units);
        if (packs) out[i] = packs;
      }
      return out;
    };
    ui.showDialog({
      id: "P02", icon: "📋", title: "Tagesplanung",
      text: "Wie viele Portionen willst du heute verkaufen? Daraus entsteht dein Einkaufszettel.",
      body: (body) => {
        const draw = () => {
          body.innerHTML = "";
          for (const p of unique) {
            const line = el("div", "line");
            line.appendChild(el("div", "lbl", `<span class="ic">${this.cfg.products[p].icon}</span><div>${esc(this.cfg.products[p].name)}</div>`));
            const stp = el("div", "stepper");
            const minus = el("button", "", "−"), plus = el("button", "", "+"), val = el("span", "", String(plan[p]));
            minus.onclick = () => { plan[p] = Math.max(0, plan[p] - (p === "coffee" ? 5 : 1)); draw(); };
            plus.onclick = () => { plan[p] += p === "coffee" ? 5 : 1; draw(); };
            stp.append(minus, val, plus); line.appendChild(stp); body.appendChild(line);
          }
          const list = need();
          const cost = Object.entries(list).reduce((a, [i, q]) => a + q * items[i].price, 0);
          const rows = Object.entries(list).map(([i, q]) => `<div>${items[i].icon} ${q}x ${esc(items[i].name)} <span class="sub">(${esc(items[i].unit)})</span></div>`).join("") || "<div>Nichts nötig - dein Lager reicht.</div>";
          body.appendChild(el("div", "note", `<b>Einkaufszettel:</b>${rows}<b>Geschätzte Kosten: ${euro(cost)}</b>` +
            (cost > v.money ? `<div class="warn">Mehr als dein Kassenstand (${euro(v.money)})!</div>` : "")));
        };
        draw();
      },
      secondary: { label: "Abbrechen" },
      primary: { label: "Einkaufszettel speichern", action: () => { this.send("confirm_plan", { plan }, this.ok()); } },
    });
  }

  // -------------------------------------------------------- P03 wholesaler
  askWholesale() {
    const v = this.v;
    const list = Object.entries(v.shopping_list).map(([i, q]) => `${this.cfg.wholesale_items[i].icon} ${q}x ${esc(this.cfg.wholesale_items[i].name)}`).join("<br>") || "Kein Einkaufszettel - du kannst trotzdem einkaufen.";
    this.game.ui.showDialog({
      id: "P03", icon: "🏬", title: "Großhandel betreten?", unique: true,
      text: "Hier bekommst du alle Zutaten. Dein Warenkorb ist mit dem Einkaufszettel vorbelegt.",
      rows: [{ label: "Einkaufszettel", value: list }],
      secondary: { label: "Später" },
      primary: { label: "Betreten", action: () => {
        this.send("enter_wholesaler", {}, this.ok(() => { this.wholesaleAllowed = true; }));
      } },
    });
  }

  // -------------------------------------------------------- P04 item
  openItem(item) {
    const spec = this.cfg.wholesale_items[item], ui = this.game.ui;
    if (!this.v.in_wholesaler) return ui.toast("Du bist nicht im Großhandel.", true);
    let qty = this.v.cart[item] ?? this.v.shopping_list[item] ?? 0;
    const others = () => this.v.cart_total - (this.v.cart[item] || 0) * spec.price;
    ui.showDialog({
      id: "P04", icon: spec.icon, title: `Ware: ${spec.name}`, text: esc(spec.description),
      body: (body) => {
        const draw = () => {
          body.innerHTML = "";
          const shelf = spec.shelf_days === null ? "unbegrenzt" : spec.shelf_days === 1 ? "1 Tag" : `${spec.shelf_days} Tage`;
          const t = el("table", "dlg-rows",
            `<tr><td>Preis</td><td>${euro(spec.price)} / ${esc(spec.unit)}</td></tr>` +
            `<tr><td>Reicht für</td><td>${spec.base_units} ${esc(spec.base_name)}</td></tr>` +
            `<tr><td>Haltbarkeit</td><td>${shelf}</td></tr>`);
          body.appendChild(t);
          const line = el("div", "line");
          line.appendChild(el("div", "lbl", "<b>Menge</b>"));
          const stp = el("div", "stepper");
          const minus = el("button", "", "−"), plus = el("button", "", "+"), val = el("span", "", String(qty));
          minus.onclick = () => { qty = Math.max(0, qty - 1); draw(); };
          plus.onclick = () => { qty += 1; draw(); };
          stp.append(minus, val, plus); line.appendChild(stp); body.appendChild(line);
          const total = others() + qty * spec.price;
          const bad = total > this.v.money;
          body.appendChild(el("table", "dlg-rows",
            `<tr><td>Zwischensumme</td><td>${euro(qty * spec.price)}</td></tr>` +
            `<tr class="total"><td>Warenkorb gesamt</td><td class="${bad ? "bad" : ""}">${euro(total)}</td></tr>` +
            (bad ? `<tr><td colspan="2" class="bad">Nicht genug Geld (Kasse: ${euro(this.v.money)})</td></tr>` : "")));
        };
        draw();
      },
      secondary: { label: "Abbrechen" },
      primary: { label: "In den Warenkorb", action: () => { this.send("set_cart_item", { item, qty }, this.ok()); } },
    });
  }

  // -------------------------------------------------------- P05 checkout
  openCheckout() {
    const v = this.v, items = this.cfg.wholesale_items;
    if (!v.in_wholesaler) return;
    if (!Object.keys(v.cart).length) return this.game.ui.toast("Dein Warenkorb ist leer.");
    const rows = Object.entries(v.cart).map(([i, q]) => ({ label: `${items[i].icon} ${q}x ${esc(items[i].name)} à ${euro(items[i].price)}`, value: euro(q * items[i].price) }));
    const after = v.money - v.cart_total;
    rows.push({ label: "Summe", value: euro(v.cart_total), cls: "total" });
    rows.push({ label: "Kassenstand vorher", value: euro(v.money) });
    rows.push({ label: "Kassenstand nachher", value: euro(after), vcls: after < 0 ? "bad" : "good" });
    this.game.ui.showDialog({
      id: "P05", icon: "🧾", title: "Kasse Großhandel",
      text: "Der Kassierer lächelt: <i>„Bom dia! Alles gefunden?“</i>" + (after < 0 ? `<div class="warn">Nicht genug Geld - nimm etwas aus dem Warenkorb.</div>` : ""),
      rows,
      secondary: { label: "Zurück zum Einkauf" },
      primary: { label: "Bezahlen", disabled: after < 0, action: () => { this.send("pay", {}, this.ok()); } },
    });
  }

  // -------------------------------------------------------- P06 stock goods
  openStock(shop) {
    const v = this.v, items = this.cfg.wholesale_items;
    if (!this.bagHasItemsFor(shop)) return;
    const usable = new Set(this.cfg.shops[shop].products.flatMap((p) => Object.keys(this.cfg.products[p].uses)));
    const rows = Object.entries(v.bag).filter(([i]) => usable.has(i)).map(([i, q]) => ({
      label: `${items[i].icon} ${q}x ${esc(items[i].name)}`, value: `${q * items[i].base_units} ${esc(items[i].base_name)}` }));
    this.game.ui.showDialog({
      id: "P06", icon: "📦", title: "Waren einräumen", unique: true,
      text: "Deine Einkaufstasche ist voll. Räum alles ins Lager.",
      rows,
      primary: { label: "Einräumen", action: () => { this.send("stock_goods", { shop }, this.ok()); } },
    });
  }

  // -------------------------------------------------------- P07 prices, P08 open
  openPrices(shop) {
    const v = this.v, ui = this.game.ui;
    const prices = Object.assign({}, v.shops[shop].prices);
    const cost = (p) => Object.entries(this.cfg.products[p].uses).reduce((a, [i, q]) =>
      a + q * this.cfg.wholesale_items[i].price / this.cfg.wholesale_items[i].base_units, 0);
    ui.showDialog({
      id: "P07", icon: "🏷️", title: `Preise festlegen - ${this.shopName(shop)}`,
      text: "Höhere Preise bringen mehr Marge, aber weniger Studenten finden das Angebot lohnend.",
      body: (body) => {
        const draw = () => {
          body.innerHTML = "";
          for (const p of Object.keys(prices)) {
            const line = el("div", "line");
            const margin = prices[p] - cost(p);
            line.appendChild(el("div", "lbl", `<span class="ic">${this.cfg.products[p].icon}</span><div>${esc(this.cfg.products[p].name)}<div class="sub">Kosten ${euro(cost(p))} · Marge <span style="color:${margin >= 0 ? "#23784a" : "#d9534f"}">${euro(margin)}</span></div></div>`));
            const stp = el("div", "stepper");
            const minus = el("button", "", "−"), plus = el("button", "", "+"), val = el("span", "", euro(prices[p]));
            minus.onclick = () => { prices[p] = Math.max(10, prices[p] - 10); draw(); };
            plus.onclick = () => { prices[p] = Math.min(this.cfg.max_price, prices[p] + 10); draw(); };
            stp.append(minus, val, plus); line.appendChild(stp); body.appendChild(line);
          }
          if (v.shops.rival.owner === "bot") {
            const rp = v.shops.rival.prices;
            body.appendChild(el("div", "note", "Konkurrenz: " + Object.entries(rp).map(([p, c]) => `${this.cfg.products[p].icon} ${euro(c)}`).join(" · ")));
          }
        };
        draw();
      },
      secondary: { label: "Abbrechen" },
      primary: { label: "Preise übernehmen", action: () => {
        this.send("set_prices", { shop, prices }, this.ok(() => { if (!this.v.open && this.game.clock.t >= 7) this.askOpen(); }));
      } },
    });
  }

  askOpen() {
    const v = this.v;
    if (v.open || v.closed) return;
    const waiting = this.queues.cafe.length;
    this.game.ui.showDialog({
      id: "P08", icon: "🚪", title: "Laden öffnen?", unique: true,
      text: this.game.clock.t < 7 ? "Öffnen kannst du ab 07:00 Uhr. Um 08:00 Uhr öffnet der Laden automatisch."
        : `Es ist ${fmtTime(this.game.clock.t)} Uhr. ${waiting ? `${waiting} Student${waiting === 1 ? "" : "en"} warten schon vor der Tür.` : "Noch wartet niemand."}`,
      secondary: { label: "Noch nicht" },
      primary: { label: "Öffnen", disabled: this.game.clock.t < 7, action: () => { this.send("open_shop", {}, this.ok(() => this.onOpened())); } },
    });
  }

  // -------------------------------------------------------- P09 new order
  openOrder(shop, sid) {
    const a = this.agents.get(sid);
    if (!a || !a.atCounter || a.mode !== "queue" || this.v.current_order) return;
    this.p09For = sid;
    const items = a.order || [];
    const chips = items.map((p) => `<span class="chip">${this.cfg.products[p].icon} ${esc(this.cfg.products[p].name)}</span>`).join("") +
      (a.soldOut || []).map((p) => `<span class="chip off">${this.cfg.products[p].icon} ${esc(this.cfg.products[p].name)}</span>`).join("");
    const total = items.reduce((s, p) => s + this.v.shops[shop].prices[p], 0);
    const dlg = {
      id: "P09", icon: "🙋", title: `Neue Bestellung - ${a.info.name}`, unique: true,
      valid: () => this.queues[shop][0] === sid && !this.v.current_order && a.mode === "queue",
      body: (body) => {
        body.appendChild(el("div", "chips", chips));
        if ((a.soldOut || []).length) body.appendChild(el("div", "note", "Durchgestrichen = ausverkauft."));
        const pb = el("div", "progress"); const bar = el("div"); pb.appendChild(bar); body.appendChild(pb);
        const f = clamp(a.patience / a.patienceMax, 0, 1);
        bar.style.width = `${f * 100}%`;
        bar.style.background = f > 0.5 ? "#2f9e5b" : f > 0.25 ? "#f2c94c" : "#d9534f";
        body.appendChild(el("div", "note", `Geduld · Wert der Bestellung ${euro(total)}`));
      },
      // Closing without a decision lets the dialog come back; after a decision we wait for Python.
      onClose: () => { if (!dlg.decided) this.p09For = null; },
      secondary: { label: "Ablehnen", action: () => {
        dlg.decided = true;
        a.mode = "rejected";
        this.send("reject", { shop, student: sid }, (r) => {
          this.p09For = null;
          this.removeFromQueue(shop, sid);
          const decision = r.ok ? r.result : { action: "wander" };
          a.inside = false; a.mode = "exiting";
          a.walkTo([P[shop].doorIn, P[shop].doorOut], () => this.handleDecision(a, decision));
        });
      } },
      primary: { label: "Annehmen", action: () => {
        dlg.decided = true;
        a.mode = "served"; // optimistic, so the dialog does not open again while Python answers
        this.send("accept", { shop, student: sid, player_inside: this.playerIn(shop) }, (r) => {
          this.p09For = null;
          if (r.ok) { a.patience = a.patienceMax; return; }
          a.mode = "queue";
          this.game.ui.toast(r.error, true);
        });
      } },
    };
    this.game.ui.showDialog(dlg);
  }

  // -------------------------------------------------- P10-P12 stations (progress)
  openStation(shop, product) {
    const v = this.v, spec = this.cfg.products[product];
    const order = v.current_order;
    if (!order || order.shop !== shop) return this.game.ui.toast("Nimm zuerst eine Bestellung an der Theke an.");
    if (!v.shops[shop].can_make[product]) return this.game.ui.toast(`${spec.name} ist ausverkauft.`, true);
    const ids = { coffee: "P10", orange_juice: "P11", pastel_de_nata: "P12", tea: "P10", croissant: "P12" };
    const verbs = { coffee: "Starten", orange_juice: "Pressen", pastel_de_nata: "Nehmen", tea: "Aufgießen", croissant: "Nehmen" };
    const steps = {
      coffee: "Tasse unterstellen, Knopf drücken - der Espresso läuft.",
      orange_juice: "Drei Orangen einlegen und pressen.",
      pastel_de_nata: "Ein Pastel de Nata aus der Vitrine aufs Tablett legen.",
      tea: "Beutel in die Tasse, heißes Wasser drauf.",
      croissant: "Ein Croissant aus der Vitrine nehmen.",
    };
    const needed = order.items.filter((p) => p === product).length - v.tray.filter((p) => p === product).length;
    let bar = null;
    const dlg = {
      id: ids[product], icon: spec.icon, title: `${spec.name} ${product === "orange_juice" ? "pressen" : product === "coffee" || product === "tea" ? "zubereiten" : "nehmen"}`,
      text: steps[product] + (needed <= 0 ? `<div class="warn">Steht nicht (mehr) auf der Bestellung!</div>` : ""),
      body: (body) => {
        const pb = el("div", "progress"); bar = el("div"); pb.appendChild(bar); body.appendChild(pb);
        body.appendChild(el("div", "note", `Dauer: ${spec.prep_minutes} Spielminuten`));
      },
      secondary: { label: "Abbrechen" },
      primary: { label: verbs[product], action: () => {
        dlg.busy = true;
        this.game.ui.primaryButton.disabled = true;
        this.progress = { minutes: spec.prep_minutes, done: 0, bar: () => bar, onDone: () => {
          this.send("prepare", { shop, product, player_inside: this.playerIn(shop) }, this.ok());
          dlg.busy = false; this.game.ui.closeDialog();
        } };
        return "keep";
      } },
      onClose: () => { if (this.progress && dlg.busy) this.progress = null; },
    };
    this.game.ui.showDialog(dlg);
  }

  // -------------------------------------------------------- P13 handover
  openHandover(shop) {
    const v = this.v, order = v.current_order;
    if (!order) return;
    const tray = [...v.tray];
    const chips = order.items.map((p) => {
      const i = tray.indexOf(p);
      if (i >= 0) { tray.splice(i, 1); return `<span class="chip ok">✔ ${this.cfg.products[p].icon} ${esc(this.cfg.products[p].name)}</span>`; }
      return `<span class="chip miss">✘ ${this.cfg.products[p].icon} ${esc(this.cfg.products[p].name)}</span>`;
    }).join("") + tray.map((p) => `<span class="chip miss">+ ${this.cfg.products[p].icon} zu viel</span>`).join("");
    const a = this.agents.get(order.student);
    this.game.ui.showDialog({
      id: "P13", icon: "🤝", title: `Bestellung übergeben - ${a ? a.info.name : ""}`,
      text: "Bestellung gegen Tablett:",
      body: (body) => body.appendChild(el("div", "chips", chips)),
      secondary: { label: "Abbrechen" },
      primary: { label: "Übergeben", action: () => {
        this.send("handover", { shop, student: order.student, player_inside: this.playerIn(shop) }, (r) => {
          if (!r.ok) return this.game.ui.toast(r.error, true);
          this.game.ui.toast(r.result.toast, !r.result.correct);
          this.removeFromQueue(shop, order.student);
          if (a) this.exitShop(a, shop);
        });
      } },
    });
  }

  // -------------------------------------------------------- P14/P15 closing
  openClosing() {
    const spots = Object.values(this.cfg.cleaning_spots).map((s) => `• ${s.name}`).join("<br>");
    this.game.ui.showDialog({
      id: "P14", icon: "🌙", title: "Ladenschluss", unique: true, urgent: true,
      text: `Es ist 20:00 Uhr. Das Schild zeigt „Geschlossen“. Wartende Kunden gehen nach Hause.<br><br>Räum jetzt auf:<br>${spots}`,
      primary: { label: "Aufräumen" },
    });
  }
  openCleaning(spot) {
    const spec = this.cfg.cleaning_spots[spot];
    let bar = null;
    const icons = { counter: "🧽", coffee_machine: "☕", tables: "🍽️", floor: "🧹" };
    const dlg = {
      id: "P15", icon: icons[spot], title: `Aufräumen: ${spec.name}`,
      body: (body) => { const pb = el("div", "progress"); bar = el("div"); pb.appendChild(bar); body.appendChild(pb); },
      primary: { label: "Starten", action: () => {
        dlg.busy = true; this.game.ui.primaryButton.disabled = true;
        this.progress = { minutes: spec.minutes, done: 0, bar: () => bar, onDone: () => {
          this.send("clean", { spot }, this.ok((res) => { if (res.summary) this.openSummary(); }));
          dlg.busy = false; this.game.ui.closeDialog();
        } };
        return "keep";
      } },
    };
    this.game.ui.showDialog(dlg);
  }

  // -------------------------------------------------------- P16 summary
  openSummary() {
    const s = this.v.summary;
    if (!s) return;
    const products = this.cfg.products;
    this.game.ui.showDialog({
      id: "P16", icon: "📊", title: `Tagesbilanz - Tag ${s.day}`, unique: true, noEsc: true,
      rows: [
        { label: "Umsatz", value: euro(s.revenue), vcls: "good" },
        { label: "Einkaufskosten", value: euro(-s.purchase_cost) },
        { label: "Ausbau & Personal", value: euro(-s.spending) },
        { label: "<b>Gewinn</b>", value: euro(s.profit), cls: "total", vcls: s.profit >= 0 ? "good" : "bad" },
        { label: "Verdorbene Ware (im Einkauf enthalten)", value: euro(s.spoiled_value), vcls: s.spoiled_value ? "bad" : "" },
        { label: "Kunden bedient / verloren", value: `${s.served} / ${s.lost}` + (s.wrong ? ` · ${s.wrong} falsch` : "") },
        { label: "Ruf", value: `${s.reputation} / 100` },
        { label: "Marktanteil", value: `${Math.round(s.market_share * 100)} %` },
        { label: "Kassenstand", value: euro(s.money) },
      ],
      body: (body) => {
        const keys = [...new Set([...Object.keys(s.plan), ...Object.keys(s.sold)])].filter((p) => (s.plan[p] || s.sold[p]));
        if (!keys.length) return;
        const max = Math.max(1, ...keys.map((p) => Math.max(s.plan[p] || 0, s.sold[p] || 0)));
        const bars = el("div", "bars");
        for (const p of keys) {
          const b = el("div", "bar");
          b.innerHTML = `<div class="pair">` +
            `<span class="col plan" style="height:${(s.plan[p] || 0) / max * 70}px"></span>` +
            `<span class="col sold" style="height:${(s.sold[p] || 0) / max * 70}px"></span></div>${products[p].icon} ${s.sold[p] || 0}/${s.plan[p] || 0}`;
          bars.appendChild(b);
        }
        body.appendChild(el("div", "note", "<b>Verkauft gegen Plan</b> (grau = Plan, grün = verkauft)"));
        body.appendChild(bars);
      },
      primary: { label: this.v.status === "running" ? "Nächster Tag" : "Weiter", action: () => {
        if (this.v.status !== "running") return this.openEnd();
        this.game.fade(() => this.send("next_day", {}, this.ok()));
      } },
    });
  }

  // -------------------------------------------------------- P17 competitor
  openCompetitor() {
    const v = this.v;
    const prices = Object.entries(v.shops.rival.prices).map(([p, c]) => ({ label: `${this.cfg.products[p].icon} ${esc(this.cfg.products[p].name)}`, value: euro(c) }));
    const can = v.can_buy_competitor;
    this.game.ui.showDialog({
      id: "P17", icon: "🏪", title: `Konkurrenz - ${this.shopName("rival")}`, unique: true,
      text: can ? `Der Besitzer wäre bereit zu verkaufen: <b>${euro(this.cfg.acquisition_cost)}</b>.`
        : `Die Konkurrenz hat feste Preise und einen guten Ruf (Faktor ${v.shops.rival.factor.toFixed(2)}). ` +
          `Mit einem Manager in deinem Café kannst du sie später für ${euro(this.cfg.acquisition_cost)} kaufen.`,
      rows: prices,
      secondary: can ? { label: "Später" } : null,
      primary: can ? { label: "Café kaufen", disabled: v.money < this.cfg.acquisition_cost,
        action: () => { this.send("buy_competitor", {}, this.ok(() => this.checkEnd())); } } : { label: "OK" },
    });
  }

  // -------------------------------------------------------- P18 upgrades
  openUpgrades() {
    const ui = this.game.ui;
    const dlg = {
      id: "P18", icon: "🛠️", title: "Ausbau & Personal",
      text: "Upgrades machen deinen Laden attraktiver (Nutzenfaktor). Ein Manager bedient selbstständig.",
      body: (body) => {
        const v = this.v;
        for (const shop of Object.keys(v.shops)) {
          if (v.shops[shop].owner !== "player") continue;
          body.appendChild(el("div", "note", `<b>${esc(this.shopName(shop))}</b> · Faktor ${v.shops[shop].factor.toFixed(2)}`));
          for (const [u, spec] of Object.entries(this.cfg.upgrades)) {
            const line = el("div", "line");
            line.appendChild(el("div", "lbl", `<span class="ic">${spec.icon}</span><div>${esc(spec.name)}<div class="sub">+${spec.factor_bonus.toFixed(2)} Faktor · ${euro(spec.cost)}</div></div>`));
            if (v.shops[shop].upgrades.includes(u)) line.appendChild(el("span", "chip ok", "✔ gekauft"));
            else {
              const b = el("button", "btn primary", "Kaufen");
              b.disabled = v.money < spec.cost;
              b.onclick = () => this.send("buy_upgrade", { shop, upgrade: u }, this.ok(() => ui.refreshDialog()));
              line.appendChild(b);
            }
            body.appendChild(line);
          }
          const line = el("div", "line");
          line.appendChild(el("div", "lbl", `<span class="ic">🧑‍🍳</span><div>Manager<div class="sub">bedient automatisch · ${euro(this.cfg.manager_cost)}</div></div>`));
          if (v.shops[shop].manager) line.appendChild(el("span", "chip ok", "✔ eingestellt"));
          else {
            const b = el("button", "btn primary", "Einstellen");
            b.disabled = v.money < this.cfg.manager_cost;
            b.onclick = () => this.send("hire_manager", { shop }, this.ok(() => { ui.refreshDialog(); this.checkEnd(); }));
            line.appendChild(b);
          }
          body.appendChild(line);
        }
      },
      primary: { label: "Schließen" },
    };
    ui.showDialog(dlg);
  }

  // -------------------------------------------------------- P19 end, P20 pause
  checkEnd() {
    setTimeout(() => {
      if (!this.v || this.v.status === "running") return;
      const ui = this.game.ui;
      ui.queue = [];
      if (ui.current) { ui.current.busy = false; ui.closeDialog(); }
      this.openEnd();
    }, 50);
  }
  openEnd() {
    const v = this.v, win = v.status === "victory";
    this.game.ui.showDialog({
      id: "P19", icon: win ? "🏆" : "💸", title: win ? "Monopol erreicht!" : "Pleite!", unique: true, noEsc: true, urgent: true,
      text: win ? `Beide Cafés gehören dir und laufen mit Managern. Du hast den Campus nach <b>${v.day} Tagen</b> erobert.`
        : "Dein Kassenstand ist am Ende des Tages auf 0 € oder darunter gefallen.",
      rows: [{ label: "Tage gespielt", value: String(v.day) }, { label: "Gesamtgewinn", value: euro(v.total_profit) }],
      primary: { label: "Neues Spiel", action: () => this.game.startSession("new_game") },
    });
  }
  openPause() {
    const g = this.game;
    if (!g.view || g.ui.current?.id === "P20") return;
    if (g.ui.dialogOpen && !g.ui.current.pausable) { g.clock.paused = !g.clock.paused; return; }
    g.clock.paused = true;
    g.ui.showDialog({
      id: "P20", icon: "⏸️", title: "Pause", urgent: true,
      text: "Alles steht still: Uhr, Studenten und Fortschrittsbalken. Dein Spiel wird automatisch gespeichert.",
      onClose: () => { g.clock.paused = false; },
      extra: [{ label: "Speichern & beenden", cls: "secondary", action: () => { g.ui.closeDialog(); g.startSession("quit"); } }],
      primary: { label: "Weiter" },
    });
  }

  // ------------------------------------------------------------------ events
  onOpened() { for (const s of ["cafe", "rival"]) this.repositionQueue(s); }

  sendTicks(force = false) {
    const t = this.game.clock.t;
    for (const mark of TICKS) {
      if (t + 1e-6 >= mark && !this.sentTicks.has(mark)) {
        this.sentTicks.add(mark);
        this.send("tick", {}, (r) => {
          if (!r.ok) return;
          const res = r.result;
          if (res.toast) this.game.ui.toast(res.toast);
          if (res.opened) this.onOpened();
          if (res.closed) { this.game.setSpeed(1); this.onClosed(); }
          if (res.summary) this.openSummary();
        });
      }
    }
  }

  onClosed() {
    const ui = this.game.ui;
    if (ui.current && ["P09", "P10", "P11", "P12", "P13"].includes(ui.current.id)) { ui.current.busy = false; this.progress = null; ui.closeDialog(); }
    ui.queue = ui.queue.filter((d) => !["P09", "P13"].includes(d.id));
    for (const shop of ["cafe", "rival"]) {
      for (const sid of [...this.queues[shop]]) {
        const a = this.agents.get(sid);
        this.removeFromQueue(shop, sid);
        if (a) this.exitShop(a, shop);
      }
      this.auto[shop] = null;
    }
    this.openClosing();
  }

  // ---------------------------------------------------------------- students
  resetDay(plan, view) {
    for (const a of this.agents.values()) this.game.scene.remove(a.figure.group);
    this.agents.clear();
    this.queues = { cafe: [], rival: [] };
    this.auto = { cafe: null, rival: null };
    this.sentTicks = new Set(TICKS.filter((m) => view.time > m + 1e-6 || (m === 8 && view.open) || (m === 20 && view.closed)));
    this.zoneFlags = {};
    this.p09For = null;
    this.progress = null;
    this.wholesaleAllowed = view.in_wholesaler;
    const t = view.time;
    for (const [sid, info] of Object.entries(view.students)) {
      const a = new StudentAgent(this.game, sid, info);
      const sched = plan.schedule[sid];
      a.presence = sched.presence;
      a.decisions = sched.decisions;
      a.pIdx = a.presence.findIndex(([, b]) => b > t);
      if (a.pIdx < 0) a.pIdx = a.presence.length;
      a.dIdx = a.decisions.findIndex((d) => d >= t);
      if (a.dIdx < 0) a.dIdx = a.decisions.length;
      if (info.status !== "off_map") {
        // continuing a saved game: put the student somewhere on campus
        const wp = this.game.world.wanderPoints[Math.floor(hashRand(sid + t) * this.game.world.wanderPoints.length)];
        a.pos = { x: wp.x, z: wp.z }; a.figure.place(a.pos); a.figure.visible = true;
        a.mode = "idle"; a.waitUntil = t;
        a.visit = 1;
      }
      this.agents.set(sid, a);
    }
  }

  spawnPoint(a) {
    const pts = this.game.world.edgePoints;
    return pts[Math.floor(hashRand(a.id + ":" + a.visit) * pts.length)];
  }

  wanderTarget(a) {
    const pts = this.game.world.wanderPoints;
    const p = pts[Math.floor(Math.random() * pts.length)];
    return { x: p.x + a.offset.x * 2, z: p.z + a.offset.z * 2 };
  }

  startWander(a) {
    a.mode = "wandering";
    a.walkTo(this.game.world.findPath(a.pos, this.wanderTarget(a)), () => {
      a.mode = "idle";
      a.waitUntil = this.game.clock.t + (2 + Math.random() * 6) / 60;
    });
  }

  handleDecision(a, res) {
    if (!res || res.action !== "shop") { if (a.mode !== "leaving" && a.mode !== "off") this.startWander(a); return; }
    a.mode = "to_shop";
    a.shop = res.shop;
    a.wanted = res.items;
    a.atCounter = false; a.order = null; a.soldOut = [];
    const door = P[res.shop].doorOut;
    a.walkTo(this.game.world.findPath(a.pos, { x: door.x + a.offset.x, z: door.z + a.offset.z }), () => this.reachShop(a));
  }

  reachShop(a) {
    const shop = a.shop;
    if (this.v.closed) return this.startWander(a);
    if (this.queues[shop].length >= this.cfg.max_queue) {
      return this.send("queue_full", { student: a.id, shop }, (r) => this.handleDecision(a, r.ok ? r.result : null));
    }
    this.queues[shop].push(a.id); // reserve the slot right away
    a.mode = "queue";
    a.patience = a.patienceMax;
    a.inside = false;
    this.send("join_queue", { student: a.id, shop }, (r) => {
      if (!r.ok || r.result.action) {
        this.removeFromQueue(shop, a.id);
        this.handleDecision(a, r.ok ? r.result : null);
        return;
      }
      this.repositionQueue(shop);
    });
    this.repositionQueue(shop);
  }

  removeFromQueue(shop, sid) {
    const q = this.queues[shop];
    const i = q.indexOf(sid);
    if (i >= 0) q.splice(i, 1);
    if (this.auto[shop] && this.auto[shop].sid === sid) this.auto[shop] = null;
    const a = this.agents.get(sid);
    if (a) { a.atCounter = false; a.pendingCounter = false; }
    this.repositionQueue(shop);
  }

  repositionQueue(shop) {
    const open = this.v && this.v.open;
    this.queues[shop].forEach((sid, i) => {
      const a = this.agents.get(sid);
      if (!a) return;
      const spots = open ? P[shop].queue : P[shop].outside;
      const spot = spots[Math.min(i, spots.length - 1)];
      const key = `${open}:${i}`;
      if (a.slotKey === key) return;
      a.slotKey = key;
      if (a.mode === "served") a.mode = "served"; else a.mode = "queue";
      const pts = [];
      if (open && !a.inside) { pts.push(P[shop].doorOut, P[shop].doorIn); a.inside = true; }
      pts.push(spot);
      a.walkTo(pts, () => a.faceTo(shop === "cafe" ? { x: -40, z: spot.z } : { x: spot.x, z: -30 }));
    });
  }

  exitShop(a, shop) {
    a.slotKey = null; a.shop = null; a.atCounter = false; a.order = null;
    a.mode = "exiting";
    const pts = a.inside ? [P[shop].doorIn, P[shop].doorOut] : [];
    a.inside = false;
    if (!pts.length) return this.startWander(a);
    a.walkTo(pts, () => this.startWander(a));
  }

  updateStudents(dtReal, dtGameMin) {
    const t = this.game.clock.t;
    const speed = this.game.clock.running ? this.game.clock.speed : 0;
    for (const a of this.agents.values()) {
      // arrivals
      if (a.mode === "off" && a.pIdx < a.presence.length) {
        const [arr, lv] = a.presence[a.pIdx];
        if (t >= arr && t < lv) {
          a.visit += 1;
          const sp = this.spawnPoint(a);
          a.pos = { x: sp.x, z: sp.z }; a.figure.place(a.pos); a.figure.visible = true;
          a.mode = "arriving";
          this.send("student_arrive", { student: a.id }, () => {});
          a.walkTo(this.game.world.findPath(a.pos, this.wanderTarget(a)), () => { a.mode = "idle"; a.waitUntil = t; });
        } else if (t >= lv) a.pIdx += 1;
      }
      // leaving for a lecture or home
      if (["wandering", "idle", "arriving", "to_shop"].includes(a.mode) && a.pIdx < a.presence.length && t >= a.presence[a.pIdx][1]) {
        a.mode = "leaving";
        this.send("student_leave", { student: a.id }, () => {});
        const edge = this.game.world.edgePoints.reduce((best, p) => (dist2(p, a.pos) < dist2(best, a.pos) ? p : best));
        a.walkTo(this.game.world.findPath(a.pos, edge), () => { a.mode = "off"; a.figure.visible = false; a.pIdx += 1; });
      }
      // decisions at their scheduled times
      while (a.dIdx < a.decisions.length && a.decisions[a.dIdx] <= t) {
        const at = a.decisions[a.dIdx++];
        if (["wandering", "idle", "arriving"].includes(a.mode)) {
          a.mode = "deciding";
          this.send("decide", { student: a.id, at }, (r) => {
            if (a.mode !== "deciding") return;
            if (r.ok && r.result.action === "busy") { a.mode = "idle"; return; }
            this.handleDecision(a, r.ok ? r.result : null);
          });
        }
      }
      if (a.mode === "idle" && t >= a.waitUntil) this.startWander(a);
      // patience while queuing / being served: runs from opening time on, also when the player is away
      if ((a.mode === "queue" || a.mode === "served") && a.shop && this.queues[a.shop].includes(a.id) && speed && this.v.open) {
        a.patience -= dtGameMin;
        if (a.patience <= 0 && !a.expiring) this.patienceExpired(a);
      }
      a.update(dtReal * speed);
    }
    // front of every queue
    for (const shop of ["cafe", "rival"]) this.updateCounter(shop, dtGameMin);
  }

  patienceExpired(a) {
    a.expiring = true;
    const shop = a.shop;
    this.send("patience_expired", { student: a.id, shop }, (r) => {
      a.expiring = false;
      const ui = this.game.ui;
      if (r.ok && r.result.toast && this.v.shops[shop].owner === "player") ui.toast(r.result.toast, true);
      if (this.p09For === a.id && ui.current?.id === "P09") ui.closeDialog();
      if (["P10", "P11", "P12", "P13"].includes(ui.current?.id) && !this.v.current_order) {
        this.progress = null; ui.current.busy = false; ui.closeDialog();
      }
      this.removeFromQueue(shop, a.id);
      const decision = r.ok ? r.result : null;
      if (a.inside) {
        a.inside = false; a.mode = "exiting";
        a.walkTo([P[shop].doorIn, P[shop].doorOut], () => this.handleDecision(a, decision));
      } else this.handleDecision(a, decision);
    });
  }

  updateCounter(shop, dtGameMin) {
    const v = this.v;
    if (!v.open) return;
    const sid = this.queues[shop][0];
    const a = sid && this.agents.get(sid);
    if (!a || a.path.length || !a.inside || a.expiring) return;
    if (!a.atCounter && !a.pendingCounter && a.mode === "queue") {
      a.pendingCounter = true;
      this.send("at_counter", { student: sid, shop }, (r) => {
        a.pendingCounter = false;
        if (!r.ok) { this.removeFromQueue(shop, sid); this.exitShop(a, shop); return; }
        if (r.result.leaves) {
          this.removeFromQueue(shop, sid);
          a.walkTo([P[shop].doorIn, P[shop].doorOut], () => this.handleDecision(a, r.result.decision));
          a.inside = false; a.mode = "exiting";
          return;
        }
        a.order = r.result.items; a.soldOut = r.result.sold_out; a.atCounter = true;
      });
      return;
    }
    if (!a.atCounter) return;
    if (v.shops[shop].auto) {
      if (!this.auto[shop]) {
        const minutes = a.order.reduce((s, p) => s + this.cfg.products[p].prep_minutes, 0);
        this.auto[shop] = { sid, remain: minutes };
      }
      if (this.game.clock.running) this.auto[shop].remain -= dtGameMin;
      if (this.auto[shop].remain <= 0 && !this.auto[shop].sent) {
        this.auto[shop].sent = true;
        this.send("auto_serve", { student: sid, shop }, () => { this.removeFromQueue(shop, sid); this.exitShop(a, shop); });
      }
    } else if (!v.current_order && a.mode === "queue" && this.playerIn(shop) && !this.game.ui.dialogOpen && this.p09For !== sid) {
      this.openOrder(shop, sid);
    }
  }

  // ------------------------------------------------------------ zones/triggers
  updateZones() {
    const g = this.game, p = g.player.pos, v = this.v;
    if (!v || g.ui.dialogOpen) return;
    const zone = (name, inside, fn) => {
      if (inside && !this.zoneFlags[name]) { this.zoneFlags[name] = true; fn(); }
      if (!inside) this.zoneFlags[name] = false;
    };
    const inWholesale = g.world.buildingAt(p) === "wholesale";
    zone("wholesale_entry", !inWholesale && p.x > 23.8 && p.x < 27.8 && Math.abs(p.z) < 2.8 && !this.wholesaleAllowed, () => this.askWholesale());
    zone("rival_entry", p.x > -3.2 && p.x < 3.2 && p.z > -15.8 && p.z < -11.5 && v.shops.rival.owner === "bot", () => this.openCompetitor());
    zone("cafe_bag", g.world.buildingAt(p) === "cafe" && this.bagHasItemsFor("cafe"), () => this.openStock("cafe"));
    zone("rival_bag", g.world.buildingAt(p) === "rival" && v.shops.rival.owner === "player" && this.bagHasItemsFor("rival"), () => this.openStock("rival"));
    // Leaving the wholesaler
    if (this.wholesaleAllowed && v.in_wholesaler && !inWholesale && p.x < 27.5) {
      this.send("leave_wholesaler", {}, (r) => { if (r.ok) this.wholesaleAllowed = false; });
      this.wholesaleAllowed = false;
      this.zoneFlags.wholesale_entry = true; // no "enter?" dialog right after leaving
    }
    zone("gate_hint", inWholesale && p.x < 29.3 && Math.abs(p.z) < 2 && Object.keys(v.cart).length > 0,
      () => g.ui.toast("Du hast noch unbezahlte Ware im Warenkorb - erst zur Kasse!", true));
    // Leaving the café with an order in progress pauses it (T12)
    const order = v.current_order;
    zone("order_left", !!order && !this.playerIn(order.shop), () => g.ui.toast("Bestellung pausiert - du hast das Café verlassen"));
  }

  updateGate() {
    const g = this.game, gate = g.world.gates.wholesale;
    const inside = g.world.buildingAt(g.player.pos) === "wholesale";
    gate.active = inside ? Object.keys(this.v?.cart || {}).length > 0 : !this.wholesaleAllowed;
  }
}
