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
    this.wasInWholesale = false;
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
  itemLine(i, q) { const it = this.cfg.wholesale_items[i]; return `${it.icon} ${q}x ${esc(it.name)} <span class="sub">(${esc(it.unit)})</span>`; }

  objectiveText() {
    if (!this.v) return "";
    if (this.v.day_state === "SHOP_OPEN") {
      if (this.game.isManual("cafe") && !this.playerIn("cafe")) return "Go back to your café - customers are waiting at the counter.";
      if (this.v.current_order) return "Prepare the order at the stations, then hand it over.";
      if (!this.game.isManual("cafe")) return "Your staff serve the customers. Use the time for upgrades or growth.";
    }
    if (this.v.day_state === "WHOLESALE_SHOPPING" && !this.v.in_wholesaler) return "Walk into the wholesaler.";
    if (this.canSkipToOpening()) return "Set your prices at the counter, then press ⏩ Start the day (top right).";
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
      case "SHOP_OPEN": return this.game.isManual("cafe") && !this.playerIn("cafe") ? { x: -36.4, z: 0 } : null;
      case "CLOSING": {
        const it = this.game.world.interactables.find((i) => i.cleaning && !v.cleaning[i.cleaning]);
        return it ? it.pos : null;
      }
      default: return null;
    }
  }

  registerLabel() {
    if (!this.v) return "Register";
    return !this.v.open && !this.v.closed ? "Set prices" : "Register";
  }
  useRegister(shop) {
    if (!this.v.open && !this.v.closed) return this.openPrices(shop);
    this.game.ui.toast(this.v.open ? "Customers pay when you hand over their order." : "The café is closed.");
  }
  counterLabel(shop) {
    if (!this.v || !this.game.isManual(shop) || !this.playerIn(shop)) return null;
    const order = this.v.current_order;
    if (order && order.shop === shop) return "Hand over the order";
    const front = this.queues[shop][0] && this.agents.get(this.queues[shop][0]);
    if (front && front.atCounter && !order) return "Take the order";
    return null;
  }
  useCounterFront(shop) {
    const order = this.v.current_order;
    if (order && order.shop === shop) return this.openHandover(shop);
    const sid = this.queues[shop][0];
    if (sid) this.openOrder(shop, sid);
  }

  // ------------------------------------------------------------- P00 title
  showTitle(hasSave, info) {
    const ui = this.game.ui;
    const help = "<b>W A S D</b> walk, <b>Shift</b> run, <b>click the game</b> to look around with the mouse (Esc frees it), " +
      "<b>E</b> or click to use things, <b>Enter</b> confirm, <b>Esc</b> cancel, <b>Tab</b> lists, <b>P</b> pause.";
    ui.showDialog({
      id: "P00", noEsc: true,
      custom: (box) => {
        box.appendChild(el("div", "title-logo", "☕ Nova Campus<br>Tycoon"));
        box.appendChild(el("div", "title-sub", "Run your café, beat the competition and take over the whole campus."));
        if (hasSave && info) box.appendChild(el("div", "save-info", `💾 Saved game: day ${info.day} · ${euro(info.money)}`));
        box.appendChild(el("div", "dlg-text", help));
      },
      // With a saved game, Enter continues it; a new game asks first (it replaces the save).
      extra: hasSave ? [{ label: "New game", action: () => this.confirmRestart() }] : [],
      primary: hasSave
        ? { label: "Continue", action: () => this.game.startSession("continue_game") }
        : { label: "New game", action: () => this.game.startSession("new_game") },
    });
  }
  confirmRestart() {
    const ui = this.game.ui;
    const back = this.v ? () => this.openPause() : () => this.showTitle(this.game.titleInfo.hasSave, this.game.titleInfo.info);
    ui.queue = []; if (ui.current) { ui.current.busy = false; ui.current.onClose = null; ui.closeDialog(); }
    ui.showDialog({
      id: "P21", icon: "🔄", title: "Start a new game?", urgent: true, noEsc: true,
      text: "Your saved game will be replaced. Day, money, reputation, upgrades and cafés start from zero again.",
      secondary: { label: "Back", action: () => setTimeout(back, 0) },
      primary: { label: "Yes, start over", action: () => { this.game.clock.paused = false; this.game.startSession("new_game"); } },
    });
  }

  // ------------------------------------------------------------- P01 morning
  openMorning() {
    const v = this.v, y = v.yesterday;
    const stockOf = (s) => Object.entries(v.shops[s].stock).map(([i, e]) => {
      const days = e.batches.map((b) => b.days_left).filter((d) => d !== null);
      const shelf = days.length ? ` (${Math.min(...days)} day${Math.min(...days) === 1 ? "" : "s"} left)` : "";
      return `${this.cfg.wholesale_items[i].icon} ${e.units} ${this.cfg.wholesale_items[i].base_name}${shelf}`;
    });
    const sold = y ? Object.entries(y.sold).map(([p, n]) => `${this.cfg.products[p].icon} ${n}`).join(" &nbsp; ") || "nothing" : "no sales yet";
    const rows = [{ label: "Cash", value: euro(v.money) }];
    for (const s of Object.keys(v.shops)) {
      if (v.shops[s].owner !== "player") continue;
      rows.push({ label: `Stock ${esc(this.shopName(s))}`, value: stockOf(s).join("<br>") || "empty" });
    }
    rows.push({ label: "Sold yesterday", value: sold });
    if (v.restock && v.restock.cost) rows.push({ label: `${esc(this.shopName("rival"))} restocked`, value: euro(-v.restock.cost) });
    this.game.ui.showDialog({
      id: "P01", icon: "🌅", title: `Good morning, day ${v.day}`, unique: true,
      text: v.day === 1
        ? "Welcome to campus! You run the café on the left. Plan your day at the <b>planning board</b>, buy supplies at the <b>wholesaler</b> and open at 08:00. The minimap in the corner shows where everything is."
        : "A new day begins. What do you want to sell today?",
      rows,
      primary: { label: "Let's go" },
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
      // Display only; Python computes the binding shopping list when you confirm.
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
      id: "P02", icon: "📋", title: "Day planning",
      text: "How many portions do you want to sell today? Your shopping list is calculated from this.",
      body: (body) => {
        const draw = () => {
          body.innerHTML = "";
          for (const p of unique) {
            const line = el("div", "line");
            line.appendChild(el("div", "lbl", `<span class="ic">${this.cfg.products[p].icon}</span><div>${esc(this.cfg.products[p].name)}</div>`));
            const stp = el("div", "stepper");
            const step = p === "coffee" || p === "tea" ? 5 : 1;
            const minus = el("button", "", "−"), plus = el("button", "", "+"), val = el("span", "", String(plan[p]));
            minus.onclick = () => { plan[p] = Math.max(0, plan[p] - step); draw(); };
            plus.onclick = () => { plan[p] += step; draw(); };
            stp.append(minus, val, plus); line.appendChild(stp); body.appendChild(line);
          }
          const list = need();
          const cost = Object.entries(list).reduce((a, [i, q]) => a + q * items[i].price, 0);
          const rows = Object.entries(list).map(([i, q]) => `<div>${this.itemLine(i, q)}</div>`).join("") || "<div>Nothing needed - your stock is enough.</div>";
          body.appendChild(el("div", "note", `<b>Shopping list:</b>${rows}<b>Estimated cost: ${euro(cost)}</b>` +
            (cost > v.money ? `<div class="warn">More than your cash (${euro(v.money)})!</div>` : "")));
        };
        draw();
      },
      secondary: { label: "Cancel" },
      primary: { label: "Save shopping list", action: () => { this.send("confirm_plan", { plan }, this.ok()); } },
    });
  }

  // -------------------------------------------------------- P03 wholesaler
  askWholesale() {
    const v = this.v;
    const list = Object.entries(v.shopping_list).map(([i, q]) => this.itemLine(i, q)).join("<br>") || "No shopping list - you can still shop freely.";
    this.game.ui.showDialog({
      id: "P03", icon: "🏬", title: "Enter the wholesaler?", unique: true,
      text: "All your supplies are sold here. Your cart starts with your shopping list.",
      rows: [{ label: "Shopping list", value: list }],
      secondary: { label: "Later" },
      primary: { label: "Enter", action: () => {
        this.wholesaleAllowed = true; // open the door right away; Python confirms
        this.send("enter_wholesaler", {}, (r) => {
          if (!r.ok) { this.wholesaleAllowed = false; this.game.ui.toast(r.error, true); return; }
          this.game.ui.toast("Welcome! Walk to the stands, then pay at the checkout.");
        });
      } },
    });
  }

  // -------------------------------------------------------- P04 item
  openItem(item) {
    const spec = this.cfg.wholesale_items[item], ui = this.game.ui;
    if (!this.v.in_wholesaler) return ui.toast("You are not inside the wholesaler.", true);
    let qty = this.v.cart[item] ?? this.v.shopping_list[item] ?? 0;
    const others = () => this.v.cart_total - (this.v.cart[item] || 0) * spec.price;
    ui.showDialog({
      id: "P04", icon: spec.icon, title: `Item: ${spec.name}`, text: esc(spec.description),
      body: (body) => {
        const draw = () => {
          body.innerHTML = "";
          const shelf = spec.shelf_days === null ? "unlimited" : spec.shelf_days === 1 ? "1 day" : `${spec.shelf_days} days`;
          body.appendChild(el("table", "dlg-rows",
            `<tr><td>Price</td><td>${euro(spec.price)} / ${esc(spec.unit)}</td></tr>` +
            `<tr><td>Makes</td><td>${spec.base_units} ${esc(spec.base_name)}</td></tr>` +
            `<tr><td>Shelf life</td><td>${shelf}</td></tr>`));
          const line = el("div", "line");
          line.appendChild(el("div", "lbl", "<b>Quantity</b>"));
          const stp = el("div", "stepper");
          const minus = el("button", "", "−"), plus = el("button", "", "+"), val = el("span", "", String(qty));
          minus.onclick = () => { qty = Math.max(0, qty - 1); draw(); };
          plus.onclick = () => { qty += 1; draw(); };
          stp.append(minus, val, plus); line.appendChild(stp); body.appendChild(line);
          const total = others() + qty * spec.price;
          const bad = total > this.v.money;
          body.appendChild(el("table", "dlg-rows",
            `<tr><td>Subtotal</td><td>${euro(qty * spec.price)}</td></tr>` +
            `<tr class="total"><td>Cart total</td><td class="${bad ? "bad" : ""}">${euro(total)}</td></tr>` +
            (bad ? `<tr><td colspan="2" class="bad">Not enough money (cash: ${euro(this.v.money)})</td></tr>` : "")));
        };
        draw();
      },
      secondary: { label: "Cancel" },
      primary: { label: "Add to cart", action: () => { this.send("set_cart_item", { item, qty }, this.ok()); } },
    });
  }

  // -------------------------------------------------------- P05 checkout
  openCheckout() {
    const v = this.v, items = this.cfg.wholesale_items;
    if (!v.in_wholesaler) return;
    if (!Object.keys(v.cart).length) return this.game.ui.toast("Your cart is empty - visit the stands first.");
    const rows = Object.entries(v.cart).map(([i, q]) => ({ label: `${items[i].icon} ${q}x ${esc(items[i].name)} at ${euro(items[i].price)}`, value: euro(q * items[i].price) }));
    const after = v.money - v.cart_total;
    rows.push({ label: "Total", value: euro(v.cart_total), cls: "total" });
    rows.push({ label: "Cash before", value: euro(v.money) });
    rows.push({ label: "Cash after", value: euro(after), vcls: after < 0 ? "bad" : "good" });
    this.game.ui.showDialog({
      id: "P05", icon: "🧾", title: "Wholesaler checkout",
      text: "The cashier smiles: <i>“Bom dia! Found everything?”</i>" + (after < 0 ? `<div class="warn">Not enough money - take something out of your cart.</div>` : ""),
      rows,
      secondary: { label: "Back to shopping" },
      primary: { label: "Pay", disabled: after < 0, action: () => { this.send("pay", {}, this.ok(() => this.game.ui.toast("Now carry the goods back to your café."))); } },
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
      id: "P06", icon: "📦", title: "Stock the goods", unique: true,
      text: "Your bag is full. Put everything into the storage.",
      rows,
      primary: { label: "Stock", action: () => { this.send("stock_goods", { shop }, this.ok()); } },
    });
  }

  // -------------------------------------------------------- P07 prices, P08 open
  openPrices(shop) {
    const v = this.v, ui = this.game.ui;
    const prices = Object.assign({}, v.shops[shop].prices);
    const cost = (p) => Object.entries(this.cfg.products[p].uses).reduce((a, [i, q]) =>
      a + q * this.cfg.wholesale_items[i].price / this.cfg.wholesale_items[i].base_units, 0);
    ui.showDialog({
      id: "P07", icon: "🏷️", title: `Set prices - ${this.shopName(shop)}`,
      text: "Higher prices mean more margin, but fewer students think the offer is worth it.",
      body: (body) => {
        const draw = () => {
          body.innerHTML = "";
          for (const p of Object.keys(prices)) {
            const line = el("div", "line");
            const margin = prices[p] - cost(p);
            line.appendChild(el("div", "lbl", `<span class="ic">${this.cfg.products[p].icon}</span><div>${esc(this.cfg.products[p].name)}<div class="sub">Cost ${euro(cost(p))} · margin <span style="color:${margin >= 0 ? "#23784a" : "#d9534f"}">${euro(margin)}</span></div></div>`));
            const stp = el("div", "stepper");
            const minus = el("button", "", "−"), plus = el("button", "", "+"), val = el("span", "", euro(prices[p]));
            minus.onclick = () => { prices[p] = Math.max(10, prices[p] - 10); draw(); };
            plus.onclick = () => { prices[p] = Math.min(this.cfg.max_price, prices[p] + 10); draw(); };
            stp.append(minus, val, plus); line.appendChild(stp); body.appendChild(line);
          }
          if (v.shops.rival.owner === "bot") {
            const rp = v.shops.rival.prices;
            body.appendChild(el("div", "note", "Competitor: " + Object.entries(rp).map(([p, c]) => `${this.cfg.products[p].icon} ${euro(c)}`).join(" · ")));
          }
        };
        draw();
      },
      secondary: { label: "Cancel" },
      primary: { label: "Save prices", action: () => {
        this.send("set_prices", { shop, prices }, this.ok(() => { if (!this.v.open && this.game.clock.t >= 7) this.askOpen(); }));
      } },
    });
  }

  askOpen() {
    const v = this.v;
    if (v.open || v.closed) return;
    if (this.game.clock.t < 7 && this.canSkipToOpening()) {
      return this.game.ui.showDialog({
        id: "P08", icon: "⏩", title: "Start the day now?", unique: true,
        text: "Everything is ready. Jump straight to 08:00 and open the café, or wait and look around first. The ⏩ button at the top right does the same later.",
        secondary: { label: "Not yet" },
        primary: { label: "⏩ Start the day", action: () => this.skipToOpening() },
      });
    }
    const waiting = this.queues.cafe.length;
    this.game.ui.showDialog({
      id: "P08", icon: "🚪", title: "Open the café?", unique: true,
      text: this.game.clock.t < 7 ? "You can open from 07:00. At 08:00 the café opens automatically."
        : `It is ${fmtTime(this.game.clock.t)}. ${waiting ? `${waiting} student${waiting === 1 ? " is" : "s are"} already waiting at the door.` : "Nobody is waiting yet."}`,
      secondary: { label: "Not yet" },
      primary: { label: "Open", disabled: this.game.clock.t < 7, action: () => { this.send("open_shop", {}, this.ok(() => this.onOpened())); } },
    });
  }

  // -------------------------------------------------------- P09 new order
  openOrder(shop, sid) {
    const a = this.agents.get(sid);
    if (!a || !a.atCounter || a.mode !== "queue" || this.v.current_order) return;
    this.p09For = sid;
    const items = a.order || [];
    const chips = items.map((p) => `<span class="chip">${this.cfg.products[p].icon} ${esc(this.cfg.products[p].name)}</span>`).join("") +
      (a.soldOut || []).map((p) => `<span class="chip off">${this.cfg.products[p].icon} ${esc(this.cfg.products[p].name)}<b>SOLD OUT</b></span>`).join("");
    const total = items.reduce((s, p) => s + this.v.shops[shop].prices[p], 0);
    const dlg = {
      id: "P09", icon: "🙋", title: `New order - ${a.info.name}`, unique: true,
      valid: () => this.queues[shop][0] === sid && !this.v.current_order && a.mode === "queue",
      body: (body) => {
        body.appendChild(el("div", "chips", chips));
        if ((a.soldOut || []).length) body.appendChild(el("div", "note",
          "Red = the customer wanted it, but your stock is empty (0 left). Buy more at the wholesaler tomorrow."));
        const pb = el("div", "progress"); const bar = el("div"); pb.appendChild(bar); body.appendChild(pb);
        const f = clamp(a.patience / a.patienceMax, 0, 1);
        bar.style.width = `${f * 100}%`;
        bar.style.background = f > 0.5 ? "#2f9e5b" : f > 0.25 ? "#f2c94c" : "#d9534f";
        body.appendChild(el("div", "note", `Patience · order value ${euro(total)}`));
      },
      // Closing without a decision lets the dialog come back; after a decision we wait for Python.
      onClose: () => { if (!dlg.decided) this.p09For = null; },
      secondary: { label: "Reject", action: () => {
        dlg.decided = true;
        a.mode = "rejected";
        this.send("reject", { shop, student: sid }, (r) => {
          this.p09For = null;
          if (r.ok) this.repToast(r.result.rep_delta, "turned away");
          this.removeFromQueue(shop, sid);
          a.emote = { icon: "😕", until: performance.now() + 3000 };
          this.leaveShop(a, shop, r.ok ? r.result : { action: "wander" });
        });
      } },
      primary: { label: "Accept", action: () => {
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
    if (!order || order.shop !== shop) return this.game.ui.toast("Take an order at the counter first.");
    if (!v.shops[shop].can_make[product]) return this.game.ui.toast(`${spec.name} is sold out.`, true);
    const ids = { coffee: "P10", orange_juice: "P11", pastel_de_nata: "P12", tea: "P10", croissant: "P12" };
    const verbs = { coffee: "Brew", orange_juice: "Squeeze", pastel_de_nata: "Take one", tea: "Brew", croissant: "Take one" };
    const titles = { coffee: "Make a coffee", orange_juice: "Squeeze orange juice", pastel_de_nata: "Take a pastel de nata", tea: "Make a tea", croissant: "Take a croissant" };
    const steps = {
      coffee: "Put a cup under the spout, press the button - the espresso is running.",
      orange_juice: "Put three oranges in and squeeze.",
      pastel_de_nata: "Take a pastel de nata from the display case and put it on the tray.",
      tea: "Tea bag into the cup, hot water on top.",
      croissant: "Take a croissant from the display case.",
    };
    const needed = order.items.filter((p) => p === product).length - v.tray.filter((p) => p === product).length;
    let bar = null;
    const dlg = {
      id: ids[product], icon: spec.icon, title: titles[product],
      text: steps[product] + (needed <= 0 ? `<div class="warn">This is not (or no longer) part of the order!</div>` : ""),
      body: (body) => {
        const pb = el("div", "progress"); bar = el("div"); pb.appendChild(bar); body.appendChild(pb);
        body.appendChild(el("div", "note", `Takes ${spec.prep_minutes} game minute${spec.prep_minutes === 1 ? "" : "s"}`));
      },
      // Cancel also works while the product is being made: nothing is used up then.
      cancelWhileBusy: true,
      secondary: { label: "Cancel", action: () => {
        if (dlg.busy) { this.progress = null; dlg.busy = false; this.game.ui.toast(`${spec.name} cancelled - nothing used`); }
      } },
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
    }).join("") + tray.map((p) => `<span class="chip miss">+ ${this.cfg.products[p].icon} extra</span>`).join("");
    const a = this.agents.get(order.student);
    this.game.ui.showDialog({
      id: "P13", icon: "🤝", title: `Hand over the order - ${a ? a.info.name : ""}`,
      text: "Order against tray:",
      body: (body) => {
        body.appendChild(el("div", "chips", chips));
        if (v.tray.length) body.appendChild(el("div", "note", "Something wrong on the tray? Throw it away and make the right product."));
      },
      secondary: { label: "Back" },
      extra: [
        ...(v.tray.length ? [{ label: "🗑 Throw away tray", action: () => { this.game.ui.closeDialog(); this.discardTray(); } }] : []),
        { label: "✖ Cancel order", action: () => { this.game.ui.closeDialog(); this.confirmCancelOrder(); } },
      ],
      primary: { label: "Hand over", disabled: !v.tray.length, action: () => {
        this.send("handover", { shop, student: order.student, player_inside: this.playerIn(shop) }, (r) => {
          if (!r.ok) return this.game.ui.toast(r.error, true);
          this.game.ui.toast(r.result.toast, !r.result.correct);
          this.repToast(r.result.rep_delta);
          this.removeFromQueue(shop, order.student);
          if (a) { a.emote = { icon: r.result.correct ? "😊" : "😠", until: performance.now() + 3500 }; this.exitShop(a, shop); }
        });
      } },
    });
  }

  discardTray() {
    const order = this.v.current_order;
    if (!order || !this.v.tray.length) return;
    this.send("discard_tray", { shop: order.shop, player_inside: this.playerIn(order.shop) }, this.ok());
  }
  confirmCancelOrder() {
    const order = this.v.current_order;
    if (!order) return;
    const a = this.agents.get(order.student);
    this.game.ui.showDialog({
      id: "P22", icon: "✖", title: "Cancel this order?", unique: true,
      text: `${a ? esc(a.info.name) : "The customer"} leaves without buying. What is on the tray is lost and your reputation drops by ${-this.cfg.reputation.order_cancelled}.`,
      secondary: { label: "Keep serving" },
      primary: { label: "Cancel order", action: () => this.cancelOrder() },
    });
  }
  cancelOrder() {
    const order = this.v.current_order;
    if (!order) return;
    const shop = order.shop, a = this.agents.get(order.student);
    this.send("cancel_order", { shop, player_inside: this.playerIn(shop) }, (r) => {
      if (!r.ok) return this.game.ui.toast(r.error, true);
      this.game.ui.toast(r.result.toast, true);
      this.repToast(r.result.rep_delta);
      this.removeFromQueue(shop, order.student);
      if (a) { a.emote = { icon: "😠", until: performance.now() + 3500 }; this.leaveShop(a, shop, r.result); }
    });
  }
  // Reputation changes are always shown, so you see why it goes up or down.
  repToast(delta, why = "") {
    if (!delta) return;
    const d = Math.round(delta * 10) / 10;
    this.game.ui.toast(`Reputation ${d > 0 ? "+" : ""}${d}${why ? ` (${why})` : ""}`, d < 0);
  }

  // -------------------------------------------------------- start the day early
  canSkipToOpening() {
    const v = this.v;
    return !!v && v.status === "running" && v.day_state === "SET_PRICES" && !v.open && !v.closed &&
      this.game.clock.t < this.cfg.time.open && !Object.keys(v.bag).length;
  }
  skipToOpening() {
    if (!this.canSkipToOpening()) return;
    this.game.clock.t = this.cfg.time.open; // the 08:00 tick opens the café
    this.game.clock.paused = false;
    this.game.ui.toast("Jumped to 08:00 - your café opens");
    this.game.ui.updateHud();
  }

  // -------------------------------------------------------- P14/P15 closing
  openClosing() {
    const spots = Object.values(this.cfg.cleaning_spots).map((s) => `• ${s.name}`).join("<br>");
    this.game.ui.showDialog({
      id: "P14", icon: "🌙", title: "Closing time", unique: true, urgent: true,
      text: `It is 20:00. The sign says “Closed” and waiting customers go home. The game is back at 1x speed.<br><br>Clean up now:<br>${spots}`,
      primary: { label: "Clean up" },
    });
  }
  openCleaning(spot) {
    const spec = this.cfg.cleaning_spots[spot];
    let bar = null;
    const icons = { counter: "🧽", coffee_machine: "☕", tables: "🍽️", floor: "🧹" };
    const dlg = {
      id: "P15", icon: icons[spot], title: `Clean up: ${spec.name}`,
      body: (body) => { const pb = el("div", "progress"); bar = el("div"); pb.appendChild(bar); body.appendChild(pb); },
      primary: { label: "Start", action: () => {
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
  // Four tabs: today's result, stock movements, the competitor, the last days.
  openSummary() {
    const s = this.v.summary;
    if (!s) return;
    let tab = "today";
    const dlg = {
      id: "P16", icon: "📊", title: `Daily summary - day ${s.day}`, unique: true, noEsc: true, wide: true,
      body: (body) => {
        const tabs = el("div", "tabs");
        const content = el("div", "dlg-scroll");
        const names = { today: "Today", stock: "Stock", competitor: "Competitor", history: "Last days" };
        const draw = () => {
          tabs.querySelectorAll("button").forEach((b) => b.classList.toggle("active", b.dataset.tab === tab));
          content.innerHTML = "";
          ({ today: () => this.summaryToday(content, s), stock: () => this.summaryStock(content, s),
            competitor: () => this.summaryCompetitor(content, s), history: () => this.summaryHistory(content) })[tab]();
        };
        for (const [key, label] of Object.entries(names)) {
          const b = el("button", "", label); b.dataset.tab = key;
          b.onclick = () => { tab = key; draw(); };
          tabs.appendChild(b);
        }
        body.append(tabs, content);
        draw();
      },
      primary: { label: this.v.status === "running" ? "Next day" : "Continue", action: () => {
        if (this.v.status !== "running") return this.openEnd();
        this.game.fade(() => this.send("next_day", {}, this.ok()));
      } },
    };
    this.game.ui.showDialog(dlg);
  }
  table(head, rows) {
    return `<table class="sum-table"><tr>${head.map((h) => `<th>${h}</th>`).join("")}</tr>` +
      rows.map((r) => `<tr>${r.map((c) => `<td>${c}</td>`).join("")}</tr>`).join("") + "</table>";
  }
  signed(n, fmt = (x) => x) { return n > 0 ? `<span class="pos">+${fmt(n)}</span>` : n < 0 ? `<span class="neg">${fmt(n)}</span>` : "0"; }
  summaryToday(box, s) {
    const products = this.cfg.products;
    const money = [
      ["Sales", euro(s.revenue)],
      ["Tips", euro(s.tips || 0)],
      ["Purchases", euro(-s.purchase_cost)],
      ["Upgrades & staff", euro(-s.spending)],
      ["<b>Profit</b>", `<b>${this.signed(s.profit, euro)}</b>`],
      ["Spoiled goods (part of purchases)", euro(s.spoiled_value)],
      ["Cash tonight", euro(s.money)],
    ];
    const people = [
      ["Customers served", s.served],
      ["Lost (left unhappy)", s.lost],
      ["... of them: sold out", s.sold_out || 0],
      ["Wrong orders", s.wrong],
      ["Thrown away", s.wasted || 0],
      ["Reputation", `${s.reputation} / 100`],
      ["Market share", `${Math.round(s.market_share * 100)} %`],
    ];
    const grid = el("div", "sum-grid");
    grid.appendChild(el("div", "", `<div class="sum-h">💶 Money</div>` + this.table(["", ""], money)));
    grid.appendChild(el("div", "", `<div class="sum-h">🙋 Customers</div>` + this.table(["", ""], people)));
    box.appendChild(grid);
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
    box.appendChild(el("div", "sum-h", "Sold vs. plan <span class=\"sub\">(grey = plan, green = sold)</span>"));
    box.appendChild(bars);
  }
  summaryStock(box, s) {
    const items = this.cfg.wholesale_items;
    const report = s.stock || {};
    if (!Object.keys(report).length) { box.appendChild(el("div", "note", "No stock data for this day.")); return; }
    for (const [shop, rows] of Object.entries(report)) {
      const lines = Object.entries(rows).map(([i, r]) => [
        `${items[i].icon} ${esc(items[i].name)}`, r.open, r.in ? `+${r.in}` : "0", r.used ? `-${r.used}` : "0",
        r.spoiled ? `<span class="neg">-${r.spoiled}</span>` : "0", `<b>${r.close}</b>`, this.signed(r.change),
      ]);
      box.appendChild(el("div", "sum-h", `📦 ${esc(this.shopName(shop))}`));
      box.appendChild(el("div", "", this.table(["Item", "Start", "In", "Used", "Spoiled", "End", "Change"], lines)));
    }
    box.appendChild(el("div", "note", "Units: portions of coffee, single oranges, pieces of pastry, tea bags. Spoiled goods are thrown away at night."));
  }
  summaryCompetitor(box, s) {
    const products = this.cfg.products;
    const c = s.competitor;
    if (!c) {
      box.appendChild(el("div", "note", `You own ${esc(this.shopName("rival"))}. Its numbers are part of your results now (see Today and Stock).`));
      return;
    }
    const share = (rev) => (s.revenue + c.revenue ? Math.round(rev / (s.revenue + c.revenue) * 100) : 0) + " %";
    box.appendChild(el("div", "sum-h", `🏪 You vs. ${esc(c.name)}`));
    box.appendChild(el("div", "", this.table(["", "You", esc(c.name)], [
      ["Customers served", s.served, c.served],
      ["Customers lost", s.lost, c.lost],
      ["Sales", euro(s.revenue), euro(c.revenue)],
      ["Market share", share(s.revenue), share(c.revenue)],
    ])));
    const prices = s.prices || {};
    const all = [...new Set([...Object.keys(prices.cafe || {}), ...Object.keys(c.prices)])];
    box.appendChild(el("div", "sum-h", "🏷️ Prices today"));
    box.appendChild(el("div", "", this.table(["Product", "You", esc(c.name)], all.map((p) => [
      `${products[p].icon} ${esc(products[p].name)}`,
      prices.cafe && prices.cafe[p] != null ? euro(prices.cafe[p]) : "-",
      c.prices[p] != null ? euro(c.prices[p]) : "-",
    ]))));
    const sold = Object.entries(c.sold).map(([p, n]) => `${products[p].icon} ${n}`).join(" &nbsp; ") || "nothing";
    box.appendChild(el("div", "note", `They sold: ${sold}`));
  }
  summaryHistory(box) {
    const days = this.v.history || [];
    if (!days.length) { box.appendChild(el("div", "note", "No finished days yet.")); return; }
    box.appendChild(el("div", "sum-h", "📈 The last days"));
    box.appendChild(el("div", "", this.table(
      ["Day", "Sales", "Profit", "Served", "Lost", "Rep.", "Cash", "Competitor sales"],
      days.slice().reverse().map((d) => [
        d.day, euro(d.revenue + (d.tips || 0)), this.signed(d.profit, euro), d.served, d.lost, d.reputation, euro(d.money),
        d.competitor ? `${euro(d.competitor.revenue)} (${d.competitor.served})` : "yours",
      ]),
    )));
  }

  // -------------------------------------------------------- P17 competitor
  openCompetitor() {
    const v = this.v;
    const prices = Object.entries(v.shops.rival.prices).map(([p, c]) => ({ label: `${this.cfg.products[p].icon} ${esc(this.cfg.products[p].name)}`, value: euro(c) }));
    const can = v.can_buy_competitor;
    this.game.ui.showDialog({
      id: "P17", icon: "🏪", title: `Competitor - ${this.shopName("rival")}`, unique: true,
      text: can ? `The owner is willing to sell for <b>${euro(this.cfg.acquisition_cost)}</b>. The barista stays, keeps selling automatically and restocks every morning.`
        : `The competitor has fixed prices and a good reputation (factor ${v.shops.rival.factor.toFixed(2)}). ` +
          `Once a manager works in your café, you can buy it for ${euro(this.cfg.acquisition_cost)}.`,
      rows: prices,
      secondary: can ? { label: "Later" } : null,
      primary: can ? { label: "Buy the café", disabled: v.money < this.cfg.acquisition_cost,
        action: () => { this.send("buy_competitor", {}, this.ok(() => this.checkEnd())); } } : { label: "OK" },
    });
  }

  // -------------------------------------------------------- P18 upgrades
  openUpgrades() {
    const ui = this.game.ui;
    const dlg = {
      id: "P18", icon: "🛠️", title: "Upgrades & staff",
      text: "Upgrades make your café more attractive (utility factor). A manager serves customers on their own.",
      body: (body) => {
        const v = this.v;
        for (const shop of Object.keys(v.shops)) {
          if (v.shops[shop].owner !== "player") continue;
          const staff = shop === "rival" ? " · barista sells automatically" : "";
          body.appendChild(el("div", "note", `<b>${esc(this.shopName(shop))}</b> · factor ${v.shops[shop].factor.toFixed(2)}${staff}`));
          for (const [u, spec] of Object.entries(this.cfg.upgrades)) {
            const line = el("div", "line");
            line.appendChild(el("div", "lbl", `<span class="ic">${spec.icon}</span><div>${esc(spec.name)}<div class="sub">+${spec.factor_bonus.toFixed(2)} factor · ${euro(spec.cost)}</div></div>`));
            if (v.shops[shop].upgrades.includes(u)) line.appendChild(el("span", "chip ok", "✔ bought"));
            else {
              const b = el("button", "btn primary", "Buy");
              b.disabled = v.money < spec.cost;
              b.onclick = () => this.send("buy_upgrade", { shop, upgrade: u }, this.ok(() => ui.refreshDialog()));
              line.appendChild(b);
            }
            body.appendChild(line);
          }
          const line = el("div", "line");
          const what = shop === "rival" ? "takes over the second café - completes your monopoly" : "serves automatically";
          line.appendChild(el("div", "lbl", `<span class="ic">🧑‍🍳</span><div>Manager<div class="sub">${what} · ${euro(this.cfg.manager_cost)}</div></div>`));
          if (v.shops[shop].manager) line.appendChild(el("span", "chip ok", "✔ hired"));
          else {
            const b = el("button", "btn primary", "Hire");
            b.disabled = v.money < this.cfg.manager_cost;
            b.onclick = () => this.send("hire_manager", { shop }, this.ok(() => { ui.refreshDialog(); this.checkEnd(); }));
            line.appendChild(b);
          }
          body.appendChild(line);
        }
      },
      primary: { label: "Close" },
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
      id: "P19", icon: win ? "🏆" : "💸", title: win ? "Monopoly reached!" : "Bankrupt!", unique: true, noEsc: true, urgent: true,
      text: win ? `Both cafés are yours and run with managers. You took over the campus in <b>${v.day} days</b>.`
        : "Your cash dropped to €0.00 or below at the end of the day.",
      rows: [{ label: "Days played", value: String(v.day) }, { label: "Total profit", value: euro(v.total_profit) }],
      primary: { label: "New game", action: () => this.game.startSession("new_game") },
    });
  }
  openPause() {
    const g = this.game;
    if (!g.view || g.ui.current?.id === "P20") return;
    if (g.ui.dialogOpen) { g.clock.paused = !g.clock.paused; return; }
    g.clock.paused = true;
    g.ui.showDialog({
      id: "P20", icon: "⏸️", title: "Paused", urgent: true,
      text: "Everything stands still: clock, students and progress bars. Your game is saved automatically after every action, so you can close the browser and continue later.",
      onClose: () => { g.clock.paused = false; },
      extra: [
        { label: "🔄 New game", cls: "secondary", action: () => this.confirmRestart() },
        { label: "Save & quit", cls: "secondary", action: () => { g.ui.closeDialog(); g.startSession("quit"); } },
      ],
      primary: { label: "Resume" },
    });
  }

  // ------------------------------------------------------------------ events
  onOpened() { for (const s of ["cafe", "rival"]) this.repositionQueue(s); }

  sendTicks() {
    const t = this.game.clock.t;
    for (const mark of TICKS) {
      if (t + 1e-6 >= mark && !this.sentTicks.has(mark)) {
        this.sentTicks.add(mark);
        this.send("tick", { t: Math.max(t, mark) }, (r) => {
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
    this.wholesaleAllowed = !!view.in_wholesaler;
    this.wasInWholesale = false;
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
    // A good reputation makes customers of your cafés wait longer.
    const perk = this.v.shops[shop].owner === "player" && this.v.rep_perks ? this.v.rep_perks.patience : 1;
    a.patienceMax = a.info.traits.patience * perk;
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
      if (a.mode !== "served") a.mode = "queue";
      const pts = [];
      if (open && !a.inside) { pts.push(P[shop].doorOut, P[shop].doorIn); a.inside = true; }
      pts.push(spot);
      a.walkTo(pts, () => a.faceTo(shop === "cafe" ? { x: -40, z: spot.z } : { x: spot.x, z: -30 }));
    });
  }

  exitShop(a, shop) {
    a.slotKey = null; a.shop = null; a.atCounter = false; a.order = null; a.wanted = null;
    a.mode = "exiting";
    const pts = a.inside ? [P[shop].doorIn, P[shop].doorOut] : [];
    a.inside = false;
    if (!pts.length) return this.startWander(a);
    a.walkTo(pts, () => this.startWander(a));
  }

  leaveShop(a, shop, decision) {
    a.slotKey = null; a.atCounter = false; a.order = null;
    if (a.inside) {
      a.inside = false; a.mode = "exiting";
      a.walkTo([P[shop].doorIn, P[shop].doorOut], () => this.handleDecision(a, decision));
    } else this.handleDecision(a, decision);
  }

  updateStudents(dtReal, dtGameMin) {
    const t = this.game.clock.t;
    const speed = this.game.clock.running ? this.game.clock.speed : 0;
    for (const a of this.agents.values()) {
      // arrivals over the map edges
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
      // patience runs while queuing from opening time on, also when the player is away;
      // it is frozen while staff prepare the order
      if (a.mode === "queue" && a.shop && this.queues[a.shop].includes(a.id) && speed && this.v.open) {
        a.patience -= dtGameMin;
        if (a.patience <= 0 && !a.expiring) this.patienceExpired(a);
      } else if (a.mode === "served" && a.shop && !this.v.shops[a.shop].auto && speed && this.v.open) {
        a.patience -= dtGameMin;
        if (a.patience <= 0 && !a.expiring) this.patienceExpired(a);
      }
      a.update(dtReal * speed);
    }
    for (const shop of ["cafe", "rival"]) this.updateCounter(shop, dtGameMin);
  }

  patienceExpired(a) {
    a.expiring = true;
    const shop = a.shop;
    this.send("patience_expired", { student: a.id, shop }, (r) => {
      a.expiring = false;
      const ui = this.game.ui;
      if (r.ok && r.result.toast && this.v.shops[shop].owner === "player") {
        ui.toast(r.result.toast, true);
        this.repToast(r.result.rep_delta, "waited too long");
      }
      if (this.p09For === a.id && ui.current?.id === "P09") ui.closeDialog();
      if (["P10", "P11", "P12", "P13"].includes(ui.current?.id) && !this.v.current_order) {
        this.progress = null; ui.current.busy = false; ui.closeDialog();
      }
      this.removeFromQueue(shop, a.id);
      a.emote = { icon: "😞", until: performance.now() + 3500 };
      this.leaveShop(a, shop, r.ok ? r.result : null);
    });
  }

  updateCounter(shop, dtGameMin) {
    const v = this.v;
    if (!v.open || this.game.clock.t >= this.cfg.time.close) return;
    const sid = this.queues[shop][0];
    const a = sid && this.agents.get(sid);
    if (!a || a.path.length || !a.inside || a.expiring) return;
    if (v.shops[shop].auto) {
      // Staff (barista, bot or manager) prepare the order and the student pays at once.
      if (!this.auto[shop] || this.auto[shop].sid !== sid) {
        if (a.mode !== "queue") return;
        const items = a.wanted || [];
        const minutes = Math.max(1, items.reduce((s, p) => s + this.cfg.products[p].prep_minutes, 0));
        this.auto[shop] = { sid, remain: minutes, sent: false };
        a.mode = "served";
        a.order = items;
      }
      const job = this.auto[shop];
      if (this.game.clock.running) job.remain -= dtGameMin;
      if (job.remain <= 0 && !job.sent) {
        job.sent = true;
        this.send("auto_serve", { student: sid, shop }, (r) => {
          this.removeFromQueue(shop, sid);
          const got = r.ok ? r.result.items : [];
          a.emote = { icon: got.length ? "😊" : "😞", until: performance.now() + 3500 };
          if (got.length && v.shops[shop].owner === "player") {
            this.game.ui.toast(`${this.shopName(shop)}: +${euro(r.result.amount)}` + (r.result.tip ? ` (+${euro(r.result.tip)} tip)` : ""));
          }
          if (r.ok && !got.length && v.shops[shop].owner === "player") {
            this.game.ui.toast(`${this.shopName(shop)}: sold out - the customer leaves`, true);
            this.repToast(r.result.rep_delta, "sold out");
          }
          this.exitShop(a, shop);
        });
      }
      return;
    }
    if (!a.atCounter && !a.pendingCounter && a.mode === "queue") {
      a.pendingCounter = true;
      this.send("at_counter", { student: sid, shop }, (r) => {
        a.pendingCounter = false;
        if (!r.ok) { this.removeFromQueue(shop, sid); this.exitShop(a, shop); return; }
        if (r.result.leaves) {
          this.removeFromQueue(shop, sid);
          a.emote = { icon: "😞", until: performance.now() + 3000 };
          if (v.shops[shop].owner === "player") {
            const names = (r.result.sold_out || []).map((p) => this.cfg.products[p].name).join(", ");
            this.game.ui.toast(`Sold out: ${names} - the customer leaves`, true);
            this.repToast(r.result.rep_delta, "sold out");
          }
          this.leaveShop(a, shop, r.result.decision);
          return;
        }
        a.order = r.result.items; a.soldOut = r.result.sold_out; a.atCounter = true;
      });
      return;
    }
    if (a.atCounter && !v.current_order && a.mode === "queue" && this.playerIn(shop) && !this.game.ui.dialogOpen && this.p09For !== sid) {
      this.openOrder(shop, sid);
    }
  }

  // ------------------------------------------------------------ zones/triggers
  updateZones() {
    const g = this.game, p = g.player.pos, v = this.v;
    if (!v) return;
    const inWholesale = g.world.buildingAt(p) === "wholesale";
    // Leaving the wholesaler: only after the player was really inside.
    if (inWholesale) this.wasInWholesale = true;
    if (this.wasInWholesale && !inWholesale && p.x < 27.6) {
      this.wasInWholesale = false;
      this.wholesaleAllowed = false;
      this.zoneFlags.wholesale_entry = true; // no "enter?" dialog right after leaving
      if (v.in_wholesaler) this.send("leave_wholesaler", {}, () => {});
    }
    if (g.ui.dialogOpen) return;
    const zone = (name, inside, fn) => {
      if (inside && !this.zoneFlags[name]) { this.zoneFlags[name] = true; fn(); }
      if (!inside) this.zoneFlags[name] = false;
    };
    zone("wholesale_entry", !inWholesale && p.x > 23.6 && p.x < 27.8 && Math.abs(p.z) < 3 && !this.wholesaleAllowed, () => this.askWholesale());
    zone("rival_entry", p.x > -3.2 && p.x < 3.2 && p.z > -15.8 && p.z < -11.5 && v.shops.rival.owner === "bot", () => this.openCompetitor());
    zone("cafe_bag", g.world.buildingAt(p) === "cafe" && this.bagHasItemsFor("cafe"), () => this.openStock("cafe"));
    zone("rival_bag", g.world.buildingAt(p) === "rival" && v.shops.rival.owner === "player" && this.bagHasItemsFor("rival"), () => this.openStock("rival"));
    zone("gate_hint", inWholesale && p.x < 29.3 && Math.abs(p.z) < 2 && Object.keys(v.cart).length > 0,
      () => g.ui.toast("You still have unpaid goods in your cart - pay at the checkout first!", true));
    const order = v.current_order;
    zone("order_left", !!order && !this.playerIn(order.shop), () => g.ui.toast("Order paused - you left the café"));
  }

  updateGate() {
    const g = this.game, gate = g.world.gates.wholesale;
    const inside = g.world.buildingAt(g.player.pos) === "wholesale";
    // Closed until you choose "Enter"; from inside it only blocks while unpaid goods are in the cart.
    gate.active = inside ? Object.keys(this.v?.cart || {}).length > 0 : !this.wholesaleAllowed;
  }
}
