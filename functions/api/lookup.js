var TARGET_TCINS = [
  { tcin: "93954435", name: "Prismatic Evolutions ETB" },
  { tcin: "91619922", name: "Surging Sparks ETB" },
  { tcin: "91619929", name: "Surging Sparks Booster Bundle" },
  { tcin: "91619912", name: "Stellar Crown ETB" },
  { tcin: "91619942", name: "Stellar Crown Booster Bundle" },
  { tcin: "92698334", name: "Stellar Crown Booster Display" },
  { tcin: "91255505", name: "Temporal Forces ETB Walking Wake" },
  { tcin: "89952655", name: "Temporal Forces Booster Bundle" },
  { tcin: "91600215", name: "Shrouded Fable ETB" },
  { tcin: "92436710", name: "Shrouded Fable Booster Bundle" },
  { tcin: "89444929", name: "151 Binder Collection" },
  { tcin: "88897908", name: "Charizard ex Premium Collection" },
  { tcin: "89432659", name: "Paldean Fates ETB" },
  { tcin: "89432660", name: "Paldean Fates Booster Bundle" },
  { tcin: "1010548868", name: "One Piece OP-15 Kami's Island Box" },
  { tcin: "1008009274", name: "One Piece OP-14 Azure Sea Box" },
  { tcin: "1003688214", name: "One Piece OP-11 Fist of Divine Speed" },
  { tcin: "1002658635", name: "One Piece OP-10 Royal Blood" },
  { tcin: "1001561462", name: "One Piece PRB-01 The Best" },
  { tcin: "95267143", name: "Chaos Rising ETB" },
  { tcin: "95298172", name: "Chaos Rising Booster Bundle" },
  { tcin: "94300066", name: "Prismatic Evolutions Binder Collection" },
  { tcin: "88897899", name: "151 ETB" },
];

var BESTBUY_SKUS = [
  { sku: "6584756", name: "One Piece OP-09 Emperors in New World" },
  { sku: "6584757", name: "One Piece OP-10 Royal Blood" },
];

function targetCheck(tcin, apiKey) {
  var url = "https://redsky.target.com/redsky_aggregations/v1/web/pdp_client_v1?key=" + apiKey + "&tcin=" + tcin + "&visitor_id=tcg-bot-web";
  var headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Origin": "https://www.target.com",
    "Referer": "https://www.target.com/",
    "Accept-Language": "en-US,en;q=0.9",
  };
  return fetch(url, { headers: headers }).then(function(resp) {
    if (resp.status === 403) {
      return { tcin: tcin, online: null, error: "API key rejected (403)" };
    }
    if (resp.status !== 200) {
      return { tcin: tcin, online: null, error: "Target error " + resp.status };
    }
    return resp.json().then(function(data) {
      var shipStatus = null;
      var storeMethods = [];
      try {
        shipStatus = data.product.item.availability.availability_status;
        var opts = (data.product.fulfillment && data.product.fulfillment.options) || [];
        for (var i = 0; i < opts.length; i++) {
          var ft = opts[i].fulfillment_type || "";
          var st = opts[i].availability_status || "";
          var oos = opts[i].is_out_of_stock_in_area;
          if ((st === "IN_STOCK" || oos === false) && ft) {
            storeMethods.push(ft);
          }
        }
      } catch (_) {}
      var online = shipStatus === "IN_STOCK" || shipStatus === "LIMITED_AVAILABILITY";
      return { tcin: tcin, online: online, shipStatus: shipStatus, storeMethods: storeMethods };
    });
  }).catch(function(err) {
    return { tcin: tcin, online: null, error: err.message };
  });
}

function bestbuyCheck(sku, zip, apiKey) {
  var fields = "storeId,name,city,state,distance,lowStock";
  var url = "https://api.bestbuy.com/v1/products/" + sku + "/stores.json?postalCode=" + zip + "&apiKey=" + apiKey + "&show=" + fields;
  return fetch(url).then(function(resp) {
    if (resp.status !== 200) {
      return { sku: sku, error: "Best Buy error " + resp.status };
    }
    return resp.json().then(function(data) {
      var stores = (data.stores || []).map(function(s) {
        return {
          store_id: s.storeId,
          name: s.name,
          city: s.city,
          state: s.state,
          distance: s.distance,
          lowStock: s.lowStock === true,
          status: s.lowStock === true ? "LOW_STOCK" : s.lowStock === false ? "IN_STOCK" : "UNKNOWN",
        };
      });
      return { sku: sku, stores: stores };
    });
  }).catch(function(err) {
    return { sku: sku, error: err.message };
  });
}

function runBatch(items, fn, concurrency) {
  var results = [];
  var pos = 0;
  function process() {
    if (pos >= items.length) return Promise.resolve(results);
    var batch = items.slice(pos, pos + concurrency);
    pos += concurrency;
    return Promise.all(batch.map(function(item) {
      return fn(item).then(function(r) {
        results.push(r);
        return r;
      }).catch(function(e) {
        results.push({ error: e.message });
        return null;
      });
    })).then(function() {
      return process();
    });
  }
  return process().then(function() { return results; });
}

function lookupZip(zip, targetKey, bestbuyKey, tcinFilter, skuFilter) {
  var targetItems = tcinFilter ? [{ tcin: tcinFilter, name: tcinFilter }] : TARGET_TCINS;
  var bestbuyItems = skuFilter ? [{ sku: skuFilter, name: skuFilter }] : BESTBUY_SKUS;

  var result = { zip: zip, target: [], bestbuy: [] };

  return runBatch(targetItems, function(p) {
    return targetCheck(p.tcin, targetKey).then(function(r) {
      r.name = p.name;
      return r;
    });
  }, 4).then(function(targetData) {
    result.target = targetData;
    if (bestbuyKey && bestbuyItems.length > 0) {
      return runBatch(bestbuyItems, function(p) {
        return bestbuyCheck(p.sku, zip, bestbuyKey).then(function(r) {
          r.name = p.name;
          return r;
        });
      }, 4);
    }
    return [];
  }).then(function(bestbuyData) {
    result.bestbuy = bestbuyData;
    return result;
  });
}

export async function onRequest(context) {
  var req = context.request;
  var env = context.env;
  var url = new URL(req.url);
  var zipParam = (url.searchParams.get("zip") || "").trim();
  var tcinFilter = url.searchParams.get("tcin");
  var skuFilter = url.searchParams.get("sku");

  if (!zipParam) {
    return new Response(JSON.stringify({ error: "Missing ZIP parameter" }), {
      status: 400,
      headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" },
    });
  }

  var targetKey = env.TARGET_API_KEY || "9f36aeafbe60771e321a7cc95a78140772ab3e96";
  var bestbuyKey = env.BESTBUY_API_KEY || "";

  var zips = zipParam.split(",").map(function(z) { return z.trim(); });
  var validZips = zips.filter(function(z) { return /^\d{5}$/.test(z); });

  if (validZips.length === 0) {
    return new Response(JSON.stringify({ error: "No valid 5-digit ZIPs provided" }), {
      status: 400,
      headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" },
    });
  }

  var results = await Promise.all(validZips.map(function(zip) {
    return lookupZip(zip, targetKey, bestbuyKey, tcinFilter, skuFilter);
  }));

  var response = { zips: results, count: results.length };
  if (validZips.length === 1) {
    response = results[0];
  }

  return new Response(JSON.stringify(response), {
    headers: {
      "Content-Type": "application/json",
      "Access-Control-Allow-Origin": "*",
      "Cache-Control": "public, max-age=60",
    },
  });
}
