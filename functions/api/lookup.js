const TARGET_TCINS = [
  { tcin: "93954435", name: "Prismatic Evolutions ETB" },
  { tcin: "91619922", name: "Surging Sparks ETB" },
  { tcin: "91619929", name: "Surging Sparks Booster Bundle" },
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

const BESTBUY_SKUS = [
  { sku: "6584756", name: "One Piece OP-09 Emperors in New World" },
  { sku: "6584757", name: "One Piece OP-10 Royal Blood" },
];

async function targetAvailability(tcin, apiKey) {
  const url = `https://redsky.target.com/redsky_aggregations/v1/web/pdp_client_v1?key=${apiKey}&tcin=${tcin}&visitor_id=tcg-bot-web`;
  const headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Origin": "https://www.target.com",
    "Referer": "https://www.target.com/",
    "Accept-Language": "en-US,en;q=0.9",
  };
  try {
    const resp = await fetch(url, { headers, timeout: 15000 });
    if (resp.status === 403) {
      return { tcin, online: null, error: "API key rejected (403)" };
    }
    if (!resp.ok) return { tcin, online: null, error: `Target error ${resp.status}` };
    const data = await resp.json();
    let shipStatus = null;
    const storeMethods = [];
    try {
      const avail = data.product.item.availability;
      shipStatus = avail.availability_status || null;
      const fulfillment = data.product.fulfillment;
      const opts = (fulfillment && fulfillment.options) || [];
      for (const opt of opts) {
        const ft = opt.fulfillment_type || "";
        const st = opt.availability_status || "";
        const oos = opt.is_out_of_stock_in_area;
        if ((st === "IN_STOCK" || oos === false) && ft) {
          storeMethods.push(ft);
        }
      }
    } catch (_) {}
    const online = shipStatus === "IN_STOCK" || shipStatus === "LIMITED_AVAILABILITY";
    return { tcin, online, shipStatus, storeMethods };
  } catch (err) {
    return { tcin, online: null, error: err.message };
  }
}

async function bestbuyStores(sku, zip, apiKey) {
  const fields = "storeId,name,city,state,distance,lowStock";
  const url = `https://api.bestbuy.com/v1/products/${sku}/stores.json?postalCode=${zip}&apiKey=${apiKey}&show=${fields}`;
  try {
    const resp = await fetch(url, { timeout: 15000 });
    if (!resp.ok) return { sku, error: `Best Buy error ${resp.status}` };
    const data = await resp.json();
    const stores = (data.stores ?? []).map((s) => ({
      store_id: s.storeId,
      name: s.name,
      city: s.city,
      state: s.state,
      distance: s.distance,
      lowStock: s.lowStock === true,
      status: s.lowStock === true ? "LOW_STOCK" : s.lowStock === false ? "IN_STOCK" : "UNKNOWN",
    }));
    return { sku, stores };
  } catch (err) {
    return { sku, error: err.message };
  }
}

async function mapConcurrent(items, fn, concurrency = 4) {
  const results = [];
  for (let i = 0; i < items.length; i += concurrency) {
    const batch = items.slice(i, i + concurrency);
    const batchResults = await Promise.allSettled(batch.map(fn));
    results.push(...batchResults);
  }
  return results;
}

export async function onRequest(context) {
  const { request, env } = context;
  const url = new URL(request.url);
  const zip = url.searchParams.get("zip");
  const tcinFilter = url.searchParams.get("tcin");
  const skuFilter = url.searchParams.get("sku");

  if (!zip || !/^\d{5}$/.test(zip)) {
    return new Response(JSON.stringify({ error: "Missing or invalid ZIP code (require 5 digits)" }), {
      status: 400,
      headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" },
    });
  }

  const apiKey = env.TARGET_API_KEY || "9f36aeafbe60771e321a7cc95a78140772ab3e96";
  const bestbuyKey = env.BESTBUY_API_KEY || "";

  const targetProducts = tcinFilter
    ? [{ tcin: tcinFilter, name: tcinFilter }]
    : TARGET_TCINS;
  const bestbuyProducts = skuFilter
    ? [{ sku: skuFilter, name: skuFilter }]
    : BESTBUY_SKUS;

  const targetResults = await mapConcurrent(
    targetProducts,
    (p) => targetAvailability(p.tcin, apiKey).then((r) => ({ ...r, name: p.name })),
    4
  );
  let bestbuyResults = [];
  if (bestbuyKey) {
    bestbuyResults = await mapConcurrent(
      bestbuyProducts,
      (p) => bestbuyStores(p.sku, zip, bestbuyKey).then((r) => ({ ...r, name: p.name })),
      4
    );
  }

  const target = [];
  const bestbuy = [];
  for (const r of targetResults) {
    if (r.status === "fulfilled") target.push(r.value);
  }
  for (const r of bestbuyResults) {
    if (r.status === "fulfilled") bestbuy.push(r.value);
  }

  return new Response(JSON.stringify({ zip, target, bestbuy }), {
    headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*", "Cache-Control": "public, max-age=60" },
  });
}
