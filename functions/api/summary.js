var REPO = "adamben04/tcg-bot";
var STATE_URL = "https://raw.githubusercontent.com/" + REPO + "/main/state.json";

var RET_MAP = {
  pokemon_center: "PC", target: "Target", best_buy: "BB",
  gamestop: "GS", walmart: "Walmart", costco: "Costco",
  sams_club: "Sam's", barnes_noble: "B&N", tcgplayer: "TCGP",
  amazon: "Amazon", box_lunch: "BoxLunch", hottopic: "HT",
  premium_bandai: "P-Bandai",
};

export async function onRequest(context) {
  try {
    var resp = await fetch(STATE_URL);
    if (resp.status !== 200) {
      return new Response(JSON.stringify({ error: "State fetch failed", status: resp.status }), {
        status: 502,
        headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" },
      });
    }
    var state = await resp.json();
    var prods = state.products || {};
    var entries = Object.keys(prods).map(function(k) { return prods[k]; });

    var byStatus = { in_stock: [], out_of_stock: [], unknown: [] };
    var byRetailer = {};
    var recentChanges = [];

    entries.forEach(function(p) {
      var status = p.last_status || "unknown";
      if (byStatus[status]) byStatus[status].push(p);

      var ret = p.retailer || "other";
      if (!byRetailer[ret]) byRetailer[ret] = { total: 0, inStock: 0, outOfStock: 0, items: [] };
      byRetailer[ret].total++;
      if (status === "in_stock") byRetailer[ret].inStock++;
      if (status === "out_of_stock") byRetailer[ret].outOfStock++;
      byRetailer[ret].items.push({
        name: p.name,
        url: p.url,
        status: status,
        price: p.history && p.history.length > 0 ? p.history[p.history.length - 1].price : null,
        lastChecked: p.last_checked,
      });

      var h = p.history || [];
      for (var i = Math.max(0, h.length - 2); i < h.length; i++) {
        var ev = h[i];
        if (ev && ev.status) {
          recentChanges.push({
            at: ev.at,
            status: ev.status,
            name: p.name,
            retailer: ret,
            price: ev.price,
          });
        }
      }
    });

    recentChanges.sort(function(a, b) { return (b.at || "").localeCompare(a.at || ""); });
    recentChanges = recentChanges.slice(0, 20);

    var summary = {
      updated: new Date().toISOString(),
      stats: {
        total: entries.length,
        inStock: byStatus.in_stock.length,
        outOfStock: byStatus.out_of_stock.length,
        unknown: byStatus.unknown.length,
        totalChecks: (state.stats && state.stats.total_checks) || 0,
        notificationsSent: (state.stats && state.stats.notifications_sent) || 0,
      },
      byRetailer: (function() {
        var out = {};
        Object.keys(byRetailer).forEach(function(r) {
          out[RET_MAP[r] || r] = {
            total: byRetailer[r].total,
            inStock: byRetailer[r].inStock,
            outOfStock: byRetailer[r].outOfStock,
          };
        });
        return out;
      })(),
      recentChanges: recentChanges,
    };

    return new Response(JSON.stringify(summary), {
      headers: {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
        "Cache-Control": "public, max-age=120",
      },
    });
  } catch (err) {
    return new Response(JSON.stringify({ error: err.message }), {
      status: 500,
      headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" },
    });
  }
}
